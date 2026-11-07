# Review: 2026-11-06-session-folder-owner-and-tool-named (fullstack-code-reviewer)

**Contract:** `.claude/concepts/2026-11-06-session-folder-owner-and-tool-named.md` (approved)
**Branch:** `fix/271-session-folder-owner-and-tool-named` (uncommitted diff against `c8653e3`)
**Scope:** Python hooks, installer, bridge, helper, manifests, docs, registries. There is no C# or Angular code in this change, so those checklists do not apply.

## What I checked

- I read the full guard, tracker and reset diffs, plus the installer, the bridge, the helper, `addon.json`, `hooks.json`, the five version entries, the three skills, the README, the decision table and the registry diffs.
- I compared the shared blocks of the three hooks with an AST check. These are byte-identical in all three hooks: `_remote_host`, `_own_spellings`, `session_parent_base`, `_base_shown`, `_create_parent`, `resolve_session_parent`, `session_folder_problem`, `PARENT_NAME`, `PARENT_PROBLEMS`, `_LOCAL_DEVICE_HOST_RE`, `_REPARSE_POINT` and `SESSION_PREFIX`. `_is_link_stat` differs only in its docstring; the code is the same.
- I recomputed `released_sha256` with the installer's `_fold_text_bytes` on the `e4f392c` copies of the three hooks. The guard (`8c44ed60…`), reset (`900db4ad…`) and tracker (`7e2daa3a…`) hashes all match `addon.json`. Nothing under `.claude/addons/codegraph/hooks/` changed between `e4f392c` and HEAD, so those copies really are the 0.15.2 copies.
- I ran the suites:
  - `test_codegraph_first_guard.py`: 838 passed, 0 failed, 2 skipped. Both isolation checks passed (the real temp folder and the real per-user parent).
  - `test_addons.py`: OK.
  - `test_worktree_path_guards.py`: 190 of 190 passed.
  - `test_plugin_manifests.py`: 191 passed.
  - `test_installed_plugin_root.py`: 18 OK.
  - `test_codegraph_session_parent_docs.py`: 14 OK.
- I ran the contract's re-grep list over README, skills, references, addons, hooks, scripts and registries (results in "Re-grep dispositions" below).
- Statelessness: once `problem` is set, `ensure_folder`, `has_plain_file`, `read_json`, `write` and `create_once` all return before any filesystem call. `announce()` returns after the stderr line and before any flag or log call. `marker_cause` / `note_foreign_marker` run only after `turn-marker-present`, which needs a usable verdict. The ticket `os.remove` runs only after `has_plain_file` is True. Step 8 re-resolves the verdict after a failed write and never allows. The tracker returns before writing anything. The reset hook exits before deleting or pruning anything and still removes the legacy sentinel. Statelessness holds.
- I-4: the verdict functions catch `Exception` (giving `check-failed` / `session-check-failed`), and `ensure_folder` now catches `Exception`. The catch-all in `__main__` is reachable only from code outside the folder check (for example `block()`'s own print or `log_event`, both unchanged in kind). I-4 holds as scoped.
- Hop proof: the guard (`_pp_has_hop_refusal`), the bridge (`TREE_HOP_REFUSAL`) and the installer (`getattr(api, "TREE_HOP_REFUSAL", False) is not True`) all use the contract's expression. `WORKTREE_OWN_ROOT_NATIVE` is gone from code and from `__all__`.
- Version: 0.15.3 in `plugin.json`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json` and both entries of `.claude-plugin/marketplace.json`. `check_version_bump.py` reports "no shipped plugin file changed". That is expected, because the diff is uncommitted. Re-run it after the commit.

---

### `.claude/addons/codegraph/hooks/codegraph-first-guard.py` and the shipped E1 sentence (10 doc sites)

**[WARN]: The "repeat after `retry-ticket-unwritten`" sentence names the wrong reason for unknown-class calls** (guard line 1150-1151; README x3, install SKILL x3, uninstall SKILL:142, decision table:131, VOCABULARY.md:124, MECHANISMS.md:106)
```
"Repeat this exact call: the guard tries again to record the retry. When that works the block says",
"`source-target`, and the identical call after it is allowed.",
```
**Problem**: In step 8, a successful ticket write gives `source-target` only when a target is of the source class. A Grep with only a pattern, or a generic Glob such as `**/*`, gets `ambiguous-target`. The banner and E1 ("blocked once more (as `source-target`)") are false for those calls. The contract's own E1 / I-7b text has the same defect, and the implementation copied it faithfully. That makes it a contract defect (JOURNAL entry appended). It breaks the 2026-10-28 rule that guard messages must use names the guard emits.
```
"Repeat this exact call: the guard tries again to record the retry. When that works the block says",
"`source-target` (or `ambiguous-target`), and the identical call after it is allowed.",
```
Apply the same change to E1 at every site: "...so the repeat is blocked once more (as `source-target` or `ambiguous-target`) and the identical call after it is allowed." Then update `E1_TAIL` in `test_codegraph_session_parent_docs.py` if it pins the old text.

---

**[INFO]: `Session.path()` on a stateless session returns a cwd-relative name** (line 466-467)
```
def path(self, name: str) -> str:
    return os.path.join(self.folder, name)   # folder == "" while problem is set
```
**Problem**: Every current caller is gated behind `has_plain_file` or a usable verdict, so nothing escapes today. A future caller that uses `path()` without the gate would act on `<cwd>/turn.json`. You could make the stateless contract structural, for example by returning `os.devnull`-style junk or raising when `self.problem is not None`. Optional.

**[INFO]: A `check-failed` raised before `parent` is assigned shows an empty path** (`resolve_session_parent`, the `parent = ""` default)
The banner then reads `Problem:   -- the folder could not be checked (check-failed): ...`. An exception raised in `session_parent_base` (in `realpath`) is the only way in. You could fall back to `_base_shown(os.environ, os.name)` when `parent` is empty.

---

### `.claude/hooks/tests/test_codegraph_first_guard.py`

**[WARN]: The hook-parity row pins only `session_parent_base`; the fail-closed checks are unpinned** (line 2578-2614)
```
for label, os_name, env, want_problem, want_base, realmap in rule_rows():
    ... fn = getattr(mod, "session_parent_base", None)
```
**Problem**: The owner, mode, link and writability checks (`resolve_session_parent`, `_create_parent`, `session_folder_problem`) are the security core of I-6. Their three copies are byte-identical today (I checked with AST), but no row would catch drift. A tracker copy that stops checking `open-mode` would write markers into a folder the guard refuses. A reset copy that stops checking `link` would prune through a link. The contract asked for "the Parent base rule and the problem set", and that is met in letter. In spirit, the contract also said "the inline copies drift apart → a parity row". The cheapest fix is an AST source-segment equality row:
```
for fn_name in ("session_parent_base", "_base_shown", "_create_parent", "resolve_session_parent",
                "session_folder_problem", "_remote_host", "_own_spellings"):
    segs = {name: _fn_source(path, fn_name) for name, path in hooks}
    check(f"Q-parity: {fn_name} is textually identical in the three hooks", len(set(segs.values())) == 1, ...)
```

---

### `skills/auto-improve-codegraph-install/SKILL.md`

**[WARN]: The upgrade paragraph still says "from before 0.15.2"** (line 158)
```
**Upgrading an install from before 0.15.2.** The old hook files differ from the new ones, so this skill refuses with `addon-file-differs`.
```
**Problem**: A 0.15.2 install now also refuses with `addon-file-differs`, because its three hook files differ from 0.15.3. The README's 0.15.3 block gives the route, but the skill the user actually runs reads as though a 0.15.2 project needs nothing. The contract did not list this line, so the re-grep missed it.
```
**Upgrading an install from before 0.15.3.** The old hook files differ from the new ones, so this skill refuses with `addon-file-differs`. ...
```

---

### `.claude/registries/MECHANISMS.md`, `.claude/registries/VOCABULARY.md`, `README.md`

**[INFO]: The span edit left a grammar break** (MECHANISMS.md:106)
`The codegraph add-on's guard is fails open only on proof:` should read `The codegraph add-on's guard fails open only on proof:`. Applying the contract's span replacement literally produced "is fails".

**[INFO]: A sentence starts in lowercase** (VOCABULARY.md:125)
`... carries a non-empty agent_id). an unusable session folder is not a reason ...`: capitalise "An".

**[INFO]: E2 has no referent in the 0.15.3 "It fails closed" bullet** (README.md around line 320)
"While the session folder cannot be used, these lines print on every call and nothing is logged." follows a sentence about the retry, so "these lines" points at nothing. The contract did not list this site for E2. Either drop it there or write "the `allowed (fail-open:<reason>)` lines print on every call".

---

### Contract alignment

- **Data Shapes:** they match. The Parent base rule reads only the mapping. Parent creation is one level and never uses `makedirs`. The problem set is closed and matches the contract. The marker is stamped `{writer, session}`. The flag is `logged-foreign-marker`. The Stateless session matches. `TREE_HOP_REFUSAL` and the Hop proof match. The refusal message is one line per finding, in the contract's shape. The decision order is 1-8, as amended. One addition: a `Session` that was never resolved defaults to `problem="check-failed"` (stateless). That is a harmless, stricter default.
- **Reused Mechanisms:** `_remote_host` / `_own_spellings` are reused verbatim (six copies, W-14 rows updated). `_hop_allowed` stays at four copies. The pruner is unchanged apart from its root argument.
- **Files to touch:** one file is outside the list: the untracked `.claude/scripts/tests/test_codegraph_session_parent_docs.py` (a wording test for the shipped-text list). It is under `.claude/` and test-only. [WARN] Add it to the contract's Files to touch, or name it in the PR as a test-only addition.
- **Off-area drift:** none. `derive_area.py` returns `uncategorized` (the area map is empty), and `## Adjacent Areas` is not applicable.
- **End-User View:** not applicable (no Angular surface).
- **Re-grep dispositions:**
  - Fixed:
    - every `state-unwritable` hit is now history in the 0.15.3 README text;
    - `nudge` remains only in the angular-tailwind and plan-question advisors, which are unrelated;
    - `WORKTREE_OWN_ROOT_NATIVE` appears only in the README's "replaces" sentence;
    - `gettempdir` has no call in the three codegraph hooks.
  - Out of scope:
    - `_project_paths.py:949-952`, `stop-dispatcher.py:168`, `concept_changed_check.py:159` and `integration-check.py:41` keep session state in the system temp folder.
    - **[INFO / follow-up question]** These carry the same cross-user plant class on Windows (a shared `TMP` lets another user plant state keyed by the victim's session id). They are outside #271, but worth an issue.
- **Registries:**
  - No new reusable mechanism: the contract says "None", and I agree. The parent rule is a location rule inside the session-keyed-marker pattern.
  - VOCABULARY already carries "Per-user session parent" and "Foreign marker" plus the dated correction.
  - INTEGRATION.md: no REST, SignalR or DTO surface, so nothing to update.
  - JOURNAL.md: I appended one entry (the E1 contract defect, `Trigger: post-impl divergence`).

---

### Summary

| Severity | Count |
|---|---|
| [CRITICAL] | 0 |
| [WARN] | 4 |
| [INFO] | 6 |

**Verdict**: `FIX THEN SHIP`

**Top priority fix**: Correct the `retry-ticket-unwritten` banner and the E1 sentence. They promise `source-target`, but an unknown-class call (a pattern-only Grep, a generic Glob) gets `ambiguous-target`.

### HANDOFF
- **Status:** has-issues
- **Files reviewed:** the 26 files in `git diff --stat`, plus the untracked `.claude/scripts/tests/test_codegraph_session_parent_docs.py`.
- **Issues to fix:**
  - [WARN] `codegraph-first-guard.py:1150-1151` and the 10 E1 doc sites name `source-target` only; add `ambiguous-target`.
  - [WARN] `test_codegraph_first_guard.py:2578` has no textual parity row for `resolve_session_parent` / `_create_parent` / `session_folder_problem` / `_base_shown`.
  - [WARN] `skills/auto-improve-codegraph-install/SKILL.md:158` says "before 0.15.2"; it should say "before 0.15.3".
  - [WARN] Contract Files to touch omits `test_codegraph_session_parent_docs.py`.
- **Safe to test:** yes
- **Warnings:**
  - The other system-temp session markers (`_project_paths.session_marker`, `stop-dispatcher`, `concept_changed_check`, `integration-check`) have the same cross-user plant class. That is a follow-up, not this PR.
  - `check_version_bump.py` must be re-run after the commit.
- **Context for next agent:** the stateless path and I-4 scoping are sound. The remaining risk is drift between the three inline copies and message wording.
- **Recommended next:** back-to-implementer
- **Suggested input for next agent:**
  TASK: Fix the 4 WARNs above (E1/banner ambiguous-target wording at the guard and 10 doc sites; add AST textual parity row for the shared verdict functions; install SKILL:158 "before 0.15.3"; note the docs test file in the PR/contract), plus the INFO grammar fixes in MECHANISMS.md:106 and VOCABULARY.md:125.
  FILES: .claude/addons/codegraph/hooks/codegraph-first-guard.py, README.md, skills/auto-improve-codegraph-install/SKILL.md, skills/auto-improve-codegraph-uninstall/SKILL.md, .claude/references/codegraph-decision-table.md, .claude/registries/VOCABULARY.md, .claude/registries/MECHANISMS.md, .claude/hooks/tests/test_codegraph_first_guard.py, .claude/scripts/tests/test_codegraph_session_parent_docs.py
  FOCUS: a retry-ticket-unwritten row with a pattern-only Grep asserting the repeat gives ambiguous-target; parity row fails when one copy is edited.

```yaml
findings:
  - id: F1
    severity: Soft
    file: .claude/addons/codegraph/hooks/codegraph-first-guard.py:1150
    description: E1 / I-7b promise source-target; unknown-class calls get ambiguous-target.
    proposed_feedback_rule:
      name: feedback_message_predicts_every_reason.md
      body: |
        A message or doc sentence that predicts the block reason of a later call must name every reason that branch can return.
        **Why:** E1 in #271 said "as source-target" at 10 sites while step 8 also gives ambiguous-target.
        **How to apply:** before writing "the next call gives X", read the branch that picks X and list all its return values, or describe the outcome without the reason name.
  - id: F2
    severity: Soft
    file: .claude/hooks/tests/test_codegraph_first_guard.py:2578
    description: Hook parity pins only session_parent_base behaviourally; the fail-closed verdict functions can drift silently.
    no_rule_needed:
      reason: The class "inline copies must be pinned by a parity row" is already a standing rule; this is a coverage gap in applying it, fixed by extending the existing Q-parity row.
      existing_rule: .claude/registries/MECHANISMS.md (Same-host path rule, "each set is pinned by a parity row")
  - id: F3
    severity: Soft
    file: skills/auto-improve-codegraph-install/SKILL.md:158
    description: Upgrade paragraph still scoped to "before 0.15.2" though 0.15.2 installs now also refuse addon-file-differs.
    no_rule_needed:
      reason: Covered by the JOURNAL 2026-10-22 lesson "Describe a broken install by the rows each install age really has"; the miss was the contract's shipped-text list, not a new class.
      existing_rule: .claude/registries/JOURNAL.md (2026-10-22 entry)
  - id: F4
    severity: Safe
    file: .claude/concepts/2026-11-06-session-folder-owner-and-tool-named.md (Files to touch)
    description: New test file test_codegraph_session_parent_docs.py not listed.
    no_rule_needed:
      reason: The existing reviewer Files-to-touch audit caught it; it is a test-only addition under .claude/ that enforces the contract's own re-grep list.
      existing_rule: .claude/agents fullstack-code-reviewer contract alignment checklist
```
