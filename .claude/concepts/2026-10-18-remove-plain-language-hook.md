# Concept Contract — Remove the plain-language guard hook from the plugin

**Project:** claude-agentic-auto-improve
**Date:** 2026-10-18
**Requested by:** user
**Status:** approved
**Work Item Brief:** .claude/work-items/2026-10-18-remove-plain-language-hook.md
**Tracking issue:** #71 (follow-ups only; the work itself has no tracker issue)

> **Protocol:** filled in by `data-architect`. Lifecycle and gate rules: see `.claude/templates/concept-contract.md`.

---

## Business Concept

- **What is this thing, in domain language?**
  The plugin ships a hook called the **plain-language guard**. At the end of each turn it reads the assistant's last message. When a sentence is too long, a short form is not spelled out, a bare number is used as a label or dashes are stacked, it holds the turn and asks for a rewrite. It has a second registration on prompt submit (`--carry-forward`). That one hands over a correction note the end-of-turn run saved. The user asked to remove this hook. This contract removes the guard's file, its rules file, its tests and both registrations, and every list, count and document that names it. The plain-language **agreement** stays. It is the standing advice text that `working-agreements.py` delivers at session start, and it stays the one agreement the size limit never drops. Only its closing sentence changes, because that sentence claims a checker exists. The **Stop dispatcher** (`stop-dispatcher.py`) stays as the single Stop seam, with one member left: the **Changed-file check** (`../scripts/concept_changed_check.py`).

- **Existing VOCABULARY.md terms that apply:**
  - **Working agreement** and **Always-kept agreement** (Universal tier, 2026-10-05). Unchanged: the always-kept agreement is the shipped plain-language agreement, which is not the guard.
  - **Registration key** (Universal tier, 2026-10-04). The definition is unchanged. Its example names the guard, so the example is replaced (see Extension Points).

- **New terms proposed for VOCABULARY.md:** none.

---

## End-User View

Not applicable. Reason: `Files to touch` holds no Angular or other UI surface. The plugin's users are operators of Claude Code. What they notice is described under Data Shapes and in the README change: the end-of-turn rewrite requests and the carried-over notes stop, and the Stop status line names the Changed-file check instead.

---

## Data Shapes

### Entities

| Name | Fields | Invariants | Ownership (aggregate) |
|------|--------|------------|-----------------------|
| Plugin hook registration set (`.claude/hooks/hooks.json`) | entries: list of (event, matcher, script, extra arguments, async, status message) | **R1** exactly **13** entries (was 14). The only one removed is the prompt-submit entry `plain-language-guard.py --carry-forward`. **R2** no entry names `plain-language-guard.py` in any event. **R3** the Stop group still has two entries in this order: `stop-dispatcher.py` (not async) and `memory-pager.py` (async). **R4** the Stop dispatcher entry keeps a status message, which now reads `Checking changed files against approved contracts...` (the old text was `Checking the message reads plainly...`). **R5** prompt submit keeps exactly one entry, `plan-question-advisor.py`. | plugin |
| Stop member list (`CHECKS` in `stop-dispatcher.py`) | ordered list of member paths | **S1** `CHECKS == ["../scripts/concept_changed_check.py"]`. **S2** the behaviour is unchanged for any member list: the members run in order in one process; exit 2 when any member exits 2, with every member's error text in member order; any other member exit is ignored; output is passed through, or merged JSON when several members spoke; the dispatcher's own failure exits 0; a missing member gets one error-log line plus one notice per session and never crashes. **S3** the code changes only in the `CHECKS` literal and in docstring and comment text. | plugin |
| Shipped hook files (`.claude/hooks/*.py`, no leading underscore) | file names | **F1** 14 files on disk (13 hook files plus `gate-launch.py`, which was 15). The README's count of "hook files", which leaves out the launcher, goes from fourteen to **thirteen**. **F2** each file is still registered in `hooks.json` or named in a dispatcher's `CHECKS` (manifest INV-8). | plugin |
| Guard rules files | file names | **G1** four guard files plus `working-agreements.rules.json` is the shipped set: `architecture-guard.rules.json`, `architecture-guard.exceptions.json`, `db-destructive-guard.rules.json`, `integration-check.rules.json`, and `working-agreements.rules.json` (which belongs to the working-agreements hook and is untouched). `plain-language-guard.rules.json` is deleted. | plugin |
| Plain-language agreement (`.claude/agreements/plain-language.md`) | title, seven labelled rules, closing line | **A1** the title and the seven labels stay unchanged, and so does the element-rule sentence holding "no automatic checker". **A2** the closing line no longer claims that an end-of-turn checker exists (wording: Open Question 1). **A3** `ALWAYS_KEPT_SLUG = "plain-language"` and the delivery order in `working-agreements.py` are not touched. | plugin |
| Leftover runtime state in a consuming project | `<project>/.claude/state/plain-language-guard-<session>.json`, `<project>/.claude/logs/plain-language-guard.log` | **L1** no shipped code reads or writes them after this change. **L2** no shipped code deletes them, because they are machine-local runtime files and not repository content (`state_dir()` docstring: "Gitignored -- runtime"). A saved note that was never handed over is simply never delivered. **L3** the README removal note says both may be deleted by hand. | consuming project |

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Plugin version | semantic version string | 0.9.11 becomes **0.9.12** in all five declarations (`plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` twice, `.cursor-plugin/plugin.json`). Manifest checks INV-11 and INV-O1 enforce this. |
| Plugin description count | text | The manifest description "17 enforcement hooks" changes to "13 hooks" in `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`. Seventeen matched no set that can be counted (see Uncertain Assumptions). |

### Events

| Name (past tense) | Emitter | Listeners | Payload |
|-------------------|---------|-----------|---------|
| (removed) PlainLanguageBreakFound, NoteCarriedForward | the guard | the model | Both stop existing. No new event is introduced. |

### Commands (if any)

Not applicable. Reason: the change removes behaviour and adds no command.

---

## Reused Mechanisms

- **Session-start context delivery** (MECHANISMS Universal): consumed as-is. The agreement text changes, the hook does not. `ALWAYS_KEPT_SLUG` and the order logic stay untouched (A3).
- **Guard rules file** (MECHANISMS Universal): consumed as-is. The registry entry's list shrinks from five files to four (G1). Nothing changes about how the mechanism works.
- **Preview-hash apply** / `auto_improve_finish_install.py`: consumed as-is, **with no code change**. VERIFIED: the script names no hook file and reads its registrations from whichever `hooks.json` it is given. A search for `plain-language` in the script finds nothing. Only its test suite names the guard.
- **Registration key** (VOCABULARY): consumed as-is. Its example is reworded.
- **Bidirectional sync with manual conflict resolution** (MECHANISMS Universal): consumed as-is. A consuming repository whose copy of the guard is missing from the plugin gets a one-sided-file report, and the run stops with a conflict to resolve (MECHANISMS: exit 2). Nothing is deleted for it, but the obvious resolution, deleting the local copy, is the harmful order when the project still has the rows. The sync configuration is not in this repository, so which trees carry the guard cannot be checked here. The README removal note carries the safe order (see Failure Modes).
- **Stop dispatcher missing-member path** (contract 2026-10-12 dedupe, not a registered mechanism): consumed as-is. An old vendored `stop-dispatcher.py` that still lists the guard after the guard file is gone exits 0 and gives one notice per session.
- **Follow-up stub lifecycle** (`.claude/templates/followup-stub.md`): the 2026-10-05 stub about the guard naming a person is moot. Under the lifecycle it is renamed to `.followup.superseded.md` and gets a `Superseded by:` line.

## New Mechanisms (if any)

None. This is a removal.

---

## Extension Points

Every live reference that must change, by file. Line numbers are from the worktree at draft time.

1. **`.claude/hooks/hooks.json`**
   - Delete the prompt-submit entry at lines 158-162 (the opening brace is on 158 and the trailing comma on 162).
   - Edit the Stop dispatcher's `statusMessage` at line 178 (R4).
   - In the `$comment` text: line 26 "fourteen entries" becomes "thirteen". At line 27, drop "and the plain-language guard" from the gates. Lines 33-35 become "runs the Changed-file check, .claude/scripts/concept_changed_check.py".
   - Keep the JSON valid and the comment as a string array.
2. **`.claude/hooks/stop-dispatcher.py`**: `CHECKS` becomes a list with one member (S1). Rewrite the module docstring:
   - Lines 3-9 say why it exists: one Stop seam, so a later member costs no extra program start, plus the missing-member notice.
   - Line 21 drops the guard example.
   - The `CHECKS` comment says "the Stop members".
3. **Delete** `.claude/hooks/plain-language-guard.py`, `.claude/hooks/plain-language-guard.rules.json` and `.claude/hooks/tests/test_plain_language_guard.py`.
4. **`.claude/hooks/tests/test_stop_dispatcher.py`**:
   - The `CHECKS` row asserts `[CONCEPT]`.
   - The rows about several members (order, error texts in order, exit 2 not stopping the next, exit 1, raise, and the missing first or second member) keep their assertions. They run against a **test copy of the dispatcher whose `CHECKS` literal is rewritten** to `["first-stub.py", CONCEPT]`. The Workspace asserts that the rewrite happened, so a renamed constant fails loudly instead of silently testing one member.
   - Add rows against the real one-member list: a silent member gives exit 0, its exit 2 stops the turn, and its systemMessage passes through.
   - Replace `PlainLanguageGuardIdentityTests` with a stub identity row. A stub writes fixed bytes, including a non-ASCII character, to stdout and stderr and exits 2. Run it alone and through the real dispatcher: the exit code, stdout and stderr must be byte-identical.
   - Update the module docstring.
5. **`.claude/hooks/tests/test_hook_data_files_project_first.py`**:
   - Remove section 3 (lines 231-274).
   - Remove the guard's template from the lists at lines 147-148 and 160-161.
   - Remove `CLAUDE_PLAIN_LANGUAGE_GUARD` from the environment variables removed at line 113.
   - Remove the guard from the docstring at line 12.
6. **`.claude/hooks/tests/test_working_agreements.py`**: add one row. The real `plain-language.md` must not contain "writing checker catches", and the existing "no automatic checker" phrase row stays green (A1, A2).
7. **`.claude/hooks/db-destructive-guard.py`** line 393: a comment only. Drop "and plain-language-guard.rules.json". No code changes.
8. **`.claude/agreements/plain-language.md`** line 19: apply the Open Question 1 answer.
9. **`.claude/scripts/tests/test_plugin_manifests.py`**:
   - `EXPECTED_TABLE`: drop line 580 and rewrite the comment at 583-584. The assertion becomes `== 13`.
   - `table_problems`: "14" and "fourteen" become 13 and thirteen at lines 621-622. Delete lines 633-634: the exact-table rule already rejects any extra row.
   - Labels at lines 654 and 657 become "thirteen".
   - `STOP_STATUS` gets the new text (R4).
   - The required-member set at lines 268-272 loses the guard, and the label at line 262 becomes "the Stop members". The label at line 268 ("at least the six members") becomes five.
   - The word "fourteen" also appears in the INV-O1 docstring (line 53) and the section print (line 550): both become "thirteen".
   - The control at line 725 uses `memory-pager.py` as its string-form example.
   - Delete the control at lines 752-753.
10. **`.claude/scripts/tests/test_auto_improve_finish_install.py`**:
    - In the fixture `REGISTRATIONS`, the guard pair at lines 219-220 becomes a fictional `example-paired-hook.py`: one entry on prompt submit with the argument `--on-prompt`, and one at Stop with no argument. The fixture's counts **stay 17 registrations and 16 files**, so this suite's key-with-arguments coverage survives.
    - Rename and reword `test_the_plain_language_guard_pair_stays_two_distinct_keys`, `test_only_one_of_the_pair_present...`, the skip test at 1820-1825 and the positive control at 1902-1910 to that name.
    - `test_the_real_plugin_hooks_json_yields_exactly_its_fourteen_registrations` becomes "thirteen", with 14 changed to 13 at lines 1882 and 1893 and its comment updated.
    - The assertion message at line 1662 ("16 hook files, plain-language-guard twice") names the fictional pair instead.
11. **`README.md`**:
    - Line 113: "fourteen" becomes "thirteen".
    - Delete the table row at 135.
    - Stop row at 138: it runs `../scripts/concept_changed_check.py`, and the Blocks column reads "yes, with a list of files no contract covers".
    - Delete the guard bullet at 167.
    - Rewrite the stop-dispatcher bullet at 168-170 for one check.
    - Line 195: the advisory list drops the guard's file and reads three files.
    - Environment-variable table (README lines 206-216): it has ELEVEN rows today (including `CLAUDE_CONFIG_DIR`), so the current sentence "Eight of the ten ... Two are not" is already false. Count the rows by hand. After the guard's row (209) is deleted there are ten rows: seven kill switches and three others. Write the sentence to match that count ("Seven of the ten ... Three are not"), and recount before writing. Delete the row at 209. Manifest INV-12 checks this table against the variables the code reads.
    - Hooks section at 500-524: the list without the guard and "thirteen hook files".
    - Rewrite the registration arithmetic correctly: nine files are registered directly (the concept gate through the launcher), `db-destructive-guard.py` is on three matchers, `db-research-readonly-guard.py` on two and the launcher on two, which makes thirteen. The current sentence's arithmetic was already wrong.
    - Add a short **removal note** under "Installing the hooks turns on enforcement" (Open Question 2).
12. **`.claude/registries/MECHANISMS.md`** line 52 (Guard rules file): "Five exist" becomes "Four exist", without the guard's file. **`.claude/registries/VOCABULARY.md`** line 42 (Registration key): the example becomes "`Stop` + `memory-pager.py` with no arguments. The same file registered with an extra argument would be a different key."
13. **Follow-up stub** `.claude/concepts/followups/2026-10-05-plain-language-guard-names-a-person.followup.md`: rename it to `...followup.superseded.md` and add `**Superseded by:** .claude/concepts/2026-10-18-remove-plain-language-hook.md (moot: the guard was removed)` at the top.
14. **Version**: 0.9.12 in the five declarations, and the description count (Value Objects).

**Not changed, verified:**
- `auto_improve_finish_install.py`.
- `working-agreements.py` and its rules file.
- `concept_changed_check.py`. Its docstring line 12 stays true: the dispatcher process still starts at Stop.
- `test_plugin_doctor.py`, which uses its own stub member names.
- Root `CLAUDE.md`, `CONTRIBUTING.md`, skills and agents. A search finds no reference to the guard in any of them.

---

## Integration Surfaces

Not applicable. Reason: the change is contained in the plugin's hook layer. The only boundary is Claude Code reading `hooks.json`, and its shape (event, matcher, exec-form command) is unchanged. No API, SignalR or data-transfer-object surface exists in this repository.

---

## Adjacent Areas

Not applicable. Reason: the cross-area scan was **not run**, because this agent has no shell. The scan also has nothing to score against: `.claude/area-mapping.json` declares an empty `areas` set. The main session may run `py -3 .claude/scripts/cross_area_scan.py <this file>` to confirm. One adjacent concern came from the design investigation, not from the scanner. It is filed as `.claude/concepts/followups/2026-10-18-warn-on-rows-naming-unshipped-hooks.followup.md` (Issue: pending).

## UI Implications

Not applicable. Reason: no frontend consumer appears in Integration Surfaces.

## Chat Tool Impact

Not applicable. Reason: the change adds or changes no REST endpoint and no SignalR event.

---

## Non-Goals

- Rewording or removing the plain-language agreement beyond its closing line (A1).
- Any other hook. That includes the memory pager, the Changed-file check, and removing the Stop dispatcher itself.
- Deleting leftover state or log files in consuming projects (L2), or editing any project's `settings.json`.
- Rewriting past contracts, work items or journal entries. `2026-10-05-working-agreements-session-start.md` and `2026-10-04-auto-improve-finish-install-skill.md` keep their mentions as history.
- A check that detects project rows naming a deleted hook. This is deferred to the follow-up stub.
- Adding `plain-language-guard.py` to `CUT_HOOKS` in the manifest suite. The exact-table rule already rejects its return, and adding it would leave a live mention that the brief's search criterion forbids.

---

## Confidence

Confidence: Medium-High. High on the counts (recounted from `hooks.json` and from disk; the critic recounted the README variable table and the registrations). High on the exit-2 behaviour of a missing script (VERIFIED by one real call). Medium on the reference inventory: the critic found four spots the first sweep missed (now listed) and two spelling forms the closing search missed (now added). The implementer's final search is the backstop.

---

## Alternatives Considered & Why Rejected

- **Option A (chosen):** Delete the guard. Keep `stop-dispatcher.py` with the Changed-file check as its only member.
  - Why: the brief requires the dispatcher's behaviour to stay unchanged. Keeping it costs nothing, since there is one process either way. It also keeps the missing-member notice that makes old vendored copies fail open.
- **Option B (rejected):** Delete the dispatcher too, and register `concept_changed_check.py` directly at Stop.
  - Why rejected: the Changed-file check lives in `scripts/`, so a hooks-folder path rule and the manifest's exec-form rule (`.claude/hooks/<script>`) would both need exceptions. The missing-member fail-open path would be lost. The brief puts the dispatcher's behaviour in scope as "unchanged".
- **Option C (rejected):** Keep the guard file but switch it off (unregistered, or `CLAUDE_PLAIN_LANGUAGE_GUARD=off` by default).
  - Why rejected: the brief rules it out. A file nothing runs also fails manifest INV-8.
- **Option D (rejected):** Drop the guard pair from the finish-install fixture and lower that suite's counts to 15 and 15.
  - Why rejected: that pair is the suite's only case of one file registered twice and told apart by its arguments. The registration-key behaviour still exists. A fictional fixture name keeps the coverage and leaves no live mention of the guard.

---

## Uncertain Assumptions

- `VERIFIED via grep of the worktree`: every live mention of the guard is in the files under Extension Points. No mention exists in `.claude/skills`, `agents/`, `CONTRIBUTING.md`, the root `CLAUDE.md`, `auto_improve_finish_install.py`, `.claude/.project-tokens.json` or `.cursor-plugin/`.
- `VERIFIED via .claude/hooks/hooks.json`: 14 entries today, 13 after (recount listed under Extension Points item 11).
- `VERIFIED via .claude/hooks/plain-language-guard.py:411-418, 541-561`: the guard's state is `state_dir()/plain-language-guard-<session>.json` and its log is `logs_dir()/plain-language-guard.log`. Both live under the project.
- `VERIFIED via enumeration`: "17 enforcement hooks" matches no countable set. On disk there are 15 non-underscore `.py` files in `.claude/hooks`, 5 add-on hooks, and the README counts 14 hook files. So the description takes the README's count after removal: 13.
- `VERIFIED via test_working_agreements.py:418-426, 1788`: the only pinned phrase in the agreement is "no automatic checker" in the element rule. The closing line is not pinned.
- `VERIFIED via a real call, 2026-10-22`: `py -3 <missing file>` exits with code 2 ("can't open file ... No such file or directory"). On prompt submit, Claude Code treats that as a block. The implementer still repeats the call once before wording the README note.
- `VERIFIED via hooks.json:158-162, 171-179 and stop-dispatcher.py:151-155, 187`: since 0.9.8 the guard is registered directly only on prompt submit; at Stop it runs only through the dispatcher, whose missing-member path exits 0.
- `RESOLVED by the user`: version 0.9.12 (Open Question 3).

---

## Failure Modes & Mitigations

- **FM:** A plugin install keeps running the guard after the update.
  - **Mitigation:** none needed. `${CLAUDE_PLUGIN_ROOT}` always names the running version, and hooks are read at session start. The README note says to start a new session.
- **FM:** A vendored install deletes its copy of the guard and keeps its rows. The launcher exits 2 (VERIFIED by one real call on 2026-10-22: `py -3 <missing file>` printed "can't open file" and exited 2). What that blocks depends on which rows the install has:
  - An install registered from 0.9.8 on has ONE guard row, on prompt submit. Every prompt is blocked. Turn ends are not held, because at Stop the guard ran only through the project's own `stop-dispatcher.py`, which treats a missing member as "could not check" and exits 0.
  - An install registered before 0.9.8 also has a direct Stop row for the guard. That row holds every turn end as well.
  - **Mitigation:** the plugin never deletes a project's file. The finish-install script only adds rows. The sync stops with a conflict on a file that exists on one side only, and the obvious way out (deleting the local copy) is the harmful order when the rows stay. So the README removal note gives the safe order in plain words: remove every row that runs the guard from your `settings.json` first (one on prompt submit; installs older than 0.9.8 also have one at turn end), then delete the file and its rules file. Automatic detection is the follow-up stub.
- **FM:** A vendored install keeps its copy and rows. The guard keeps running from the project's copy.
  - **Mitigation:** accepted. It is then the project's own hook, and nothing in the plugin depends on it.
- **FM:** An old vendored `stop-dispatcher.py` still lists the guard after its file is removed.
  - **Mitigation:** the existing missing-member path gives exit 0, one error-log line and one notice per session.
- **FM:** The dispatcher tests silently degrade to one member and stop proving the ordering rules.
  - **Mitigation:** the rewritten `CHECKS` in the test copy, plus a check that the rewrite happened (Extension Points item 4).
- **FM:** The always-kept guarantee is lost while the agreement is edited.
  - **Mitigation:** A3, plus the existing INV-3, INV-6 and S1 rows in `test_working_agreements.py`, which stay green.
- **FM:** A count is missed. "fourteen" and "17" appear in several places.
  - **Mitigation:** the manifest suite (exact table, INV-8, INV-11, INV-12) and the finish-install real-`hooks.json` test fail on any drift. A last search for `plain-language-guard`, `PLAIN_LANGUAGE` and `reads plainly` must match only history files and the README removal note. Each remaining "fourteen" or "17" in the hook documents and suites is checked by hand.

---

## Open Questions for User

- [x] **1. Does "the hook for plain language" mean only the guard? And what replaces the agreement's closing line?** → **Answer (user, 2026-10-22, "approve" of the recommendation):** the guard only; closing line becomes "No automatic checker enforces any of these rules." The brief assumed the guard only, with the agreement kept. Recommendation: yes, the guard only. The closing line "The end-of-turn writing checker catches some of these breaks. It cannot catch the first one." becomes "No automatic checker enforces any of these rules." That is one short true sentence, and it keeps the element rule's existing wording valid. The other choice is to delete the line with no replacement.
- [x] **2. May the README carry one removal note that names `plain-language-guard.py`?** → **Answer (user, 2026-10-22, "approve" of the recommendation):** yes, exactly one short paragraph. The brief's criterion says a search for the name finds only history records. Existing installs need the file name to find their rows. Recommendation: yes. Allow exactly one short "Removed in 0.9.12" paragraph in the README. It names the two rows to delete first, then the file, its rules file and the optional state and log files. The criterion's search excludes that paragraph.
- [x] **3. Version 0.9.12 or 0.10.0?** → **Answer (user, 2026-10-22, "approve" of the recommendation):** 0.9.12 (a patch bump). **Implementation note:** by the time the branch was reviewed, master had moved to 0.9.16, so the patch bump became **0.9.17** (and the README note says "Removed in 0.9.17"). Everywhere this contract says 0.9.12, read 0.9.17. Recommendation: 0.9.12, which matches how this repository has numbered hook changes. Choose 0.10.0 if you want the removal of a gate to stand out as a breaking change.

---

## Critique

**Critic:** contract-critic
**Date:** 2026-10-18
**Verdict:** blockers-found

### Findings

- **[BLOCKER] The broken-install analysis describes registrations that current vendored installs do not have**
  - **What is wrong:** The Failure Modes entry says a vendored install that deletes the guard but keeps its rows "keeps its two rows" and so "every turn end is held". The follow-up stub says the same: "one on prompt submit and one at Stop". Since 0.9.8, the shipped `hooks.json` registers the guard directly only on prompt submit (`.claude/hooks/hooks.json:158-162`). At Stop the guard runs only through `stop-dispatcher.py` (`hooks.json:171-179`; `README.md:138`). So the finish-install script writes ONE guard row for any install made from 0.9.8 on. Its Stop row launches the project's own `stop-dispatcher.py`, and that file treats a missing member as "could not check" and exits 0 (`stop-dispatcher.py:151-155, 187`). Only installs registered before 0.9.8 have a direct Stop row that would hold every turn. The planned README note and the stub would therefore document the wrong guard behaviour for the common case. The prompt-blocking half is right for both.
  - **Prior artifact ignored:** `JOURNAL.md — 2026-10-04 — Check a documented guard behaviour against the guard's code` (line 68). The `py -3 <missing>` probe confirms the exit code but not which rows a given install has.
  - **Where in this contract:** `## Failure Modes & Mitigations` — "A vendored install (rows written by the finish-install script) deletes its copy of the guard and keeps its two rows. The launcher then exits 2: every prompt is blocked and every turn end is held." The same claim is in `.claude/concepts/followups/2026-10-18-warn-on-rows-naming-unshipped-hooks.followup.md:12`.
  - → Addressed by: Failure Modes rewritten by install age (one prompt-submit row from 0.9.8 on; a direct Stop row only before 0.9.8) with the exit code verified by a real call; follow-up stub line corrected the same way.
- **[WARN] The planned new README variable count is wrong**
  - **What is wrong:** The README variable table has eleven rows today, not ten (`README.md:206-216`, which includes `CLAUDE_CONFIG_DIR`). That is eight kill switches plus three others, so the current "Eight of the ten … Two are not" is already false. After row 209 is removed there are ten rows: seven kill switches and three others. The contract's "Seven of the nine" puts a new false count into the README. INV-12 compares only the set of variable names (`test_plugin_manifests.py:441-453`), so no test catches the prose count.
  - **Prior artifact ignored:** `JOURNAL.md — 2026-10-04 — Check a documented guard behaviour against the guard's code` (README drift). The contract's own `## Confidence` says "High on the counts (recounted …)".
  - **Where in this contract:** `## Extension Points` item 11 — "Line 199: "Eight of the ten" becomes "Seven of the nine"."
  - → Addressed by: item 11 now says to recount by hand and write "Seven of the ten ... Three are not".
- **[WARN] Confidence is High while two assumptions are ASSUMED**
  - **What is wrong:** `## Confidence` says "High", but `## Uncertain Assumptions` has two `ASSUMED` entries: the missing-script exit code, and 0.9.12 against 0.10.0.
  - **Prior artifact ignored:** contract-critic checklist item 5 (the verdict must match the uncertainty inventory).
  - **Where in this contract:** `## Confidence` — "Confidence: High." and `## Uncertain Assumptions` — "`ASSUMED`: `py -3 <missing file>` exits with code 2."
  - → Addressed by: the exit code is now verified, the version is resolved by the user, and Confidence is restated as Medium-High with its reasons.
- **[WARN] The reference list misses live text that becomes false, and the closing search would not find all of it**
  - **What is wrong:** The contract says "every hit placed", but these are not listed:
    - The check label in `test_plugin_manifests.py:268` says "at least the six members". It becomes five, and the "fourteen"/"17" search will not catch it.
    - `test_plugin_manifests.py:53` (INV-O1 docstring) and `:550` (section print) both say "fourteen".
    - `test_auto_improve_finish_install.py:1662` has the message "16 hook files, plain-language-guard twice".
  - **Prior artifact ignored:** `JOURNAL.md — 2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures` (line 208). Every suite must be swept, not only the rows already named.
  - **Where in this contract:** `## Extension Points` items 9 and 10; `## Confidence` — "High on the reference inventory (a repository-wide search, every hit placed)."
  - → Addressed by: the four spots are added to items 9 and 10; Confidence no longer claims a complete inventory.
- **[WARN] The final search will not catch the spelling with a space, "plain-language guard"**
  - **What is wrong:** The TASK block searches only `plain-language-guard`, `PLAIN_LANGUAGE_GUARD`, `carry-forward` and "reads plainly". Live prose uses "plain-language guard" (with a space) at `hooks.json:27`, `stop-dispatcher.py:5` and `:21`, `README.md:505` and `test_stop_dispatcher.py:187`. The agreement's "writing checker" wording is also missed. A missed edit at any of these still claims the guard exists, and the search would not flag it.
  - **Prior artifact ignored:** `.claude/work-items/2026-10-18-remove-plain-language-hook.md:40`: "`README.md`, `MECHANISMS.md` and `VOCABULARY.md` carry no claim that the guard exists."
  - **Where in this contract:** `## Implementation Handoff` TASK block — "Final search for plain-language-guard, PLAIN_LANGUAGE_GUARD, carry-forward and "reads plainly"".
  - → Addressed by: the TASK block's final search is now case-insensitive and adds "plain-language guard" (with a space) and "writing checker".
- **[WARN] The contract treats the sync report as harmless, but it leads to the harmful order**
  - **What is wrong:** By the registry entry, the sync tool now reports a file on only one side as a conflict, and the run stops with exit 2. The developer has to resolve it before the sync can finish, and the obvious fix is to delete the local guard copy. If the rows stay, that delete produces the prompt-blocking install described in the first finding. The contract presents `ONLY_IN_MAIN` as "not deleted" and leaves the safe order to a README note that the sync never shows. The sync configuration does not exist in this repository, so the contract cannot verify which trees carry the guard or its test file.
  - **Prior artifact ignored:** `MECHANISMS.md:46` (Bidirectional sync: "exits 2 … a one-sided file is reported as `ONLY_IN_MAIN`"); `JOURNAL.md — 2026-10-04 — Detect an install mode by what the sync actually delivers` (line 61).
  - **Where in this contract:** `## Reused Mechanisms` — "gets an `ONLY_IN_MAIN` report and is not deleted. That is the basis for the "existing install" answer below."
  - → Addressed by: Reused Mechanisms and Failure Modes no longer call the sync report harmless, and the README note carries the safe order (rows first, then the file). The sync configuration itself is outside this repository; that gap is stated in the contract.
- **[NIT] An old vendored dispatcher would show a misleading notice** — When the guard file is missing, an old `stop-dispatcher.py` that still lists it prints "Files a shell command wrote were not checked against a contract" (`stop-dispatcher.py:171-172`). In fact the Changed-file check did run. The contract counts this path as fully mitigated.
- **[NIT] Only half of the superseded follow-up is moot** — `2026-10-05-plain-language-guard-names-a-person.followup.md:20` asks for two things. Replacing the person's name dies with the guard. Extending the genericity scan to cover the user-facing strings of every hook source does not. Renaming the stub to `.superseded` drops the second part with no record of it.
- **[NIT] The Adjacent Areas text is not the sanctioned exception line** — It reads "the cross-area scan was **not run**" rather than the exact sanctioned sentence. No defect follows, because `.claude/area-mapping.json:14` declares `"areas": {}`, so no non-fallback area can be derived.
- **[NIT] The hooks.json delete range is off by one line** — The prompt-submit entry spans `hooks.json:158-162`, opening brace included, and its trailing comma is on 162. Item 1 says "lines 159-162". → Addressed by: item 1 corrected to 158-162.

NIT responses (user answered "approve" to the recommendation to fix the findings and approve):
- Misleading notice from an old vendored dispatcher: → Deferred: it belongs to the same follow-up as the rows-naming-an-unshipped-hook check; noted in that stub.
- Half of the 2026-10-05 follow-up still stands (extend the genericity scan to every hook's user-facing text): → Addressed by: the superseded rename adds a line saying that part is NOT moot and is carried to the new follow-up stub.
- Adjacent Areas wording: → Rejected: no defect follows (`area-mapping.json` declares no areas).

### Applicable journal entries

- **2026-10-04 — Check a documented guard behaviour against the guard's code**: violated, see the first BLOCKER. The exit-code probe is planned, but which rows each install has is not verified.
- **2026-10-04 — Detect an install mode by what the sync actually delivers**: not addressed. The contract reasons about the sync's behaviour without the sync configuration, which this repository does not hold (see the sync WARN).
- **2026-10-05 — Text delivered to the model must say which rule wins against a skill's gate**: heeded by A1 and the unchanged opening paragraph. The new closing sentence adds no instruction.
- **2026-10-05 — Do not add shared state to stop a duplicate the install tool already refuses**: heeded by L2, which adds no cleanup marker.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures**: heeded by Extension Points items 4, 5, 9 and 10, which replace the fixtures instead of weakening rows. The sweep has the gaps listed in the reference-list WARN.
- **2026-10-05 — A size budget must bound the summary it adds / Count a host's size cap the way the host counts**: not addressed. The contract did not need to, because the agreement text only gets shorter and the size logic is untouched (A3).

### What the critic did not check

- `.claude/.scout-cache/registry-digest.md` does not exist in the worktree, and the registries have no per-domain project-tier files. Only the Universal tiers of MECHANISMS, VOCABULARY and JOURNAL were applied.
- INTEGRATION.md was not consulted. The contract has no API, SignalR or DTO surface, so checklist items 7 and 12 have nothing to match.
- `.claude/north-stars/` does not exist, so checklist item 13 produced no findings.
- The real exit code of `py -3 <missing file>` was not run. The critic has no shell.

---

## Lessons referenced

- **2026-10-04 — Check a documented guard behaviour against the guard's code**: heeded by the README removal note. The exit-2 claim must be checked with one real call before it is written (Uncertain Assumptions). The README's registration arithmetic is also corrected, not just changed by one. Cross-reference: JOURNAL.md § Universal lessons.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures**: heeded by searching every suite that runs or names the guard as a fixture (the dispatcher identity rows, the project-first data-file section, the finish-install fixture, the manifest controls). Each is replaced, not left to fail.
- **2026-10-05 — Text delivered to the model must say which rule wins against a skill's gate**: checked. The agreement's precedence lives in the hook's fixed opening paragraph, which is unchanged. The new closing sentence adds no instruction.
- **2026-10-05 — Do not add shared state to stop a duplicate the install tool already refuses**: heeded by adding no marker or cleanup state for leftover files (L2).
- Orthogonal to north-stars: none. The register holds no active thought, which confirms the brief's `north_stars: none`.

---

## Implementation Handoff

### 1. Remove the guard, its registrations, tests and docs (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/hooks/hooks.json`
- `.claude/hooks/stop-dispatcher.py`
- `.claude/hooks/plain-language-guard.py`
- `.claude/hooks/plain-language-guard.rules.json`
- `.claude/hooks/db-destructive-guard.py`
- `.claude/hooks/tests/test_plain_language_guard.py`
- `.claude/hooks/tests/test_stop_dispatcher.py`
- `.claude/hooks/tests/test_hook_data_files_project_first.py`
- `.claude/hooks/tests/test_working_agreements.py`
- `.claude/agreements/plain-language.md`
- `.claude/scripts/tests/test_plugin_manifests.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/VOCABULARY.md`
- `.claude/concepts/followups/2026-10-05-plain-language-guard-names-a-person.followup.md`
- `.claude/concepts/followups/2026-10-05-plain-language-guard-names-a-person.followup.superseded.md`
- `README.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `.cursor-plugin/plugin.json`

**Pre-written TASK block:**
```
TASK: Remove the plain-language guard from the plugin: its file, rules file, test suite, both
      registrations and every list, count and document that names it. Keep the Stop dispatcher
      with the Changed-file check as its only member, and keep the plain-language agreement
      (only its closing line changes).
CONTEXT: concept contract at .claude/concepts/2026-10-18-remove-plain-language-hook.md
         brief .claude/work-items/2026-10-18-remove-plain-language-hook.md
FILES: the Files to touch list above
CONSTRAINTS:
  - Follow Extension Points items 1-14 exactly; the invariants R1-R5, S1-S3, F1-F2, G1, A1-A3,
    L1-L3 are authoritative. Use the Open Question answers recorded in the contract.
  - TESTS FIRST: change the four affected suites (stop dispatcher, project-first data files,
    manifests, finish-install) and add the working-agreements row, run them against the
    UNCHANGED tree and record which fail (RED). Then make the production change (GREEN).
  - stop-dispatcher.py: only the CHECKS literal, docstring and comments change. The multi-member
    rows run on a test copy whose CHECKS literal is rewritten, with an assertion that the rewrite
    happened; never weaken a row's assertion.
  - Before writing the README removal note, run `py -3 <a path that does not exist>` once and
    record the exit code; word the warning to match what you saw.
  - The follow-up rename is a git mv plus one added "Superseded by:" line, and a second line saying
    that only the guard-specific part is moot while the request to extend the genericity scan to
    every hook's user-facing text moves to the new follow-up stub; no other edit.
  - Version 0.9.11 -> 0.9.12 (or the Open Question 3 answer) in all five declarations.
  - Run green and report exit codes: .claude/hooks/tests/test_stop_dispatcher.py,
    test_hook_data_files_project_first.py, test_working_agreements.py,
    .claude/scripts/tests/test_plugin_manifests.py, test_auto_improve_finish_install.py,
    test_plugin_doctor.py, test_check_version_bump.py. Also run test_changed_file_check.py
    and report its result without changing it.
  - Final search (case-insensitive) for plain-language-guard, "plain-language guard" (with a
    space), PLAIN_LANGUAGE_GUARD, carry-forward, "reads plainly" and "writing checker": every remaining hit must be under .claude/concepts/, .claude/work-items/, or the
    single README removal note. Also search "fourteen" and "17" in README, hooks.json, the
    manifests and the two test suites, and fix or justify each hit as a hook count or not.
    Paste the search output in your report.
  - Do not touch auto_improve_finish_install.py, working-agreements.py, concept_changed_check.py
    or any past contract. Do not invent new data shapes; the contract is authoritative.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-18-remove-plain-language-hook.md
  contract_status: approved
```

### 2. Scope note on review

There is no separate review sub-task. The ordinary `/ship` review applies. The reviewer checks these points:
- The Stop dispatcher's diff touches only `CHECKS`, docstring and comments.
- The multi-member rows still prove the ordering rules through the rewritten test copy.
- The RED list was recorded before GREEN.
- The final search output matches the contract's allowance.

After the merge, nothing needs promoting to the registries beyond the two in-place edits in item 12.

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
