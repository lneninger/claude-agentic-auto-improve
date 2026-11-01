# Concept Contract — Warn about project hook rows that launch a missing hook file

**Project:** claude-agentic-auto-improve
**Date:** 2026-10-31 (amended 2026-11-01 after critique and user approval)
**Requested by:** user
**Status:** approved
**Work Item Brief:** .claude/work-items/2026-10-31-71-warn-on-unshipped-hook-rows.md
**Tracking issue:** #71 (follow-up 1 only; `partial: true`, so delivery uses `Refs #71`)
**Budget:** 12,000 tokens

> **Protocol:** filled in by `data-architect`. Implementer agents refuse to run unless `Status: approved` or `Status: implemented`. The `concept-gate.py` hook reads `Files to touch` to decide whether Edit/Write/MultiEdit is allowed. Lifecycle and budget rules: `.claude/templates/concept-contract.md`.

---

## Business Concept

- **What is this thing, in domain language?**
  A project keeps its own hook rows in `.claude/settings.json` and `.claude/settings.local.json`. Each row launches a hook file. A hook file can go missing in two ways. The plugin may stop shipping the hook (the plain-language guard went in 0.9.20) and the operator deletes the file but keeps the row. Or the operator may delete a file the plugin still ships, such as the gate launcher, its body or its gate. Either way, the row still launches a file that is not there. Most such rows exit with code 2. On prompt submit, code 2 blocks every prompt. On a gate-launcher row it blocks every matched edit and shell call.

  This contract adds one read-only finding to `plugin_doctor.py --drift`, reported for every such row. The finding names the layer, event, matcher, the part of the row that is missing (its role), and the path as written. It also tells the operator what to do: **restore the file if the plugin still ships it, otherwise remove the row.** The doctor never edits a settings file.

  The scan reads the project alone. It runs before the plugin comparison and does not depend on it, so its findings are still reported when the comparison cannot run (exit 4).

- **Existing VOCABULARY.md terms that apply:** these are Universal-tier terms.
  - **Vendored asset**.
  - **Vendored-asset drift** and its amendments: the `--drift` run, its closed finding set and its `plugin` / `repo` owner.
  - **Install mode**: a `vendored` install has no enabled plugin install, which is why the scan must not need a plugin.
  - **Registration key**: not reused as the identity, because the key drops the matcher and the path as written.
  - **Gate launcher**: a stub, its body `_gate_launch.py`, and a gate argument, each of which can be missing.
  - **Disabled add-on hook**: its doctor half already names rows per layer.

- **New terms proposed for VOCABULARY.md:** both are Universal tier.
  - **Dangling hook row**: a hook row in the project's settings file or local settings file whose launched hook file is not a file on disk. "Launched hook file" means a `.py` path the doctor can resolve. For a gate-launcher row it also covers the launcher's body `_gate_launch.py` and the gate argument. The repair depends on the cause, and the doctor cannot tell which cause applies: restore the file if the plugin still ships it, otherwise remove the row. Removing a gate-launcher row also removes the main-checkout guard and the merge-direction check that the launcher hosts. `plugin_doctor.py --drift` reports it as the finding kind `dangling-hook-row`, computed from the project alone.
  - **Vendored-asset drift (amendment, 2026-11-01)**: `--drift` also reports `dangling-hook-row`, which is not drift because no plugin copy is compared. The doctor scans for it from the project alone, before and independent of the comparison. It is reported even when the comparison cannot run and the run exits 4.

---

## End-User View

Not applicable. Reason: `Files to touch` holds no Angular UI surface. The only user is the operator, who runs a command-line doctor. Its output is described under Data Shapes and in the README change.

---

## Data Shapes

### Entities

Not applicable. Reason: the scan is read-only. It persists nothing and owns no aggregate.

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Launched path | `raw`: string, the token as written in the row, quotes stripped.<br>`role`: enum `launched` \| `launcher-body` \| `gate-argument`. | The paths one row depends on.<br>`launched` is the token the existing reader `_launched_and_first_argument` selects. In exec form that is the first `args` element not starting with `-`; in shell form it is the first token after the command that ends in `.py`.<br>When the launched file name is `gate-launch.py`, the row has two more paths. `launcher-body` is `_gate_launch.py` in the same folder as the launched token, written `<folder of raw>/_gate_launch.py`. `gate-argument` is the token after the launched one.<br>Only `.py` paths, in any case, are checked.<br>Rows are checked only when they plainly launch a Python script through a bare Python interpreter with simple flags, in both shell and exec form; all other shapes are skipped. The accepted cost is missed findings. |
| Resolved hook path | `absolute` (a path) or `unresolvable` | The Launched path made absolute, by the first rule that applies:<br>1. A leading `${CLAUDE_PROJECT_DIR}`, `$CLAUDE_PROJECT_DIR` or `%CLAUDE_PROJECT_DIR%` is replaced by the project root.<br>2. Any other relative path is joined to the project root.<br>3. An absolute path is used as is.<br>4. Anything else is `unresolvable`, and is skipped: `${CLAUDE_PLUGIN_ROOT}`, any other `$` or `%` variable, or a leading `~`.<br>Backslashes are folded to forward slashes first. |
| Dangling hook row finding | `kind` = `dangling-hook-row`<br>`path` = `<layer>:<event>:<matcher>:<role>:<raw>`<br>`owner` = `plugin`<br>`remedy` = the fixed text "restore the file if the plugin still ships it, otherwise remove the row" | One finding in the existing `DriftFinding` shape, plus `remedy`.<br>`layer` is `settings.json` or `settings.local.json`. `matcher` is the group's matcher, or `*` when it has none or an empty one.<br>`raw` is everything after the fourth colon, so a Windows drive colon inside `raw` stays readable.<br>Example: `settings.json:UserPromptSubmit:*:launched:${CLAUDE_PROJECT_DIR}/.claude/hooks/plain-language-guard.py`.<br>In the `--json` output, `remedy` is a key on findings of this kind only; every other kind keeps its exact shape. In the text output, the remedy is printed after each such finding. |

**Invariants**

- **INV-1 (read only).** The scan only reads files and calls `is_file`. It never writes, renames or deletes, and `--fix` does not touch it.
- **INV-2 (found only when absent).** A finding exists if and only if a Resolved hook path is `absolute` and is not a regular file. A project whose rows all launch existing files gets none. (Since the 2026-11-01 amendment this applies to rows the doctor checks; a Project hook launcher row is skipped, so rows `_written_hook` writes today give no finding even when their file is gone.) A `launcher-body` path is checked only when the `launched` gate-launcher file exists, so a missing launcher is one finding, not two.
- **INV-3 (no guessing).** A path the doctor cannot resolve is never a finding.
- **INV-4 (names the event and the row).** The path names the layer, event, matcher, role and raw token. Two rows that differ only in matcher give two findings. Identical rows in one layer collapse into one finding, because findings are deduplicated by `(kind, path)`.
- **INV-5 (one token reader).** A new helper, `_launched_raw_tokens(entry)`, returns the launched token and the token after it as written. `_launched_and_first_argument` becomes a wrapper that returns their file names, so its callers do not change. The loop over event, then group, then entry moves into one generator, `_iter_rows(body)`, used by both `_effective_hooks` and the new scan.
- **INV-6 (owner always counts).** The owner is `plugin`, so `--ignore-repo-owned` never hides the finding.
- **INV-7 (independent of the comparison).** `dangling_hook_rows(project)` is a public, pure function of the project folder. `run_drift` calls it first, before it looks for a plugin. `compute_drift` does not call it, so a finding is never counted twice.
  - When the comparison succeeds, the report lists both sets of findings, sorted by `(kind, path)`.
  - When the comparison raises `DriftError` (no plugin found, a missing plugin folder, an unreadable add-on manifest, zero file pairs, or the same-root refusal), the report still lists the dangling-row findings. `error` holds the cause, and the exit code stays 4.
  - The exit codes become: 4 if the comparison could not run, else 1 if any finding counts, else 0.
- **INV-8 (project layers only).** The scan reads `PROJECT_SETTINGS_LAYERS` only, never the user layer. If a layer does not parse, the scan skips that layer. The comparison reports the parse error as exit 4, whenever the comparison gets far enough to read that layer.
- **INV-9 (parity with the installer).** Every folder spelling in the installer's `_PROJECT_HOOK_DIRS` resolves to `<project>/.claude/hooks`. A test pins this, the way `test_plugin_doctor.py:1419` already pins `ADDON_DOCUMENTS_REL`. The doctor still does not import the installer at run time.

### Events

Not applicable. Reason: a command-line report emits and subscribes to nothing.

### Commands (if any)

| Name (imperative) | Handler | Payload | Possible rejections |
|-------------------|---------|---------|---------------------|
| Check plugin drift (existing, extended) | `plugin_doctor.py --drift` → `run_drift`, which calls `dangling_hook_rows` and then `compute_drift` | project, optional plugin, `--json`, `--ignore-repo-owned` | Exit 4 for every cause the comparison already rejects, now with the dangling-row findings still listed. Exit 1 for any counted finding, the new kind included. |

---

## Reused Mechanisms

- **Vendored-asset drift (the `--drift` run)**: **extended.**
  - The finding kind `dangling-hook-row` is added to `FINDING_KINDS`, to the comment block that lists the closed set of kinds, and to the README.
  - The report shape, the owner field and the `(kind, path)` deduplication are reused unchanged.
  - Two additions: the per-kind `remedy` key, and the rule that dangling-row findings are listed even on exit 4 (INV-7).
  - **Enum coverage:** the set of finding kinds needs the new value. The owner set needs none.
- **Disabled add-on hook** (the doctor half, D-3): its pattern is reused, one layer at a time with a colon-joined path. Its code does not change.
- **Gate launcher**: consumed as is. Its three files decide the three roles.
- **Preview-hash apply**: not touched. The installer does not change, and its test suite gains one test.

---

## New Mechanisms (if any)

None — all extensions.

---

## Extension Points

- `FINDING_KINDS` and the comment block that lists the kinds gain `dangling-hook-row`. A fixed constant holds the remedy text.
- `_launched_raw_tokens(entry)` is added. `_launched_and_first_argument` wraps it.
- `_iter_rows(body)` yields `(event, matcher, entry)`. `_effective_hooks` and the scan both use it.
- `dangling_hook_rows(project) -> List[DriftFinding]` is public and needs no plugin.
- `run_drift` calls `dangling_hook_rows` before it looks up the plugin. It merges those findings with the comparison's, or, in the `DriftError` branch, with none. `drift_report` adds `remedy` to findings of this kind.
- A module constant holds the three project-folder variable spellings (INV-9).

---

## Integration Surfaces

Not applicable. Reason: there is no API, SignalR or DTO boundary. Both scripts are Python command-line tools in one layer. The one pairing, the installer writing a vendored row (`_written_hook`) and the doctor reading it back, is pinned by the test in the installer's suite in block 1.

---

## Adjacent Areas

Not applicable. Reason: the cross-area scan cannot return a signal. `.claude/area-mapping.json` declares an empty `areas` set, which I checked directly. I did not run the script, because this agent has no shell.

---

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

---

## Chat Tool Impact

Not applicable. Reason: the contract adds no REST endpoint and no SignalR event.

---

## Non-Goals

- Removing, rewriting or restoring anything, automatically or through `--fix`.
- Telling the operator which of the two remedies applies. The text names both, because the plugin may not be present.
- Issue #71 follow-up 2 (scanning hook text for project-specific names) and follow-up 3 (the old dispatcher notice). Both stay open on the issue.
- Missing dispatcher members. The dispatcher exits 0 for them.
- The user settings layer.
- Any change to `auto_improve_finish_install.py`, including its readiness report.
- Rows that launch a program other than a `.py` file. Also a shell-form row whose command is the `.py` file itself, with no interpreter in front: `_launch_tokens` drops `tokens[0]`, and the installer never writes this form.
- Rows of any shape other than a bare Python interpreter with simple flags launching a `.py` script (shell or exec form): they are skipped, and the accepted cost is missed findings.
- Splitting a finding path whose matcher contains a colon. The path is text for the operator to read, not a format for other tools to parse.

---

## Confidence

Confidence: Medium. High on the token reader, the layer walk, the finding shape, the installer's row form and all three launcher failure paths, which were read in source. Medium on two assumptions. First, that a relative row path resolves against the project root. Second, that a patch version raise is the right step.

---

## Alternatives Considered & Why Rejected

- **Option A (chosen):** `plugin_doctor.py --drift` with a scan that reads the project alone, runs before the comparison and survives exit 4.
  - Why: the drift run already reads both project layers and keeps a closed set of finding kinds. It never writes, and it can be run in every install mode.
- **Option B (rejected):** a field in the finish-install readiness report.
  - Why rejected: the readiness report refuses every install mode except `plugin` (`auto_improve_finish_install.py:1265-1267`), so it would never run on a vendored install.
- **Option C (rejected):** both scripts report the finding.
  - Why rejected: two readers of the same rows would drift apart. The two scripts already split a row into words differently (`_hook_key` in the installer, `_launched_and_first_argument` in the doctor).
- **Option D (rejected):** the doctor's default mode (`missing` / `--fix`).
  - Why rejected: that mode treats every gap as a file to create, and `--fix` creates it. For a hook the plugin no longer ships, that is the wrong repair. The finding must give both repairs and must not offer to perform either one.

---

## Uncertain Assumptions

- `VERIFIED via auto_improve_finish_install.py:1166-1268`: the readiness report runs only in `plugin` mode, and `unresolved-commands` reads only the plugin's `hooks.json`.
- `VERIFIED via auto_improve_finish_install.py:1312-1325`: a vendored row is written in exec form, `py -3 ${CLAUDE_PROJECT_DIR}/.claude/hooks/<file>` (`python3` on POSIX). A gate argument is rewritten to the same folder.
- `VERIFIED via auto_improve_finish_install.py:211-212`: the installer recognises five spellings of the project's hooks folder.
- `VERIFIED via plugin_doctor.py:404-428`: in exec form `-3` is skipped. In shell form the first `.py` token after the command is used, with quotes stripped.
- `VERIFIED via .claude/hooks/_gate_launch.py:96-97, 120-122`: a missing gate file returns a block from `_decide`, and `main()` exits 2. The exit-1 path at lines 127-133 applies only to a gate that exists and raises.
- `VERIFIED via .claude/hooks/gate-launch.py:3-14`: a missing or broken body `_gate_launch.py` falls into `os._exit(2)`, so it also blocks.
- `VERIFIED via plugin_doctor.py:746-767`: every `DriftError` returns exit 4 with `findings: []` today. INV-7 changes this for dangling-row findings only.
- `VERIFIED via the parent contract and README.md:227-231`: a row whose launched script is missing exits 2. The parent contract checked this with a real call.
- `ASSUMED`: the host runs a hook command with the project root as its working directory. If it does not, a relative-path row could produce a false finding or be missed. Verification: one harmless relative-path row in a scratch project. The installer never writes such a row.
- `ASSUMED`: a patch raise (0.12.3 → 0.12.4) is enough. The version check only requires a raise. Verification: run `check_version_bump.py` in its default mode against the base.

---

## Failure Modes & Mitigations

- **FM:** a working row is reported as dangling because it uses a variable form the doctor does not expand.
  - **Mitigation:** INV-3, plus the parity test in INV-9.
- **FM:** a second word-splitter disagrees with `_effective_hooks` about which file a row launches.
  - **Mitigation:** INV-5. The scan and `_effective_hooks` share one token helper and one row walker. The existing registered-twice tests guard the refactor.
- **FM:** `--ignore-repo-owned` hides a row that blocks every prompt.
  - **Mitigation:** INV-6, owner `plugin`.
- **FM:** the finding is thrown away because the comparison cannot run: no plugin found (the normal case for a vendored install with no `--plugin`), a missing plugin folder, an unreadable add-on manifest, or zero file pairs compared.
  - **Mitigation:** INV-7. The scan runs first and does not depend on the plugin, and its findings are listed beside `error`. Tests cover the no-plugin case and the zero-pairs case.
- **FM:** the operator removes a gate-launcher row whose launcher, body or gate was deleted by accident. That would lose the main-checkout guard.
  - **Mitigation:** the `remedy` text puts restoring the file first, and the `role` segment shows that the row is a launcher row.
- **FM:** a caller reads exit 4 and ignores the findings.
  - **Mitigation:** the README states that exit 4 can carry dangling-row findings, and the text output prints them before the "cannot compare" line.

---

## Open Questions for User

- [x] **1. Which script owns the check?** Answer (2026-11-01): `plugin_doctor.py --drift` only.
- [x] **2. Criterion 5 ("tests in both suites").** Answer (2026-11-01): add a test to the installer's suite that feeds rows built by `_written_hook` to the doctor, plus the unit cases in the doctor's suite.
- [x] **3. Kind and term name.** Answer (2026-11-01): `dangling-hook-row` / **Dangling hook row**. The remedy text names both repairs (BLOCKER 2).
- [x] **4. Findings when the comparison cannot run.** Answer (2026-11-01): changed. Dangling-row findings are still reported on exit 4 (INV-7, BLOCKER 3).
- [x] **5. Check the gate argument?** Answer (2026-11-01): yes. The launcher's body is checked as well. Both block with exit 2 (BLOCKER 1, WARN 1).

---

## Critique

**Critic:** contract-critic
**Date:** 2026-10-31
**Verdict:** blockers-found

### Findings

- **[BLOCKER] The VERIFIED claim that a missing gate exits 1 and does not block is false**
  - **What is wrong:** `_gate_launch.py:96-97` checks `os.path.isfile(gate_arg)` inside `_decide` and returns `("block", "... the gate file %s is missing")`, so `main()` exits 2 at lines 120-122. The `runpy` branch at 127-133 that the contract cites runs only when the gate file exists. A launcher row whose gate is missing therefore blocks every matched Edit/Write call, and since block 14 also every `Bash|PowerShell` call. Open Question 5 asks the user to decide on the opposite premise.
  - **Prior artifact ignored:** `JOURNAL.md` → `2026-10-04 — Check a documented guard behaviour against the guard's code`, which `## Lessons referenced` claims is heeded. Also `VOCABULARY.md` line 64, **Gate launcher**: "A failure in its own code is a block."
  - **Where in this contract:** `## Uncertain Assumptions` and Open Question 5.
  - → Addressed by: the Uncertain Assumptions entry, now `VERIFIED via _gate_launch.py:96-97, 120-122` (exit 2, a block), and the corrected premise of Open Question 5. The gate-argument check is kept.
- **[BLOCKER] The new term's remedy "remove the row, never create the file" is false for rows that launch a hook the plugin still ships**
  - **What is wrong:** OQ3 widens the term to "the condition whatever the cause", but the definition keeps the remedy that is only right for an unshipped hook. For a gate-launcher row whose `concept-gate.py` gate, or whose launcher, was deleted by accident, removing the row also removes the main-checkout guard and the **Merge direction** check that the launcher hosts. Restoring the file is the correct repair there. Alternative D's rejection rests on the same universal claim.
  - **Prior artifact ignored:** `JOURNAL.md` → `2026-10-28 — A new term's definition must be true against every existing member`. `VOCABULARY.md` lines 64-65, **Gate launcher**.
  - **Where in this contract:** `## Business Concept` → New terms; Open Question 3.
  - → Addressed by: the definition of Dangling hook row, the `remedy` field of the finding ("restore the file if the plugin still ships it, otherwise remove the row"), a Failure Modes entry, and the reworded reason for rejecting Option D.
- **[BLOCKER] Acceptance criterion 1 is narrowed silently: in the hazard case the finding is thrown away by exit 4**
  - **What is wrong:** every `DriftError` makes `run_drift` return exit 4 with `findings: []` (`plugin_doctor.py:759-767`). The causes include "no plugin found" (`:756-757`), a missing plugin folder (`:600-603`) and an unreadable add-on manifest (`:504-519`). A vendored install is one where no enabled install exists, so a bare `--drift` there may never list the dangling row. The mitigation rested on the unproven sentence "Vendored installs always compare their hooks folder".
  - **Prior artifact ignored:** brief criterion 1; `VOCABULARY.md` line 42, **Install mode**; `README.md:923-925`.
  - **Where in this contract:** `## Failure Modes & Mitigations`; `## Data Shapes` → Commands.
  - → Addressed by: INV-7 (the scan runs first, does not depend on the plugin, and its findings are listed on exit 4), the Commands row, the rewritten Failure Modes entry (the unproven sentence is gone), the Vendored-asset drift amendment, and the no-plugin and zero-pairs tests in block 1.
- **[WARN] The gate launcher's body `_gate_launch.py` is not checked, although a missing body blocks**
  - **What is wrong:** the stub `gate-launch.py:3-14` exits 2 when its body is missing.
  - → Addressed by: the `launcher-body` role in the Launched path row, INV-2, and a VERIFIED entry for `gate-launch.py:3-14`.
- **[WARN] Confidence is High while two assumptions are ASSUMED**
  - → Addressed by: Confidence lowered to Medium, with the two assumptions named.
- **[WARN] No amendment is proposed for Vendored-asset drift, although `--drift` gains a kind that is not drift**
  - → Addressed by: the proposed term **Vendored-asset drift (amendment, 2026-11-01)** and the README sentence in block 1.
- **[NIT] Undecided design is left in Extension Points.** Addressed: the names `dangling_hook_rows`, `_launched_raw_tokens` and `_iter_rows` are now fixed, and the decision to share one row walker is made.
- **[NIT] The `role` field never reaches the finding; a Windows `raw` adds a colon.** Addressed: `role` is now a segment of the path, and `raw` is everything after the fourth colon.
- **[NIT] A shell-form row whose command is the `.py` file itself is never checked.** Addressed: listed in Non-Goals.

### Applicable journal entries

- **2026-10-04 — Check a documented guard behaviour against the guard's code**: violated in the draft. Now heeded: all three launcher failure paths are verified against the source.
- **2026-10-28 — A new term's definition must be true against every existing member**: violated in the draft. Now heeded through the two-branch remedy.
- **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work**: heeded by INV-3 and INV-9.
- **2026-10-04 — A root locator can return the consumer itself under vendoring**: heeded by INV-7.
- **2026-10-22 — Describe a broken install by the rows each install age really has**: heeded by the block 1 test list.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval**: heeded in this amendment.

---

## Lessons referenced

- **2026-10-04 — Check a documented guard behaviour against the guard's code**: heeded by Uncertain Assumptions, where all three launcher paths are VERIFIED against the source.
- **2026-10-22 — Describe a broken install by the rows each install age really has**: heeded by INV-4 and the tests in block 1, which cover the prompt-submit row written since 0.9.8 and the direct Stop row of older installs.
- **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work**: heeded by INV-3 and INV-9.
- **2026-10-04 — A root locator can return the consumer itself under vendoring**: heeded by INV-7. The scan takes no plugin root.
- **2026-10-28 — A new term's definition must be true against every existing member**: heeded by the Dangling hook row definition, which gives both remedies and covers all three launcher files.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval**: heeded. Every answer and finding above has changed the contract body.
- Orthogonal to north-stars: none (the register holds no active thought).

---

## Implementation Handoff

This contract has one mergeable block, delivered as one pull request into the default branch. With a single block the Parent Branch Delivery Rule does not apply, so the block raises the plugin version itself. The review runs as `/ship`'s reviewer step.

### 1. Dangling hook row check (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/scripts/plugin_doctor.py`
- `.claude/scripts/tests/test_plugin_doctor.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `README.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `.cursor-plugin/plugin.json`

**Pre-written TASK block:**
```
TASK: Add the read-only finding kind dangling-hook-row to plugin_doctor.py --drift. A finding is a row in
  settings.json / settings.local.json whose launched .py file (role launched) does not exist. For a
  gate-launch.py row, the launcher body _gate_launch.py beside it (role launcher-body, checked only when the
  launcher exists) and the gate argument (role gate-argument) are checked too. The scan reads the project
  only, runs before the plugin comparison and survives exit 4. Report only; never edit a settings file.
CONTEXT: concept contract at .claude/concepts/2026-10-31-warn-on-unshipped-hook-rows.md (Data Shapes,
  INV-1..INV-9). Brief: .claude/work-items/2026-10-31-71-warn-on-unshipped-hook-rows.md.
FILES: as listed in Files to touch.
CONSTRAINTS:
  - Do NOT change auto_improve_finish_install.py. Its suite gains a test only.
  - INV-5: add _launched_raw_tokens(entry) and make _launched_and_first_argument a basename wrapper over it;
    _iter_rows(body) yields (event, matcher, entry) for both _effective_hooks and the scan. No second
    word-splitter. All existing registered-twice / disabled-hook tests pass unchanged.
  - Public pure dangling_hook_rows(project) -> List[DriftFinding]; no plugin argument. compute_drift does
    NOT call it. run_drift calls it first, before the plugin lookup; it merges its findings with the
    comparison's, or in the DriftError branch lists them beside "error" and still exits 4. Exit order:
    4, else 1 if anything counts, else 0. Text output prints the findings before "cannot compare".
  - Path "<layer>:<event>:<matcher or *>:<role>:<raw>", owner "plugin". Findings of this kind carry
    remedy = "restore the file if the plugin still ships it, otherwise remove the row" in --json, and the
    same text in the text output. Every other kind keeps its exact shape.
  - Resolution exactly as the "Resolved hook path" row; every other form is never reported.
  - FINDING_KINDS and the comment listing the kinds gain dangling-hook-row.
  - test_plugin_doctor.py, a new class TestDriftDanglingHookRow, with positive AND negative controls:
      the 0.9.8+ UserPromptSubmit row and the pre-0.9.8 direct Stop row to a deleted
      plain-language-guard.py (two findings, each naming its event); the same rows with the file present
      (no finding); exec form and shell form; a gate-launch row with the launcher missing (one finding,
      role launched), with the body missing (launcher-body), with the gate missing (gate-argument);
      settings.local.json named as its layer; two matchers give two findings; a Windows absolute raw
      path; ${CLAUDE_PLUGIN_ROOT}, %OTHER% and ~ rows never reported; still counted under
      --ignore-repo-owned; remedy present in --json; run_drift exits 1 with a plugin. Survival: with no
      plugin found, and again with zero file pairs compared, run_drift exits 4 AND lists the finding
      beside "error". Parity: every _PROJECT_HOOK_DIRS spelling of the installer resolves to
      <project>/.claude/hooks. Extend TestDriftNeverWrites with a dangling row.
  - test_auto_improve_finish_install.py, a writer-to-reader test: rows from _written_hook (win32 and
    POSIX; the gate launcher with its gate) give zero dangling-hook-row findings while the launcher, body
    and gate exist, and one finding per deleted file after deletion (body only while the launcher is
    present). The settings file bytes are identical before and after.
    [Superseded 2026-11-01, see the amendment below: that per-file result holds only for old exec-form
    rows built by hand; rows _written_hook writes today are Project hook launcher rows and give no finding.]
  - README.md: in the --drift paragraph, the new kind, its remedy and that exit 4 can carry it; a
    pointer in the 0.9.20 plain-language removal paragraph; a short "Changed in 0.12.4" note before the
    0.12.0 one.
  - Raise the version 0.12.3 -> 0.12.4 in all five declarations (marketplace.json twice).
  - Run both suites and test_check_version_bump.py, and report the commands with their exit codes.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-31-warn-on-unshipped-hook-rows.md
  contract_status: approved
```

---

## Review checklist (filled in after implementation)

`pr_merged.py` fills this list. Do not tick lines by hand.

- [ ] Implementation matches Data Shapes exactly
- [ ] Reused Mechanisms are actually reused (no parallel implementations introduced)
- [ ] New Mechanisms (if any) promoted to `MECHANISMS.md`
- [ ] New vocabulary terms promoted to `VOCABULARY.md`
- [ ] Integration surfaces reflected on both backend and frontend sides
- [ ] `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced
- [ ] No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface)
- [ ] `Status` flipped to `implemented`

---

Amendment 2026-11-01: whitelist, per review passes 4-6. Rows are checked only when they plainly launch a Python script through a bare Python interpreter with simple flags (shell and exec form); paths with unresolvable characters or shell syntax are skipped; all other shapes are skipped.

Amendment 2026-11-01 (after the merge of master 0.12.3, Project hook launcher): Project hook launcher rows are out of scope and are skipped. Why: the launcher falls back on its own when a project file is missing (it also looks in the main checkout of a worktree), so the doctor cannot judge from the project alone that such a row is broken, and a form the doctor cannot judge is skipped. This corrects the CONSTRAINTS test line and INV-2 above: the per-deleted-file result of the `_written_hook` round-trip holds only for old exec-form rows built by hand; rows the installer writes today give no finding. Status is unchanged.
