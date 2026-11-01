# Concept Contract — Follow-ups from the angular-tailwind rule documents contract

**Project:** claude-agentic-auto-improve
**Date:** 2026-10-30 (revision 4, final draft)
**Requested by:** user
**Status:** implemented
**Implemented:** 2026-11-01, automatically, by pr_merged.py after https://github.com/lneninger/claude-agentic-auto-improve/pull/127, https://github.com/lneninger/claude-agentic-auto-improve/pull/129, https://github.com/lneninger/claude-agentic-auto-improve/pull/131, https://github.com/lneninger/claude-agentic-auto-improve/pull/133, https://github.com/lneninger/claude-agentic-auto-improve/pull/135, https://github.com/lneninger/claude-agentic-auto-improve/pull/137, https://github.com/lneninger/claude-agentic-auto-improve/pull/138, https://github.com/lneninger/claude-agentic-auto-improve/pull/139, https://github.com/lneninger/claude-agentic-auto-improve/pull/140, https://github.com/lneninger/claude-agentic-auto-improve/pull/141, https://github.com/lneninger/claude-agentic-auto-improve/pull/144; 3 checklist items from review reports, 0 with no structured evidence; not performed (disclosed on #86): Implementation matches Data Shapes exactly; owner confirmed resolved: none
**Supersedes:** none
**Work Item Brief:** .claude/work-items/2026-10-30-86-angular-tailwind-followups.md
**Tracking issue:** #86
**Budget:** 12,000 tokens
**Amended:** 2026-10-31 by user approval ("resume 86"): Rule V and the version files of every block

---

## Business Concept

- **What is this thing, in domain language?**
  This contract delivers the six groups of work that the parent contract (`.claude/concepts/2026-10-28-angular-tailwind-rule-documents.md`) left open. Its stub is `.claude/concepts/followups/2026-10-28-angular-tailwind-deferred-items.followup.md`.
  - **Guard weak spots:** each is fixed, recorded as an accepted guard limit, or recorded as already resolved.
  - **Kill switches:** the add-on environment switches are removed (Q1 = B).
  - **Advisor keyword:** the dead `ui` keyword stays documented.
  - **Doctor and preload:** the doctor compares add-on documents and reports a disabled add-on hook that is still installed. `python-ai-developer` stops preloading a missing skill.
  - **Candidate patterns:** table column alignment ships as P-002; the other three are rejected (Q2).
  - **Rules route:** the `.claude/rules/` route is tried live and recorded.

- **Existing VOCABULARY.md terms that apply:** Vendored-asset drift, Placeholder slot. Guard rules file, Project profile and Two-layer Claude path resolution are MECHANISMS.md entries.
- **New terms and amendments:** their exact text is in `## Registry appends`. Sub-task t8 appends it only after the facts it states have merged.

---

## End-User View

Not applicable. Reason: the plugin has no product screens. `Files to touch` holds no Angular component, template, stylesheet, state service, route or layout. The `.md` rule documents only describe Angular code.

---

## Data Shapes

### Entities

| Name | Fields | Invariants | Ownership |
|---|---|---|---|
| Guard weak-spot ledger | id; weak spot; disposition (`fixed` / `accepted` / `already-resolved`); evidence | G-0: every weak spot in the brief, plus W11, has exactly one disposition. W6 is split into W6a and W6b. Every `accepted` row has a "Known limits" line in the guard's docstring and a test that pins it | this contract; the docstring is its shipped copy |
| Add-on manifest (consumed) | `kill_switches` | K-1: no shipped add-on has the key | the add-on folder |
| Drift finding (extended) | `kind` gains `disabled-hook-installed`; `path`; `owner` | D-1: the set of kinds stays closed. D-2: one finding per (kind, path) | `plugin_doctor.py` |

### Guard weak-spot ledger

| # | Weak spot | Disposition | Rule, evidence and sub-task |
|---|---|---|---|
| W1 | Hard-coded `projects` folder | fixed | G-1, t2 |
| W2 | `/ClientApp/` and `/features/` | already-resolved | Not in the guard (grep, 2026-10-30). t2 pins their absence |
| W3 | Only `*.component.*` files are scanned | fixed | G-2, t2. The Angular 20 reading is confirmed by the user |
| W4 | The hex regex matches `#add` | fixed | G-5, t1. The residue is a pinned limit |
| W5 | `relative` and `absolute` are never checked | accepted | Settled by the parent's Q13. t1 pins that they are allowed |
| W6a | Multi-edit gap: whole-file rules see only a fragment | fixed | G-4: judged once per file on the post-edit view. t1 |
| W6b | Multi-edit gap: a line violation split across two edits | accepted | Closing it needs a line diff. t1 pins that two edits forming `text-gray-500` pass |
| W7 | The height chain sees only the fragment | fixed | G-4, t1 |
| W8 | Stylesheet rules only warn | accepted | The nesting check works one line at a time (`architecture-guard.py:846-930`). t1 pins exit 0 |
| W9 | Stale pointers to the home hooks folder | fixed | G-3, t2 |
| W10 | A design document cites a missing path | already-resolved | Every repository path cited in the shipped design documents resolves (grep, 2026-10-30). `foundation.md:47` is a removal note. The weak spot named the consuming project's document, which is step 3 of issue #84. t2 pins this |
| W11 | An edit completes a violation that started on disk | accepted | Closing it needs a line diff. Judging every touched line would block unrelated edits. t1 pins that it passes |

**Rules:**

- **G-1.** `load_app_rules` finds `<frontend_projects_root>/<app>/.app-rules.json` using the root that `detect_app` uses. That root can have more than one segment. Today `:232` compares against a literal folder name instead.
  - Controls: the rules file renamed away; the root `"apps"`; a two-segment root.
- **G-2.** File recognition (t2, after t1). The Angular evidence is the guard's own pattern, `@Component\s*\(` (`architecture-guard.py:456-457`).
  - A **template** is `*.component.html`, or `<stem>.html` whose sibling `<stem>.ts` on disk matches the pattern.
  - A **component stylesheet** is `*.component.scss`, or a `<stem>.scss` or `<stem>.css` with that same kind of sibling.
  - **Component code** is `*.component.ts`, or a `.ts` file (never `.spec.ts` or `.d.ts`) whose post-edit view matches the pattern. When the view is unavailable, the written text is used instead.
  - `classify_sibling_component` derives the stem by removing the actual suffix (`.component.scss`, `.scss` or `.css`). Today it cuts `len(".scss")` (`:763`). It reads `<stem>.component.ts` first, then `<stem>.ts`. A test covers `.css`.
  - Accepted limit, pinned: a suffix-less file is not scanned while its `.ts` does not yet match the pattern.
- **G-3.** No code path in the guard builds a home-folder path.
  - Without `_project_paths`, the fallback at `:52-59` is the hook's own folder.
  - The docstring may say exactly one thing about the home folder. It describes `hook_file`'s order (`_project_paths.py:122-140`): the project copy, then the template beside the hook, then `claude_roots()`, which ends at the home `.claude` (`:81`).
  - t2's test asserts two things: no `Path.home` call and no `HOME` name in the guard's code (checked with `ast`, docstrings excluded); and no `~/.claude` in any string other than that one docstring sentence.
  - `promote-ui-rule/SKILL.md`: `:58` names the project copy. `:72` runs the guard through a lookup block that tries the plugin root first, then the project's `.claude/hooks/`, and halts naming both paths when neither exists.
- **G-4. Post-edit view.**
  - **Construction:**
    - The disk text is read as UTF-8. CRLF is folded to LF in the disk text, in `old_string` and in `new_string`.
    - For an Edit, `old_string` must occur exactly once, unless `replace_all` is set.
    - For a MultiEdit, the edits apply in order, and one view is built per file per call.
    - Reasons the view is unavailable: `file-unreadable`, `not-utf8`, `old-string-missing`, `old-string-ambiguous`, `builder-error`.
  - **Line rules** judge each edit's new text: `inline-style`, `gray-utility:`, `hex-color`, `scroll-edge`, `app-banned-class:` and `external:<id>`. The external rules from the rules file match line by line (`:142-192`).
  - **Whole-file rules** run once per file per call: `height-chain-warn:`, `inline-component-template` and `inline-component-styles`.
    - `height-chain-warn:` uses the view when there is one.
    - The two inline rules block when any edit's new text has the pattern (as today), or when the view has it and the disk text did not.
    - Without a view, all three are judged on each edit's text, as today.
    - A rule that fires twice on the same line is reported once.
  - A Write keeps today's behaviour.
- **V-2. Fail closed.** Each new step catches its own exceptions and falls back to the stricter or the earlier outcome.

  | Step | Fallback when it raises |
  |---|---|
  | the view builder | the view is unavailable |
  | G-1's root walk | the walk uses the default root `projects` |
  | G-2's checks | the file counts as recognised |
  | G-5's reference test | the token is a colour |
  | the per-call whole-file pass | each fragment is judged as today |
  | the view-against-disk comparison | it counts as "introduced" |
  | de-duplication | every finding is printed |

  - Each step has a test that forces it to raise while the text carries a violation that blocks today; the test expects exit 2.
  - With these fallbacks, no new code path reaches the outer catch at `:1164-1171`.
- **G-5.** `hex-color` skips a `#` token that is a template reference variable. All four conditions must hold:
  1. whitespace or the start of the line comes before it;
  2. there is an even number of `"` and of `'` between the last `<` before the token (or the start of the line) and the token;
  3. whitespace, `>`, `/`, `=` or the end of the line comes after it;
  4. the hex run holds no digit.

  Tests:
  - allowed: `<input #add>`, `<mat-menu #bed="matMenu">`, the line `  #facade`;
  - blocked: `fill="#add"`, `[style.color]="'#abc'"`, `<span class="x">#ff0000</span>`, the line `  #ff0000`, `style="color:#fff"`.

  Accepted limit, pinned: a 3- or 6-character token with no digit in that position, such as `  #fff`.

### Value Objects

| Name | Fields | Used as |
|---|---|---|
| Post-edit view | path; text, or `unavailable`; source (`write-content` / `disk-plus-edits`); reason. V-1: `reason` is present exactly when the text is `unavailable` | the input of the whole-file rules |
| Document comparison pair | `<project>/.claude/references/<add-on>/<doc>` ↔ `<plugin>/.claude/addons/<add-on>/documents/<doc>` | D-4 |
| Pattern decision | candidate; `ship` (with a P ID) or `reject` (with a reason) | t6 |
| Route trial record | date; host version; install mode; the frontmatter used; three yes/no outcomes (loads in the main session; loads only on a matching path; reaches a subagent); commands with exit codes; when it loads, as observed | `.claude/references/claude-rules-route-trial.md` (shipped) |

### Kill-switch removal (Q1 = B)

- **K-1.** `codegraph/addon.json` and `strict-shell-gate/addon.json` drop `kill_switches`. The install keeps emitting `kill-switches` in its plan, as an empty list (`auto_improve_finish_install.py:2410,2921`).
- **K-2.** None of `CLAUDE_SKIP_CG`, `CLAUDE_BASH_GATE` or `CLAUDE_CONCEPT_GATE` appears anywhere in the text of any add-on hook file, and the `env_vars_read_by` scan of the add-on hooks finds none of them. A planted `os.environ.get("CLAUDE_SKIP_CG")` is caught by both checks.
- **K-3.** `concept-gate.py` still reads `CLAUDE_CONCEPT_GATE`, and a test checks it. **`CLAUDE_CONCEPT_GATE=off` no longer turns off the strict-shell-gate add-on.** Today it does (`bash-gate.py:440`). t3's pull request body and the release note both say so.
- **K-4. Ways out, per hook.** In normal operation, the uninstall skill is the way out.
  - A t3 test runs the strict-shell-gate uninstall's lookup block, preview and `--apply` through `bash-gate.py` in a project with no contract, and all three are allowed. That works because `--apply` writes through Python, so `parse_redirect_targets` finds no target.
  - When a hook cannot run, its row must come out of `.claude/settings.json` by hand. The route depends on which hook fails:

  | Failure | What the user sees | Route |
  |---|---|---|
  | `bash-gate.py` cannot import its parser | the hook's own message (`:54-65`) | remove the row with the Edit tool. `bash-gate.py` judges only Bash, and the concept gate allows `.claude/` files |
  | `bash-gate.py` is missing | Python's own error, exit 2, on every Bash call | the same Edit-tool route |
  | `codegraph-first-guard.py` is missing | Python's error on every Read, Grep and Glob, including the read of `settings.json` that Edit needs first | edit the row through the shell, or edit the file outside the session |
  | `codegraph-turn-reset.py` is missing | Python's error on `UserPromptSubmit`, so **every prompt is blocked** | edit `.claude/settings.json` outside the session, in an editor |
  | `codegraph-turn-tracker.py` is missing | an error after each CodeGraph call; the sentinel is never set, so reads stay blocked | as for a missing `codegraph-first-guard.py` |

  - **A session with no `mcp__codegraph__*` tool.** `decide` (`:335-368`) never checks for an index, so every source Read is blocked. Reading through the shell works, as does running `/auto-improve-codegraph-uninstall` and then starting a new session.
  - **The codegraph block message** is self-contained plain text that names no document. It says:
    - call any `mcp__codegraph__*` tool first;
    - if this session has none, read through the shell, or run `/auto-improve-codegraph-uninstall` and start a new session;
    - if the index is stale, run `codegraph sync` or `codegraph init -i`;
    - `/auto-improve-codegraph-install` installs the add-on.

    A test checks that it names the uninstall skill, and that it carries no `references/` path and no `CLAUDE_SKIP_CG`.
  - **Skill text.** Today the uninstall skills say "never edit `settings.json` by hand" (`auto-improve-strict-shell-gate-uninstall/SKILL.md:17,128`). That becomes: "the skill never edits it by hand; only when a hook cannot run (the table in README) does the user remove its row by hand". README carries the table.

### Doctor rules (t5)

- **D-3. A disabled hook is still installed.** Every plugin add-on is checked. Names are each `disabled[].hook` and its `former_names`, compared case-insensitively.
  - **A file** `.claude/hooks/<name>` gives the finding `.claude/hooks/<name>`.
  - **A row** in `.claude/settings.json` or `.claude/settings.local.json` gives the finding `<layer>:<event>:<name>`.
    - Rows are read with the existing reader `_effective_hooks` / `_launched_and_first_argument` (`plugin_doctor.py:415-482`), called once per layer, so a `gate-launch.py` row resolves to the file it gates.
    - The kind is `disabled-hook-installed`; the owner is `plugin`.
    - A layer that cannot be read exits 4 (`_read_json`).
  - **Parity with the install's `_disabled_hook_refusal`.** The claim is narrowed to what both readers can see.
    - They agree on these fixtures: a file only; a `settings.json` row; a row only in `settings.local.json`; both layers; a former name; an unrelated hook; an unreadable layer (install problem ↔ doctor exit 4).
    - Three divergences are pinned as expected, not hidden:
      - a **user-layer** row: the install refuses and the doctor is silent, because the user layer is not project drift;
      - a **non-object layer**: the install refuses, and the doctor reads it as no rows, as it does today (`:557-561`);
      - a **gate-launch row** naming the hook: the doctor finds it, and the install does not (its `_hook_key` matches the first `.py`). No released disabled hook was ever gate-launched.
- **D-4. Documents.** An add-on that declares `documents` is compared when the sync config's `addons` lists it, or when any of its documents exists in the project.
  - A pair is `content-differs` (after the line-ending fold) or `one-sided`, and counts in `compared_addons`.
  - The destination constant equals `auto_improve_finish_install.ADDON_DOCUMENTS_REL` (`:185`), and a test checks it.
- **D-5.** `--drift` never writes. When it compares nothing, it still exits 4.

### Events

Not applicable. Reason: these are command-line hooks and scripts; nothing publishes or subscribes.

### Commands

| Name | Handler | Payload | Possible rejections |
|---|---|---|---|
| Check plugin drift (extended) | `plugin_doctor.py --drift` | as today | as today (exit 4). The new kind only adds to exit 1 |

---

## Reused Mechanisms

- **Guard rules file** (MECHANISMS.md:52) — G-1, controlled with the rules file renamed away.
- **Two-layer Claude path resolution** (:42) — G-3.
- **Guard fallback mode** (:54) — consumed. V-2 avoids its "throws fails open" sharp edge.
- **Preview-hash apply** (:58) — consumed as-is. With the key absent, the plan emits an empty `kill-switches` list.
- **Scroll-edge CSS primitive** (:31), **Sibling skill reference file** (:70) — consumed.
- **Vendored-asset drift** (VOCABULARY.md:35), implemented by `plugin_doctor.py --drift` — extended by D-3 and D-4. They reuse `_effective_hooks`, `_launched_and_first_argument`, `_read_json`, `_folded_bytes`, `_plugin_addon` and `add()`.

---

## New Mechanisms (if any)

None new to this contract. "Disabled add-on hook" was already justified in the parent contract and is only promoted here (t8). The Post-edit view stays internal to the guard.

---

## Extension Points

- `architecture-guard.py`:
  - a view builder for each file;
  - a pass over whole-file rules once per call in `main`;
  - the `hex-color` branch;
  - `load_app_rules`, the `is_*` predicates and `classify_sibling_component`;
  - the docstring, `:52-59`, and a "Known limits" block covering W5, W6b, W8, W11 and the G-2 and G-5 limits.
- "Enforced by" corrections, only on the lines the fixes make false:
  - t1: `TAILWINDCSS_RULES.md:61,109,148`;
  - t2: `TAILWINDCSS_RULES.md:29,54` and `ANGULAR_CODE_RULES.md:37`.
- `plugin_doctor.py`: `FINDING_KINDS`, `_plugin_addon`, and the loops in `_compute_drift`.
- t3's files (K-1 to K-4).
- `## Registry appends`, written by t8.

---

## Integration Surfaces

Not applicable. Reason: feature is contained within a single layer.

---

## Adjacent Areas

Not applicable. Reason: cross-area scan returned no signal above the threshold.

---

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

---

## Chat Tool Impact

**No — UI/admin-only.** Justification: no REST endpoint or SignalR event is added.

---

## Non-Goals

- New or reworded rule entries, except P-002 and the "Enforced by" corrections. C1 to C6, the parent's Q13, and the verbatim old-hook lines (`TAILWINDCSS_RULES.md:27`, `ANGULAR_CODE_RULES.md:35`) stay unchanged.
- The default hooks' own switches: `CLAUDE_ARCH_GUARD`, and `CLAUDE_CONCEPT_GATE` as `concept-gate.py` and `concept_changed_check.py` read it.
- A codegraph check for a missing index (K-4 states the gap).
- Editing `angular-tailwind-advisor.py`, adopting `.claude/rules/`, and a `python-ai` skill.
- Other hooks' `Path.home()` fallbacks, and `integration-check.rules.json:12`.
- Making the doctor read the user settings layer, or refuse a non-object layer. Both are D-3 divergences, pinned as expected.

---

## Confidence

Confidence: Medium.
- High: the ledger, K-1 to K-4, D-3 and D-4, each checked at file:line.
- Medium: G-4's restructuring of `main`.
- Low: the rules-route outcome. Nothing depends on it.

---

## Alternatives Considered & Why Rejected

- **A (chosen):** the view is used for whole-file rules, once per call. Line rules run on the new text. The residue is recorded as limits.
- **B (rejected):** line rules on the view, or on every touched line.
  - Why rejected: an old violation would block every later edit of that file or line.
- **C (rejected):** stylesheet warnings become blocks.
  - Why rejected: false positives from the line-by-line nesting check.
- **D (rejected):** recognise a suffix-less template by its sibling alone.
  - Why rejected: it would block other frameworks under a hook that is on by default.
- **E (rejected):** the codegraph message points at the decision table.
  - Why rejected: a hook installed in a project cannot find the plugin's folder.
- **F (rejected):** the registry appends ship in t1.
  - Why rejected: they would state t3's and t5's outcomes before those merge (round 3).

---

## Uncertain Assumptions

- `VERIFIED via architecture-guard.py:142-192,209,232,453,456-457,763,935-972,1113`.
- `VERIFIED via architecture-guard.py:26,54,58`, `promote-ui-rule/SKILL.md:58,72` and `_project_paths.py:81,135-136`.
- `VERIFIED via bash-gate.py:54-65,440-442` and `codegraph-first-guard.py:179,335-368,447-451`.
- `VERIFIED via codegraph/addon.json:12-29`: the hooks registered on `UserPromptSubmit` and `PostToolUse`.
- `VERIFIED via auto_improve_finish_install.py:2079-2107` and `plugin_doctor.py:415-482,557-561`: the two readers, and the D-3 divergences.
- `VERIFIED via CLAUDE.md:5,18`, `version-bump.yml:5,15` and `check_version_bump.py:21-31`: `.claude/references/` and `.claude/registries/` are shipped.
- `VERIFIED via the user, 2026-10-30`: W3 means the Angular 20 file names.
- `VERIFIED via the user's global CLAUDE.md`: three of its lines become false or partial. Only the user edits that file. The lines are:
  - the CodeGraph "Bypass: set `CLAUDE_SKIP_CG=1`";
  - "Disable the gate entirely: `CLAUDE_CONCEPT_GATE=off`", which no longer covers the shell gate;
  - the gate "auto-bypasses until the index exists", which `decide` does not do.
- `ASSUMED`, to confirm at approval: in Q1, `CLAUDE_CONCEPT_GATE` means only the add-on's use of it. A wider reading would also change:
  - `concept-gate.py` and `concept_changed_check.py`;
  - `skills/design-first/SKILL.md:313` and `README.md:209`;
  - `test_changed_file_check.py`, `fixtures/gate_parity_corpus.json:118` and `test_main_checkout_guard.py:881-904`;
  - the user's global line.
- `ASSUMED`: no catalogue rule already states table column alignment. t6 checks this first.
- `ASSUMED`: `.claude/rules/*.md` with a `paths:` key is a feature of the host. t7 finds out.

---

## Failure Modes & Mitigations

- **FM:** new guard code raises, and the outer catch allows a blocked edit.
  - **Mitigation:** V-2: seven fallbacks, each with a forced-raise test.
- **FM:** a MultiEdit reports the same violation N times.
  - **Mitigation:** the pass once per call plus de-duplication, tested with a three-edit MultiEdit.
- **FM:** CRLF files never get a view.
  - **Mitigation:** the CRLF fold, with a test.
- **FM:** G-5 lets a real colour through.
  - **Mitigation:** the digit rule and the quote-parity rule, with pins.
- **FM:** G-2 blocks a project that is not Angular.
  - **Mitigation:** the `@Component\s*\(` evidence rule, with a negative test.
- **FM:** with no switch left, a broken gate locks the session.
  - **Mitigation:** the K-4 routes for each hook, documented in README and the skills.
- **FM:** the doctor and the install disagree about a disabled hook.
  - **Mitigation:** the D-3 parity and divergence fixtures.
- **FM:** the registry states facts before they are true.
  - **Mitigation:** t8 depends on 1, 3 and 5.
- **FM:** a rule document keeps stale "Enforced by" text.
  - **Mitigation:** the correction lists in t1 and t2, checked by t10.

---

## Open Questions for User

- [x] **Q1 — Kill switches.** Answer: B, remove them. 2026-10-30. Applied in K-1 to K-4 and t3. The narrow reading of `CLAUDE_CONCEPT_GATE` (only the strict-shell-gate add-on stops reading it) was confirmed by the user at approval, 2026-10-30.
- [x] **Q2 — Candidate patterns.** Answer: accept the recommendation (2026-10-30). P-002 ships; the status badge, card surface and `constrained-panel` are rejected (t6).
- [x] **Q3 — Promote the parent's terms.** Answer: yes. 2026-10-30. The text is in `## Registry appends`. t8 appends it after t1, t3 and t5 have merged; the landing's single raise covers it (Rule V).

---

## Registry appends

Appended by t8, verbatim, at the end of the **Universal** tier of each file. Universal is the tier the plugin syncs (MECHANISMS.md:48). No existing entry is edited. **MECHANISMS.md:15 is not rewritten:** an amendment entry is appended that supersedes its bypass clause, as the registry's append-only rule (MECHANISMS.md:40) requires.

**VOCABULARY.md (Universal):**

- **Add-on** *(2026-10-30)* — a set of files the plugin ships under `.claude/addons/<name>/` and never registers itself; a project gets them only through the add-on's install skill.
  - It declares no kill switch. It is on when installed, and its uninstall skill is the normal way to turn it off.
  - When one of its hooks cannot run, the user removes that hook's row from `.claude/settings.json` by hand, by the route its README table gives for that hook. A hook cannot run when its file is missing (Python exits 2 with its own error) or when a helper fails to import (the hook's own message).
  - The default hooks' switches, such as `CLAUDE_CONCEPT_GATE` read by `concept-gate.py`, are not add-on switches.
  - Contracts: `2026-10-28-angular-tailwind-rule-documents`, `2026-10-30-angular-tailwind-followups`.
- **Add-on manifest** *(2026-10-30)* — `addon.json`: the add-on's hook files and their rows, helpers, `documents`, an optional `stylesheet_snippet`, `disabled` hooks, and its install and uninstall skills. `kill_switches` stays optional in the checkers, so older manifests still parse; no shipped add-on declares it.
- **Add-on document** *(2026-10-30)* — a markdown rule document that an add-on copies into `.claude/references/<add-on>/` and registers in `review.documents`. The project never edits it, and project facts in it are placeholders.
- **Disabled add-on hook** *(2026-10-30)* — a hook script that an add-on still ships but no longer installs. It is declared in the manifest's `disabled` list with its row, its `former_names`, the `released_sha256` of each released copy, and a note file. The install refuses while one is present, the removal takes it out, and `plugin_doctor.py --drift` reports one as `disabled-hook-installed`.
- **Rule ID** *(2026-10-30)* — the stable ID of one shipped rule: `A-nnn` for Angular code, `M-nnn` for Material, `T-nnn` for Tailwind and styling (the catalogue series of issue #84), and `P-nnn` for plugin-owned patterns, which never restate a catalogue rule. Guard messages, tests and documents cite rules by ID.
- **Placeholder slot (amendment)** *(2026-10-30)* — one exception to "an authored slot is never changed": in `review.documents`, an add-on install may append its own Add-on document paths, and the add-on removal may remove exactly those paths.
- **Post-edit view** *(2026-10-30)* — the full text a file will hold once the current Write, Edit or MultiEdit is applied. For a Write it is the content; otherwise it is the disk text with every edit applied in order, with CRLF folded to LF. A guard judges its whole-file rules on it once per file per call. When it is unavailable, those rules are judged on the new text, as before.
- **Accepted guard limit** *(2026-10-30)* — a known gap in a guard that the maintainer has chosen not to close. It is listed under "Known limits" in the guard's docstring, and a test pins it.
- **Vendored-asset drift (amendment)** *(2026-10-30)* — `--drift` also compares Add-on documents (`content-differs` / `one-sided`) and reports a Disabled add-on hook still present as `disabled-hook-installed`.

**MECHANISMS.md (Universal):**

- **Disabled add-on hook** *(2026-10-30)* — keeps a retired add-on hook shipped, documented and removable, while no install writes it.
  - **Where:** the `disabled` key of `addon.json`, plus `<addon>/DISABLED.md`.
  - **Enforced by:** `_read_addon_manifest` and `addon_problems` (a file name appears in only one list); the install refusal `disabled-hook-present`; `addon-remove`, which matches the current and former names; and `plugin_doctor.py --drift` (`disabled-hook-installed`).
  - **Extend by:** move a hook's name and row from `hooks` and `registrations` into `disabled`, and add its released hashes.
  - **Contract:** `2026-10-28-angular-tailwind-rule-documents`.
- **CodeGraph (amendment)** *(2026-10-30)* — supersedes the bypass clause of the CodeGraph entry above. `CLAUDE_SKIP_CG` no longer exists. The ways out are:
  - call any `mcp__codegraph__*` tool;
  - read through the shell;
  - run `/auto-improve-codegraph-uninstall` and start a new session;
  - when a codegraph hook file is missing, remove its row by hand, by the route in the README table.

  **Contract:** `2026-10-30-angular-tailwind-followups`.

---

## Critique

The full text of rounds 1 to 3 is to be archived by the main session in `.claude/contract-history/2026-10-30-angular-tailwind-followups.round-<n>.md`.

**Round 1 (blockers-found):**
- Rule documents were made false → the "Enforced by" corrections.
- A single version raise → Rule V.
- The line-rule gap → W11.
- CRLF → the fold.
- A builder crash → V-2.
- G-5 untested → pins.
- W9 `:72` → a lookup block.
- `hook_file` home tail → G-3.
- W10 disposition → already-resolved.
- Order → the view moved to t1.
- D-3 parity → a test.
- K-2 → an absence check.
- NITs fixed, except `ClientApp`, which is a Non-Goal.

**Round 2 (blockers-found):**
- Registry raise → t8 with its own raise.
- "Only way out" → K-4 routes for each hook.
- Codegraph message → self-contained.
- W6 → W6a fixed, W6b accepted.
- V-2 scope → widened.
- G-4 external rules and frequency → stated.
- G-2 outside Angular → evidence rule.
- D-3 layers → per-layer reads.
- K-3 → stated plainly.
- Codegraph without the tool → K-4.
- NITs fixed, except mixed line numbers in messages: changing the format would break the shape `test_architecture_guard_messages.py` pins.

**Round 3 (blockers-found):**
- BLOCKER, registry before the facts → t8 depends on 1, 3 and 5 (Alternative F).
- WARN, text deferred → `## Registry appends` written now, with tier and append-only rule stated.
- WARN, D-3 parity too broad → the existing reader is reused, the claim narrowed, three divergences pinned.
- WARN, V-2 `main` steps → three more forced-raise tests.
- WARN, missing-file routes → the K-4 table and the Add-on text.
- NITs, all fixed:
  - `@Component\s*\(`;
  - the `.css` slice;
  - G-3 wording;
  - the uninstall "never by hand" line;
  - the empty `kill-switches` list;
  - MECHANISMS.md:15 handled as an append.

---

## Lessons referenced

- **2026-10-28 — A new term's definition must be true against every existing member** — heeded by: the Add-on text covering every hook's failure route; t8 waiting for the facts.
- **2026-10-15 — A cleanup wired to run before its own trigger event has fired never runs** — heeded by t8's dependencies.
- **2026-10-28 — Guard messages must use names the guard emits and degrade when a cited document is absent** — heeded by the self-contained codegraph message.
- **2026-10-15 — Reuse the existing brief-linkage reader** — heeded by D-3 reusing `_effective_hooks`.
- **2026-10-22 — Describe a broken install by the rows each install age really has** — heeded by D-3 (former names, both layers, gate-launch rows).
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** — heeded by: G-4's "or" rule, V-2, G-2's evidence rule, G-5's pins, and the guard suites unchanged.
- **2026-10-17 — Judge "identical to master" by git's view, not raw bytes, on Windows** — heeded by the CRLF fold.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded by the ledger, the corrections, K-3 and K-4.
- **2026-10-15 — Locate a script from the plugin root** and **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded by G-3 `:72` and t2.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — Q1 to Q3 are in the body, and the registry text is written now.
- **2026-10-05 — Never hide a forbidden name by hashing it**; **2026-10-04 — Do not rely on a host expanding a variable**; **2026-10-28 — State the real trigger of a hook**; **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam** — heeded by the K-2, D-3 and G-5 controls; by t7; by the trial record; and by promoting nothing new.
- Orthogonal to north-stars: none active.

---

## Implementation Handoff

**Delivery.** The layout is the Parent Branch Delivery Rule: parent branch `feature/86-angular-tailwind-followups`, parent issue #86.

**Rule V (version).** No sub-task raises the plugin version, and no block lists a version file. Each sub-task pull request into the parent branch keeps the parent's version (`check_version_bump.py` parent mode). The landing merges master into the parent branch and raises the version once: minor + 1, patch 0, relative to master (0.10.1 → 0.11.0 if nothing else lands first), via `--raise` then `--exact`. That one raise covers every shipped change here, including t7's record and t8's registry appends.

### 1. Guard post-edit view and matching precision (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/hooks/architecture-guard.py`
- `.claude/hooks/tests/test_architecture_guard_precision.py`
- `.claude/addons/angular-tailwind/documents/TAILWINDCSS_RULES.md`

**Pre-written TASK block:**
```
TASK: Implement G-4 and G-5 with V-2 for the builder, the per-call pass, the view-versus-disk comparison,
de-duplication and G-5. Fix W4, W6a and W7. Pin W5, W6b, W8 and W11.
CONTEXT: concept contract at .claude/concepts/2026-10-30-angular-tailwind-followups.md
FILES: as listed.
CONSTRAINTS:
  - View tests: a missing file; an ambiguous old_string; replace_all; a three-edit MultiEdit that reports each
    violation once; non-UTF-8 bytes; a CRLF file.
  - One forced-raise test per V-2 step above. Each expects exit 2 on new text that blocks today.
  - Inline template: an Edit that adds "template:" inside an existing decorator blocks. An Edit elsewhere in a
    file that already has one gives today's result.
  - Height chain: a fragment inside a file whose root carries h-full gives no warning.
  - Every G-5 row. The docstring "Known limits" block.
  - TAILWINDCSS_RULES.md: correct only the "Enforced by" lines at :61, :109 and :148. Run
    test_angular_rule_coverage.py.
  - Run test_architecture_guard_scss.py, test_architecture_guard_messages.py and
    test_hook_data_files_project_first.py unchanged.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-30-angular-tailwind-followups.md
  contract_status: approved
```

### 2. Guard paths and file recognition (`python-ai-developer`)

**Depends on:** 1

**Files to touch:**
- `.claude/hooks/architecture-guard.py`
- `.claude/hooks/tests/test_architecture_guard_paths.py`
- `.claude/scripts/tests/test_design_document_paths.py`
- `.claude/addons/angular-tailwind/documents/TAILWINDCSS_RULES.md`
- `.claude/addons/angular-tailwind/documents/ANGULAR_CODE_RULES.md`
- `skills/promote-ui-rule/SKILL.md`

**Pre-written TASK block:**
```
TASK: Implement G-1, G-2 and G-3 with V-2 for G-1 and G-2. Pin W2 and W10.
CONTEXT: concept contract (the ledger, G-1 to G-3, V-2).
FILES: as listed.
CONSTRAINTS:
  - G-1 controls: the rules file renamed away; "apps"; a two-segment root.
  - G-2 tests: a sibling written "@Component ({" is recognised; <stem>.css; negatives index.html, main.ts,
    x.spec.ts, x.d.ts, and app.html beside an app.ts with no decorator. Forced-raise tests for G-1 and G-2.
  - G-3: the ast and string test exactly as stated. promote-ui-rule :58 and :72 as stated. Run
    test_skill_script_lookup.py. Do NOT edit the advisor script.
  - W2: no "ClientApp" and no "/features/" in the guard. W10: every repository path cited in the shipped design
    documents exists; install-time paths and the foundation.md:47 note are excluded by name.
  - Correct only the "Enforced by" lines TAILWINDCSS_RULES.md:29 and :54, and ANGULAR_CODE_RULES.md:37. Run
    test_angular_rule_coverage.py and the three guard suites unchanged.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-30-angular-tailwind-followups.md
  contract_status: approved
```

### 3. Remove the add-on kill switches (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/addons/codegraph/addon.json`
- `.claude/addons/strict-shell-gate/addon.json`
- `.claude/addons/codegraph/hooks/codegraph-first-guard.py`
- `.claude/addons/strict-shell-gate/hooks/bash-gate.py`
- `skills/auto-improve-codegraph-install/SKILL.md`
- `skills/auto-improve-codegraph-uninstall/SKILL.md`
- `skills/auto-improve-strict-shell-gate-install/SKILL.md`
- `skills/auto-improve-strict-shell-gate-uninstall/SKILL.md`
- `.claude/references/codegraph-decision-table.md`
- `README.md`
- `.claude/scripts/tests/test_plugin_manifests.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `.claude/hooks/tests/test_contract_index.py`
- `.claude/hooks/tests/test_main_checkout_guard.py`
- `.claude/hooks/tests/test_shell_write_targets.py`
- `.claude/hooks/tests/test_codegraph_first_guard.py`

**Pre-written TASK block:**
```
TASK: Implement K-1 to K-4: remove CLAUDE_SKIP_CG, CLAUDE_BASH_GATE and the add-on's use of CLAUDE_CONCEPT_GATE.
CONTEXT: concept contract (Kill-switch removal; the ASSUMED narrow reading).
FILES: as listed.
CONSTRAINTS:
  - Hooks: delete the switch checks and the docstring and message lines that name them. The codegraph block
    message is the K-4 text. Do NOT touch concept-gate.py or concept_changed_check.py.
  - Skills, the decision table and README (:268, :341): no kill switch. Add the K-4 table to README. Replace the
    uninstall skills' "never edit settings.json by hand" lines (strict-shell-gate uninstall :17 and :128, and
    the codegraph equivalents) with the K-4 wording. State that CLAUDE_CONCEPT_GATE=off no longer turns off the
    shell gate.
  - Tests:
    * test_plugin_manifests: K-1, K-2 (with its positive control), K-3.
    * test_auto_improve_finish_install: the :250 fake drops its CLAUDE_BASH_GATE line; :2785 expects
      {CLAUDE_CONCEPT_GATE, CLAUDE_ARCH_GUARD}; :3412, :3420 and :4881 expect an empty kill-switches list.
    * test_contract_index section (f): the bash-gate rows prove the switches have no effect.
    * test_main_checkout_guard: the :889-891 comment only.
    * test_shell_write_targets: K-4 reachability, and the import-failure message names removing the row.
    * test_codegraph_first_guard: CLAUDE_SKIP_CG=1 no longer bypasses; the message checks of K-4.
  - Leave the environment strip lists (test_flat_worktree.py:62, test_shell_write_targets.py:227-228,
    test_worktree_path_guards.py:379) as they are: they guard against a shell that still sets an old value.
  - Pull request body: the three lines of the user's global CLAUDE.md that only the user changes.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-30-angular-tailwind-followups.md
  contract_status: approved
```

### 4. Advisor keyword note (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/addons/angular-tailwind/DISABLED.md`
- `.claude/hooks/tests/test_addons.py`

**Pre-written TASK block:**
```
TASK: Keep the "ui" limit documented. Add the advisor's home-folder fallback (line 43) as a second defect to fix
before turning the hook back on. Replace the kill-switch step.
CONTEXT: concept contract (criterion 3, G-3, K-1).
FILES: as listed.
CONSTRAINTS:
  - "How to turn it back on":
    * fix the keyword pattern, or drop "ui";
    * read the rules file through _project_paths;
    * add the new hash to released_sha256.
    Step 2 becomes "add-ons declare no kill switch".
  - A test asserts that DISABLED.md names both defects. Do not edit the advisor script.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-30-angular-tailwind-followups.md
  contract_status: approved
```

### 5. Doctor drift and agent preload (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/scripts/plugin_doctor.py`
- `.claude/scripts/tests/test_plugin_doctor.py`
- `agents/python-ai-developer.md`
- `.claude/scripts/tests/test_agent_skill_preloads.py`

**Pre-written TASK block:**
```
TASK: Implement D-3 and D-4 in --drift, and remove the python-ai preload.
CONTEXT: concept contract (Doctor rules D-1 to D-5).
FILES: as listed.
CONSTRAINTS:
  - D-3 reuses _effective_hooks and _launched_and_first_argument, called per layer. Include the parity fixtures
    and the three pinned divergences, exactly as stated. Positive and negative controls.
  - D-4: the destination equality test. --drift never writes.
  - Remove the skills: block of python-ai-developer. New test: every skills: entry in agents/*.md resolves to a
    shipped skills/<name>/SKILL.md, resolved the way test_angular_rule_delivery.py does. A planted missing
    name fails.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-30-angular-tailwind-followups.md
  contract_status: approved
```

### 6. Candidate patterns (`ui-ux-designer`)

**Depends on:** none

**Files to touch:**
- `.claude/addons/angular-tailwind/documents/UI-UX-PATTERNS.md`

**Pre-written TASK block:**
```
TASK: Ship P-002 "Table column alignment" and record the three rejected patterns (Q2).
CONTEXT: concept contract (Pattern decision, Q2). Rule entry shape and precedence paragraph as in the parent.
FILES: as listed.
CONSTRAINTS:
  - P-002: numeric columns and their headers right-aligned, text columns left-aligned, each header aligned with
    its column. Enforced by: not enforced. One short example using token utilities and placeholders. First check
    that no catalogue rule in the four documents already states it.
  - Update the boundary paragraph. Add "## Patterns this plugin does not ship", one line each:
    * status badge: its states and colours are product data, and the application-design skill has an
      advisory one;
    * card surface: product look and feel;
    * constrained-panel: a project class name; T-014 and the scroll container already bound height.
  - Run .claude/hooks/tests/test_angular_rule_coverage.py.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-30-angular-tailwind-followups.md
  contract_status: approved
```

### 7. Rules route trial (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/references/claude-rules-route-trial.md`

**Pre-written TASK block:**
```
TASK: Try the .claude/rules/ route live and record the outcome as a Route trial record.
CONTEXT: concept contract (Route trial record; alternative E of the parent).
FILES: as listed.
CONSTRAINTS:
  - Work in a new temporary folder outside every checkout. It holds .claude/rules/angular.md (paths:
    "**/*.component.html", plus a sentinel line) and one matching file.
  - PowerShell:  claude -p "Quote the sentinel line of any rule you were given" --output-format json
    Then a prompt that opens the matching file, then one that uses a subagent. Bash: the same commands.
    Record each output and exit code.
  - Record what was observed, including "did not load". Add one line on whether a follow-up issue is worth
    opening.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-30-angular-tailwind-followups.md
  contract_status: approved
```

### 8. Registry appends (`python-ai-developer`)

**Depends on:** 1, 3, 5

**Files to touch:**
- `.claude/registries/VOCABULARY.md`
- `.claude/registries/MECHANISMS.md`

**Pre-written TASK block:**
```
TASK: Append the "## Registry appends" text of this contract, verbatim, at the end of the Universal tier of each
file.
CONTEXT: concept contract (Registry appends, Q3). Runs only after t1, t3 and t5 have merged, so every appended
fact is already true.
FILES: as listed.
CONSTRAINTS:
  - Never edit, reorder or rewrite an existing entry. MECHANISMS.md:15 stays as it is; the CodeGraph amendment
    supersedes its bypass clause.
  - Before appending, check each appended fact against master: no add-on declares kill_switches; the codegraph
    message names no CLAUDE_SKIP_CG; --drift emits disabled-hook-installed.
  - Regenerate the digest if the generator exists (py -3 .claude/scripts/generate_registry_digest.py).
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-30-angular-tailwind-followups.md
  contract_status: approved
```

### 9. Release notes (`python-ai-developer`)

**Depends on:** 1, 2, 3, 4, 5, 6, 7, 8

**Files to touch:**
- `README.md`

**Pre-written TASK block:**
```
TASK: Write one "Changed in <version>" note covering t1 to t8, and update the README version line. <version> is
the landing's raise (Rule V): master's minor + 1, patch 0, read from master when this pull request opens.
CONTEXT: concept contract (all groups).
FILES: README.md
CONSTRAINTS:
  - Cover:
    * the guard fixes and their Known limits;
    * the removed switches and the K-4 routes;
    * that CLAUDE_CONCEPT_GATE=off no longer turns off the shell gate;
    * the three global CLAUDE.md lines that only the user changes;
    * the doctor's new finding and document pairs;
    * the removed preload;
    * P-002 and the rejected patterns;
    * the trial outcome;
    * the registry promotions.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-30-angular-tailwind-followups.md
  contract_status: approved
```

### 10. Review (`fullstack-code-reviewer`)

**Depends on:** 9

**Files to touch:**
- `.claude/reviews/2026-10-30-angular-tailwind-followups/t10-review-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review sub-tasks 1-9 against this contract and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-10-30-angular-tailwind-followups.md
FILES: .claude/reviews/2026-10-30-angular-tailwind-followups/t10-review-fullstack-code-reviewer.md
CONSTRAINTS:
  - Check:
    * G-0 to G-5, V-1, V-2, K-1 to K-4 and D-1 to D-5;
    * the "Enforced by" corrections, and only those;
    * P-002 and the rejections;
    * the registry appends verbatim, merged after t1, t3 and t5;
    * the trial record's commands and exit codes;
    * no sub-task pull request changes a version file (the landing raises once, Rule V);
    * the guard suites ran unchanged.
  - Write the six-section artefact. The file does NOT exist yet; you create it. Name the commit range base..head.
  - "## Evidence" lists the commands with their exit codes and is never empty.
  - The header ends with exactly one of: "**Verdict:** pass", "**Verdict:** pass-with-findings",
    "**Verdict:** blocked".
  - Write the Gate Output <artefact stem>.gate.json beside it, covering every Review checklist item.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-30-angular-tailwind-followups.md
  contract_status: approved
```

---

## Review checklist (filled in after implementation)

- [ ] Implementation matches Data Shapes exactly — not performed (disclosed on #86)
- [x] Reused Mechanisms are actually reused (no parallel implementations introduced) — evidence: .claude/reviews/2026-10-30-angular-tailwind-followups/t10-review-fullstack-code-reviewer.md
- [x] New Mechanisms (if any) promoted to `MECHANISMS.md` — evidence: .claude/reviews/2026-10-30-angular-tailwind-followups/t10-review-fullstack-code-reviewer.md
- [x] New vocabulary terms promoted to `VOCABULARY.md` — evidence: .claude/reviews/2026-10-30-angular-tailwind-followups/t10-review-fullstack-code-reviewer.md
- [ ] Integration surfaces reflected on both backend and frontend sides — not applicable (.claude/reviews/2026-10-30-angular-tailwind-followups/t10-review-fullstack-code-reviewer.md)
- [ ] `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced — not applicable (.claude/reviews/2026-10-30-angular-tailwind-followups/t10-review-fullstack-code-reviewer.md)
- [ ] No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface) — not applicable (.claude/reviews/2026-10-30-angular-tailwind-followups/t10-review-fullstack-code-reviewer.md)
- [x] `Status` flipped to `implemented`
