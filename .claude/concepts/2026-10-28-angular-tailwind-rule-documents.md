# Concept Contract — Replace the angular-tailwind prompt hook with rule documents and a skill

**Project:** claude-agentic-auto-improve
**Date:** 2026-10-28
**Requested by:** user
**Status:** approved
**Supersedes:** none
**Work Item Brief:** .claude/work-items/2026-10-28-84-angular-tailwind-rule-documents.md
**Tracking issue:** #86
**Budget:** 12,000 tokens

---

## Business Concept

- **What is this thing, in domain language?**
  The `angular-tailwind` add-on stops starting a program on every prompt. Instead it ships **rule documents** (Angular code, Angular Material, Tailwind styling, generic UI patterns). The install skill copies them into the project and registers them in the project profile's `review.documents` slot. A plugin skill carries the short rule list and points at those documents, and the Angular developer agent preloads that skill. The edit-time guard stays the enforcement, and its block and warn lines now name the **Rule ID**, plus the document when that document is installed. The old prompt hook becomes a **disabled add-on hook**: its script still ships, no install writes its row, and a note says what it did, what it cost, why it is off and how to turn it back on. The install learns one new operation: the removal of what an install wrote. A paired uninstall skill runs it. It is safe to run twice, and it also cleans projects that installed the old hook under either of its file names.

- **Existing VOCABULARY.md terms that apply:** Project profile, Placeholder slot (amended below), Registration key (used to match rows for removal), Install mode, Vendored-asset drift, Design foundation (it already states part of group T; C1 and C3 are settled there too), Guard rules file.

- **New terms and one amendment for VOCABULARY.md (Universal tier):**
  - **Add-on** — a set of files the plugin ships under `.claude/addons/<name>/` and never registers itself. A project gets them only by running the add-on's install skill. It is on when installed, and off when never installed or removed by its uninstall skill. Its manifest may also declare kill switches: human-only overrides that the user sets and an agent never sets. `codegraph` keeps `CLAUDE_SKIP_CG`, and `strict-shell-gate` keeps `CLAUDE_BASH_GATE` and `CLAUDE_CONCEPT_GATE`. `angular-tailwind` declares none. Issue #84's decision 3 (no switches for ordinary add-ons) is applied here to `angular-tailwind` only; whether the other two keep their overrides is in the follow-up stub.
  - **Add-on manifest** — `addon.json`, the declaration of what an add-on installs: its hook files with their rows, its helpers, its documents, an optional stylesheet snippet, its disabled hooks, any kill switches, and its install and uninstall skills. The script reads it and holds every install and removal rule.
  - **Disabled add-on hook** — a hook script an add-on still ships but no longer installs. It is declared in the manifest's `disabled` list with the row older installs carry, its former file names, the hashes of every released copy, and a note file. The removal takes it out of old installs. Turning it back on is a plugin change that moves it back into `hooks`.
  - **Add-on document** — a markdown rule document an add-on copies into the project and registers in `review.documents`. The project never edits it. Project facts in it are placeholders that point at profile slots or at the project's own documents.
  - **Rule ID** — the stable identifier of one shipped rule. `A-nnn` (Angular code), `M-nnn` (Material) and `T-nnn` (Tailwind and styling) are the catalogue IDs of issue #84, companion 1. `P-nnn` (patterns) is a plugin-owned series for patterns the catalogue does not hold. A `P` rule never restates a catalogue rule. Guard messages, tests and documents cite rules by ID.
  - **Placeholder slot (amendment)** — add one sentence to the existing entry: "One exception: in `review.documents`, an add-on install may append its own Add-on document paths and the add-on removal may remove exactly those paths. No other entry and no other slot is changed by either."

---

## End-User View

Not applicable. Reason: the plugin has no product screens. `Files to touch` holds no Angular component, template, stylesheet, state service, route or layout of an application. The shipped documents are rules about Angular code, not Angular code.

---

## Data Shapes

### Entities

| Name | Fields | Invariants | Ownership |
|---|---|---|---|
| Add-on manifest (extended) | `name`; `hooks` (list of plain `.py` names, **may be empty**); `helpers`; `registrations`; `prerequisites`; `kill_switches` (**optional**: absent means none, and when present it is a list of `CLAUDE_*` names); `install_skill`; **`uninstall_skill`** (`auto-improve-<name>-uninstall`, all three add-ons, Q8); **`documents`** (optional list of plain `.md` names under `<addon>/documents/`); **`stylesheet_snippet`** (optional Stylesheet snippet); **`disabled`** (optional list of Disabled hook entries) | I-1: `hooks` and `documents` are not both empty. I-2: every hook has at least one row, and every row names a hook. `registrations` may be empty only when `hooks` is empty. I-3: a file name appears in at most one of `hooks`, `disabled[].hook` and `disabled[].former_names`, and every current file exists in the add-on folder. I-4: angular-tailwind declares no `kill_switches`, no row on `UserPromptSubmit`, and no row on any event that runs per prompt | the add-on folder |
| Disabled hook entry | `hook` (plain name under `<addon>/hooks/`); **`former_names`** (`["architecture-advisor.py"]`); `registration` (`event`, optional `matcher`, `args`: the row older installs carry); `note` (`DISABLED.md`); `released_sha256` (the hex SHA-256 of the folded bytes of every released copy, under the current and every former name, from git history; Q15) | I-5: the install never copies a disabled hook and never writes its row. A project row or file naming `hook` or any former name is a disabled hook present. The kept script carries no `CLAUDE_ARCH_ADVISOR` check (Q15) | manifest |
| Add-on document | file name; rule entries; boundary paragraph; precedence paragraph; placeholder list | Each document opens with two paragraphs. (a) Boundary: the groups it holds and the groups it does not hold, naming the sibling document for each. (b) Precedence: "The project's own instructions win over every rule document. A document the project wrote and lists in `review.documents` wins over this plugin document where they disagree. For what it checks, the guard's verdict is final." It holds no project fact (see the issue's "Project facts" list). Each such fact is a `<placeholder>` naming a profile slot, or "the project's own design document listed in `review.documents`" | shipped by the add-on, copied verbatim, never edited by the project |
| Rule document set (Q1, Q2, Q3) | `ANGULAR_CODE_RULES.md` (group A except A-025); `ANGULAR_MATERIAL_RULES.md` (group M); `TAILWINDCSS_RULES.md` (group T, including the scroll container pattern); `UI-UX-PATTERNS.md` (A-025, the states pattern with its markup, and P-001, the error banner). Destination in the project: `.claude/references/angular-tailwind/<file>` | Every catalogue ID from companion 1 appears exactly once as a rule heading across the set. `P` IDs are unique and restate no catalogue rule. The status badge, table rules beyond T-023, the card surface and `constrained-panel` are not shipped (Q3) | the add-on |

### Value Objects

| Name | Fields | Used as |
|---|---|---|
| Rule entry | Rule ID; one-sentence rule; "Enforced by" (`guard blocks` / `guard warns` / `not enforced`, with the guard rule name it emits); allowed exceptions; at most one short example | One heading `### <ID> — <title>` in a document. A-002, A-004, A-006, A-011 and A-012 read `not enforced`, with the reason "the source project's pattern enforcer does not ship in this plugin" |
| Coverage row | printed text of the old hook; required Rule IDs; required literal fragments (for example `style=`, `text-gray-`, `scroll-edge-header`, `templateUrl`) | the data table of the coverage test (t2), one row per line of companion 2's coverage map, including the three extra pieces |
| Stylesheet snippet (Q12) | file `snippets/scroll-edge.scss`; selectors `.scroll-edge`, `.scroll-edge-content`, `.scroll-edge-header`; the setting `--scroll-edge-header-bg` with the default `var(--mat-sys-surface)`; begin and end marker comments `/* agentic-auto-improve:scroll-edge begin */` … `end */` | Appended at the end of a named global stylesheet, which is after Tailwind and the theme bridge. The header rule is `@apply sticky top-0 z-10;` plus `background-color: var(--scroll-edge-header-bg, var(--mat-sys-surface));`. The wrapper has no `overflow-hidden`; the documents name it as an optional addition. The removal never takes the snippet out (Q7) |
| Removal plan | rows to remove (Registration keys, matched under the current and former hook names); files, each `delete` / `kept-differs` / `absent`; document entries to unregister; kept items (helpers, snippet) with the reason; `plan-sha256` | the `addon-remove` preview |
| Guard violation (extended) | `rule` (the name the guard emits); `line_no`; `line_text`; `suggestion`; **`rule_id`**; **`document`** (a name, or none) | The output line is `[<rule>] <rule_id> line N`. One footer line says either `Rule text: <project>/.claude/references/angular-tailwind/<document>` when that file exists, or `Rule text not installed in this project: the angular-tailwind add-on installs it (/auto-improve-angular-tailwind-install).` when it does not |

### Guard rule map (t6; key matching stated)

- **Exact names:**
  - `inline-style` → T-001
  - `hex-color` → T-004
  - `scroll-edge` → T-012 (also emitted by the new `sticky` check)
  - `inline-component-template` and `inline-component-styles` → A-003
  - `scss-warn:raw-property` → T-010
  - `scss-warn:dead-host` → T-011
- **Prefixes:**
  - `gray-utility:` → T-003
  - `app-banned-class:` → T-022
  - `height-chain-warn:` → T-014
  - `external:` → that rule's own id, with no document
- **Documents:** T-numbered rules point at `TAILWINDCSS_RULES.md`; A-003 points at `ANGULAR_CODE_RULES.md`.
- **Project root:** the guard checks whether a document is installed under the project root, which comes from `_project_paths` (`CLAUDE_PROJECT_DIR`). When the root cannot be determined, the document counts as not installed.

### Settled rule texts (binding wording for t1, t6 and t7)

- **C1 Inline style (T-001 and T-008; Q11).** A component template has no static `style="…"`. The closed list of exceptions:
  - (a) Bindings `[style.prop]`, `[style]` and `[attr.style]` whose value is computed at run time. Any property is allowed here, including a chart colour read from a theme token by a signal, which is what the guard's hex-colour suggestion already advises.
  - (b) A static `style` on an SVG element (`svg`, `g`, `text`, `tspan`, `rect`, `circle`, `ellipse`, `line`, `polyline`, `polygon`, `path`, `use`, `image`, `foreignObject`) or on `canvas`, when every property is a positioning property (`position`, `left`, `top`, `right`, `bottom`, `transform`, `transform-origin`, `translate`). The opening tag name must sit on the same line as `style=`, because the guard reads one line at a time. A tag split across lines is not excepted.
  - (c) Tooltip `max-width`, written as a global class. That is a recipe, not an exception to T-001.

  A static `style` never carries a colour, background or border value. A fixed theme colour is a utility class (T-002), never a binding. The Design foundation's "Inline Style Elimination" paragraph is reworded to this scope.
- **C2 Material overrides (M-006 and T-011).** An override that serves one component goes in that component's stylesheet, under `:host ::ng-deep` (encapsulated component) or under the element selector (`ViewEncapsulation.None`). An override used by more than one component goes in the global stylesheet, scoped by a wrapper class. Neither rule says "only".
- **C3 `!important` and Tailwind `!` (T-018 and M-003).** A stylesheet never writes `!important` except to override a third-party library. In a template, the `!` prefix is allowed only on an element a third-party library renders (Material), to beat its host styles (M-003, M-004, M-011), and never on the project's own elements.
- **C4 Pixel values and arbitrary values (T-019).** Use the Tailwind scale. An arbitrary value such as `max-h-[400px]` is a last resort, used only when no scale step fits, and only inside a utility class. Never use one in `style=` or in a component stylesheet. The guard's suggestion stops citing `w-[200px]`.
- **C5 Response envelope (Q9).** No document or agent names a success flag. The text reads "check `<the success flag of the project's response envelope>` (named in the project's own handbook listed in `review.documents`) before reading the value". No profile slot is added.
- **C6 Theme polarity (T-021).** The `frontend.theme-polarity` slot is the only authority. Documents never state an app's polarity. When a project design document disagrees with the slot, the agent reports the mismatch and does not choose between them.

### Rule skill (Q4, Q14)

`skills/angular-ui-rules/SKILL.md` is a plugin skill that always ships. Its contents:
- the sentinel first line `Rule set: angular-ui-rules`;
- the short rule list, keyed by Rule ID;
- the precedence paragraph;
- the absence clause: when the documents are not in `review.documents`, it says the add-on is not installed and works from the short list alone;
- the per-app instruction: read the working app's `.app-rules.json`, including its `advisorRemindersAppendix`;
- one layout sentence naming `agentic-auto-improve:application-design` and `agentic-auto-improve:website-design` as advisory.

`angular-senior-dev` preloads it. `ui-ux-designer`'s `angular` preload is repointed to it (Q5).

### Events

Not applicable. Reason: these are file and configuration changes made by command-line scripts. Nothing publishes or subscribes to anything.

### Commands

| Name | Handler | Payload | Possible rejections |
|---|---|---|---|
| Install add-on (extended) | `auto_improve_finish_install.py addon` | `--name`, `--project`, `--stylesheet <rel>` (repeatable, t5), `--apply --expect-sha256` | Existing codes, plus: `profile-slot-missing` (no profile, or no `review.documents` row; nothing written); `disabled-hook-present` (a row or file naming a disabled hook or one of its former names is in the project; the message names the uninstall skill; Q6); `stylesheet-partial-snippet` (some of the three classes are defined and some are not); `stylesheet-missing`. When everything is already present: `nothing-to-do` |
| Remove add-on (extension) | `auto_improve_finish_install.py addon-remove` | `--name`, `--project`, `--apply --expect-sha256` | `addon-unknown`, `plugin-source-checkout`, `changed-since-preview`, `write-failed`, and `profile-slot-missing` only when entries need unregistering. A second run gives `nothing-to-do`, exit 0 |

Invariants:
- **I-6 (profile).**
  - Paths are compared without backticks and with forward slashes.
  - The install appends only those of its document paths that are not already listed. A path already listed is skipped. When every path is already listed, the profile is not written.
  - A slot that is a placeholder or `none` becomes the document list.
  - The removal deletes exactly the add-on's paths and leaves every other entry. When no entry remains, the slot reads `none`.
- **I-7 (order).** The removal writes `settings.json` (with a backup) **before** it deletes any hook file. A row that points at a missing script exits 2 and would block every prompt (JOURNAL 2026-10-22).
- **I-8 (deletion).** "Identical" means equal after `_fold_text_bytes`: CRLF folded to LF and a leading byte order mark stripped, the same fold `released_sha256` uses. The removal deletes a file only when it is identical to the plugin's copy or its folded hash is a released hash. A file that differs is kept and reported. Helpers are never deleted. The stylesheet snippet is never removed (Q7).
- **I-9 (hash).** The plan hash covers the settings, profile and stylesheet bytes, plus the bytes of every file to copy or delete.
- **I-10 (no install, nothing).** A project that never ran the install has no add-on document under `.claude/references/angular-tailwind/`, no add-on row, and an unchanged `review.documents`. The plugin's `hooks.json` registers no add-on hook.

---

## Reused Mechanisms

- **Preview-hash apply** — extended through its own "Extend by" seam (`MECHANISMS.md:58`: "return plan, apply and refusal dicts of the same shape from a new subcommand"):
  - The digest gains the profile and stylesheet bytes.
  - `addon-remove` is a new subcommand with the same dict shapes, carrying invariants I-7 and I-8.
  - New refusal codes join the closed set.
  - It reuses `_slot_rows`, `_parse_set_value`, `_format_value`, `_is_placeholder`, `_backup_write`, `_atomic_write`, `_fold_text_bytes`, `_open_box`, `_scan_value_end` and `_plan_settings_edit`.
  - After implementation, the registry entry gains one sentence naming the removal and its order rule.
- **Project profile** — consumed. The `review.documents` slot is the destination. No slot is added (Q9). Placeholder slot is amended (see the new terms above).
- **Registration key** — consumed as-is to find the rows to remove, in string and exec form, under every hook name.
- **Guard rules file** and `architecture-guard.exceptions.json` — consumed as-is. The rule map is generic, so it lives as a constant in the guard. The `reference_documents` key stays, because the guard still prints it.
- **Scroll-edge CSS primitive** — extended with a shipped snippet, a named header-background setting and an install step.
- **Design foundation** and **Sibling skill reference file** — consumed. The foundation's inline-style and `!important` lines are reworded to C1 and C3. The skill points at the foundation and does not restate it.
- **Vendored-asset drift** (`plugin_doctor.py --drift`) — consumed, with one known effect. `plugin_doctor.py:517,535` read the manifest's `hooks`, so with `hooks: []` the presence-based comparison no longer finds old advisor copies. Documents are not compared either. Both effects are in the follow-up stub. The upgrade path does not depend on the doctor, because the install refusal and the removal cover it.

---

## New Mechanisms (if any)

- **Name:** Disabled add-on hook
  - **Purpose:** keep a retired add-on hook shipped, documented and removable, without any install writing it.
  - **Why an existing mechanism was not sufficient:** the plugin has no such state. The README's "Retired hooks" precedent either deletes a hook (`plain-language-guard.py`, 0.9.20) or brings it back as an installed add-on (0.9.9). Both checkers refuse a hook without a row (`_read_addon_manifest` in `auto_improve_finish_install.py` around line 1848; `addon_problems` in `test_plugin_manifests.py` around line 859).
  - **Proposed location:** the `disabled` key of `addon.json`, plus `<addon>/DISABLED.md`.
  - **Extension seam:** any add-on can retire a hook by moving its name and row from `hooks` and `registrations` into `disabled`.
  - **Promote to MECHANISMS.md:** yes.

Add-on removal is not a new mechanism. It is the Preview-hash apply extension above.

---

## Extension Points

- `addon.json` of all three add-ons gains `uninstall_skill`. angular-tailwind changes to: `hooks: []`, `registrations: []`, `documents: [4 names]`, `stylesheet_snippet`, `disabled: [advisor entry with former_names]`, and no `kill_switches`.
- In `auto_improve_finish_install.py`:
  - `_read_addon_manifest` checks I-1 to I-3.
  - `_addon_file_ops` adds document operations (`copy` / `present` / `addon-file-differs`).
  - `_plan_addon` adds the profile edit (I-6), the `disabled-hook-present` check and the snippet step.
  - `build_parser` gains `--stylesheet` and `addon-remove`.
  - `_addon_listing` reports `uninstall-skill`.
- In `architecture-guard.py`:
  - `Violation` gains `rule_id` and `document`, filled from the Guard rule map.
  - The three output functions print the ID and the footer line.
  - `RX_INLINE_STYLE` honours C1(b).
  - A class-attribute `sticky` check covers any offset and emits `scroll-edge` (Q13). `relative` and `absolute` stay unchecked.
- In `_addon_fixture.py`: `KEY_DOCUMENTS`, `KEY_DISABLED`, `KEY_UNINSTALL_SKILL`, `KEY_SNIPPET`; `hook_files` allows an empty list; a new `install_disabled(add_on)`.
- `agents/angular-senior-dev.md` and `agents/ui-ux-designer.md` frontmatter: `skills: [angular-ui-rules]`, with the spelling settled by the t7 trial.

---

## Integration Surfaces

Not applicable. Reason: the work stays inside one layer, the plugin's own scripts, hooks, skills and markdown. No API, SignalR or DTO surface exists.

---

## Adjacent Areas

Not applicable. Reason: cross-area scan returned no signal above the threshold. `.claude/area-mapping.json` is the template with `"areas": {}`, so the scanner has no area to score. The scanner was not executed: this agent has no shell. Deferred items are recorded in `.claude/concepts/followups/2026-10-28-angular-tailwind-deferred-items.followup.md`.

---

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces (the plugin has no frontend roots).

---

## Chat Tool Impact

**No — UI/admin-only.** Justification: this contract adds no REST endpoint and no SignalR event, only scripts and markdown, so there is no surface a chat tool could wrap.

---

## Non-Goals

- Product look and feel, adoption in the consuming repository (step 3 of the issue), and project-specific rules.
- The guard weak spots no settled conflict depends on:
  - the hard-coded `projects` folder and `/ClientApp/`;
  - scanning only `*.component.*` files;
  - the `#add` hex false positive;
  - `relative` and `absolute` checks;
  - the multi-edit gap;
  - the height chain seen only in the edited fragment;
  - stylesheets that only warn;
  - documents and comments that point at the old global hooks folder (for example the guard's docstring `~/.claude/hooks/architecture-guard.exceptions.json`);
  - a design document that cites a reference path that does not exist.

  All go to the follow-up.
- The advisor's keyword `ui` that can never match. The hook is disabled; `DISABLED.md` records the defect for anyone who turns it back on.
- The guard's own `CLAUDE_ARCH_GUARD` switch (the guard is a default hook), and the kill switches of `codegraph` and `strict-shell-gate` (follow-up).
- Doctor drift for documents, and a doctor finding for a still-installed disabled hook (follow-up).
- The `python-ai` preload of `python-ai-developer`, which names a skill the plugin does not ship (follow-up).
- The source project's pattern enforcer. It does not ship in this plugin, and its rules read `not enforced`.
- The status badge, table rules beyond T-023, the card surface and `constrained-panel` (Q3).

---

## Confidence

Confidence: Medium.
- High: the manifest, checker, install and guard changes, all read in the code.
- Medium: the profile append and the text-preserving row removal, which are new splicing code.
- Low: whether the skill preload reaches a plugin subagent, and how its name is spelled. Neither is tested yet; the t7 trial decides, and the subagent-start hook is the fallback.

---

## Alternatives Considered & Why Rejected

- **A (chosen):** documents through the add-on install, a plugin skill preloaded by the agent, Rule IDs in guard messages, and the hook kept as a disabled entry.
  - Why: no program start on any prompt, the rules reach the subagent that writes the code, and the reminder appears exactly when a rule is broken.
- **B (rejected):** keep the prompt hook and narrow its keywords.
  - Why rejected: the hook has no matcher, so it still starts a program on every prompt (123 ms against a 50 ms bare start). It still may not reach the subagent, and the maintainer has already decided against it.
- **C (rejected):** deliver the rules through the session-start context mechanism.
  - Why rejected: it reaches every project, Angular or not, and spends context in every session.
- **D (rejected):** split the advisor into a fourth add-on.
  - Why rejected: it adds two more skills, it still writes a per-prompt row when installed, and nothing would clean old installs.
- **E (rejected for now):** project `.claude/rules/` files with path frontmatter.
  - Why rejected: whether they load, and whether they reach subagents, is unverified. The documents would also leave `review.documents`. This is recorded in the follow-up.

---

## Uncertain Assumptions

- `VERIFIED via auto_improve_finish_install.py:1837-1863`: the install script's checker does **not** read `kill_switches`. Line 2072 only echoes the list. It **does** require `hooks` and `registrations` to be non-empty.
- `VERIFIED via test_plugin_manifests.py:862-865`: the test-suite checker **requires** `kill_switches` to be a list, so a missing key fails today. t3 makes the key optional and keeps a control that rejects a non-`CLAUDE_*` entry.
- `VERIFIED via test_plugin_manifests.py:833-861`: rows are required to be non-empty, and every hook needs a row. This is why the disabled state cannot be expressed today.
- `VERIFIED via README.md:225-252`: there is no disabled-add-on precedent. README line 250 records the former name `architecture-advisor.py`.
- `VERIFIED via agents/ui-ux-designer.md:7-8, agents/python-ai-developer.md:7-8`: the `skills:` preload is used twice. Both name skills the plugin does not ship, and no tested preload exists.
- `VERIFIED via addon.json:9-15` and the advisor's `main()`: the hook is registered on `UserPromptSubmit` with no matcher. It starts on every prompt, and only its printing depends on the keywords.
- `VERIFIED via architecture-guard.py:186,280,428,455,476,500,531,544,569,770,795`: the rule names the guard emits, as listed in the Guard rule map.
- `VERIFIED via architecture-guard.py:441-453`: `style=` is matched one line at a time, which is why C1(b) requires the tag name on the same line.
- `VERIFIED via test_auto_improve_finish_install.py:3923-3925`: `WriterHarness` writes rows through the fake angular-tailwind spec. t3 moves it to strict-shell-gate.
- `VERIFIED via a Glob of .claude/hooks/`: no pattern-enforcer hook ships in this plugin.
- `ASSUMED`: the rows older installs carry under `architecture-advisor.py`. Expected: one prompt-submit row in a vendored `settings.json`, or one plugin-registered row in releases before 0.7.0. Matters because the removal must match them. Verification path: t4 reads the git history of `.claude/hooks/hooks.json` and of the add-on for every row that named either file, before freezing its fixtures, and t8's note lists the rows by install age.
- `ASSUMED`: an agent's `skills:` entry naming a plugin skill resolves under a plugin install. Verification path: the t7 live trial. The fallback is a `SubagentStart` row with the matcher `angular-senior-dev`, which costs one program start per subagent start and none per prompt.
- `ASSUMED`: Tailwind 4 `@apply sticky top-0 z-10` works in a global stylesheet that imports Tailwind. The t5 test checks only that the definitions exist; a consuming project's build is the proof.
- `ASSUMED`: "registry mirrors" in the acceptance criteria means the five version lines plus the generated registry digest (absent from this checkout). Verification path: the maintainer.

---

## Failure Modes & Mitigations

- **FM:** an old install keeps the advisor row, under either file name, after the upgrade.
  - **Mitigation:** the install refuses with `disabled-hook-present`, and the removal matches both names and removes the row, then the file (I-5, I-7).
- **FM:** the removal deletes the hook file before the row, so every prompt is blocked.
  - **Mitigation:** I-7, with a test that stops between the two writes.
- **FM:** a document drops a rule the hook printed.
  - **Mitigation:** the t2 coverage test, with a positive control.
- **FM:** the SVG exception lets colour through.
  - **Mitigation:** the property allow-list. Tests:
    - `style="fill:#fff; left:0"` on `<svg>`: blocks;
    - `style="left:0"` on `<g>`: allowed;
    - `style="left:0"` on `<text>`: allowed;
    - `style="left:0"` on `<div>`: blocks;
    - a `<rect` tag whose `style=` sits on the next line: blocks.
- **FM:** a project that never installed the add-on is pointed at a missing document.
  - **Mitigation:** the footer line checks for the file and falls back to the "not installed" line. Tests cover both cases.
- **FM:** a second install rewrites the profile or the stylesheet.
  - **Mitigation:** I-6 skips paths already listed, and selector detection sees the snippet already present. Tests run the install twice: a second preview with nothing to add, an apply that returns `nothing-to-do`, and a tree that is byte-identical afterwards.
- **FM:** the profile append corrupts the slot table.
  - **Mitigation:** reuse `_slot_rows` and `_format_value`, and test a placeholder slot, a `none` slot, an authored list, an already-listed path and a missing row.

---

## Open Questions for User

- [x] **Q1** Document destination. Answer: accept recommendation (`.claude/references/angular-tailwind/`). 2026-10-28.
- [x] **Q2** Group M as a fourth document. Answer: accept recommendation (ship `ANGULAR_MATERIAL_RULES.md`). 2026-10-28.
- [x] **Q3** Other candidate patterns. Answer: accept recommendation (ship the states pattern under A-025 and the error banner as P-001; defer the status badge, table rules beyond T-023, card surface and `constrained-panel`). 2026-10-28.
- [x] **Q4** Where the rule skill lives. Answer: accept recommendation (the plugin skill `skills/angular-ui-rules/`, with an absence clause). 2026-10-28.
- [x] **Q5** The `ui-ux-designer` preload. Answer: accept recommendation (repoint it to `angular-ui-rules` in t7). 2026-10-28.
- [x] **Q6** The upgrade path. Answer: accept recommendation (the install refuses `disabled-hook-present` until the uninstall has run). 2026-10-28.
- [x] **Q7** The snippet on uninstall. Answer: accept recommendation (leave it, and say so). 2026-10-28.
- [x] **Q8** Uninstall skills for the other add-ons. Answer: accept recommendation (all three, in t4). 2026-10-28.
- [x] **Q9** The response envelope. Answer: accept recommendation (a placeholder, with no new slot). 2026-10-28.
- [x] **Q10** The version. Answer: accept recommendation (0.9.22, bumped in t1; release notes in t8). 2026-10-28.
- [x] **Q11** The C1(b) exception. Answer: accept recommendation (the tag list and the positioning-property list, both required). 2026-10-28.
- [x] **Q12** `overflow-hidden`. Answer: accept recommendation (not in the snippet; documented as optional). 2026-10-28.
- [x] **Q13** `sticky`. Answer: accept recommendation (any offset is blocked in class attributes; `relative` and `absolute` stay unchecked). 2026-10-28.
- [x] **Q14** The layout nudge. Answer: accept recommendation (one advisory sentence in the skill). 2026-10-28.
- [x] **Q15** The advisor script. Answer: accept recommendation (drop the `CLAUDE_ARCH_ADVISOR` check; `released_sha256` lists every released copy). 2026-10-28.

---

## Critique

**Critic:** contract-critic
**Date:** 2026-10-28
**Verdict:** warnings-only

### Findings

- **[WARN] The cost is stated per matching prompt, but the hook starts on every prompt**
  - **What is wrong:** t3 (DISABLED.md) and t8 (timing) say "123 ms per matching prompt", but the hook is registered on `UserPromptSubmit` with no matcher. The program starts on every prompt and only its printing depends on the keywords.
  - **Prior artifact ignored:** issue #84 companion 2, "When it runs"; `.claude/addons/angular-tailwind/addon.json:9-15`; JOURNAL 2026-10-04 "Check a documented guard behaviour against the guard's code"
  - **Where in this contract:** `## Implementation Handoff` t3 — "123 ms per matching prompt against a 50 ms bare start"; t8 — "before, 123 ms per matching prompt"
  - → Addressed by: t3, t8, Alternative B and a VERIFIED entry now say the hook starts on every prompt (no matcher) and prints about 400 words only when a keyword matches.
- **[WARN] The Rule document set invariant contradicts the P rules**
  - **What is wrong:** P-nnn IDs are not catalogue IDs, yet the Rule ID term says "The IDs are the catalogue's IDs". P-001 (loading, empty and error states, Q3) also restates catalogue A-025, which breaks "No rule is written twice".
  - **Prior artifact ignored:** issue #84 companion 1, A-025; Proposal 1, "so no rule is written twice"
  - **Where in this contract:** `## Business Concept` — "Rule ID … The IDs are the catalogue's IDs from issue #84"; `## Data Shapes → Rule document set` — "No rule is written twice"; Q3
  - → Addressed by: Rule ID now defines `P` as a plugin-owned series that restates no catalogue rule. The states pattern sits under A-025 in `UI-UX-PATTERNS.md`, and P-001 is the error banner.
- **[WARN] I-6 rewrites authored slots without amending the Placeholder slot term**
  - **What is wrong:** I-6 appends to an authored list and replaces `none`. The registered term says an authored slot, `none` included, "is never changed" and is the only kind `/auto-improve-finish-install` may not write. No amendment to the term is proposed, so the registry would contradict the code.
  - **Prior artifact ignored:** `VOCABULARY.md:41` (Placeholder slot)
  - **Where in this contract:** `## Data Shapes → Commands` I-6 — "A slot that is a placeholder or reads `none` becomes the document list"; `## Reused Mechanisms` — "a stated, narrow extension"
  - → Addressed by: a Placeholder slot amendment (the `review.documents` exception for an add-on's own paths) is added under the new terms, and Reused Mechanisms cites it.
- **[WARN] Profile edits are not defined as idempotent, and the empty-after-removal value is undefined**
  - **What is wrong:** I-6 does not say that a path already listed is skipped. No handoff names a test that runs the install twice for the documents and the profile (t5 does it for the snippet only). The Removal plan also never says what the slot holds once the last entry is unregistered (`none` or a placeholder).
  - **Prior artifact ignored:** brief acceptance criterion "Failure path: running the install … twice … changes nothing"; `MECHANISMS.md:58` (Preview-hash apply: "writes nothing when there is nothing to add")
  - **Where in this contract:** `## Data Shapes → Commands` I-6; `## Value Objects` Removal plan — "document entries to unregister"
  - → Addressed by: I-6 now skips already-listed paths, writes no profile when there is nothing to add, and leaves `none` after the last removal. t3 names the install-twice test for documents and profile.
- **[WARN] The new "Add-on" term is false for two of the three add-ons**
  - **What is wrong:** the term says "No environment variable turns an add-on on or off". `codegraph` keeps `CLAUDE_SKIP_CG`, and `strict-shell-gate` keeps `CLAUDE_BASH_GATE` and `CLAUDE_CONCEPT_GATE`. t4 edits both manifests and leaves those switches. Decision 3 of the issue ("ordinary add-ons") is not settled for them in Non-Goals or in Open Questions, so the question is hidden.
  - **Prior artifact ignored:** `.claude/addons/codegraph/addon.json:37-39`; `.claude/addons/strict-shell-gate/addon.json:20-23`; `MECHANISMS.md:15` (`CLAUDE_SKIP_CG`, user only)
  - **Where in this contract:** `## Business Concept → New terms` — "Add-on … No environment variable turns an add-on on or off"; I-4 (angular-tailwind only)
  - → Addressed by: the term now allows declared human-only kill switches and says decision 3 is applied to angular-tailwind only. The other two keep theirs, recorded in Non-Goals and in the follow-up stub.
- **[WARN] Guard messages cite a document that exists only after the add-on is installed**
  - **What is wrong:** the guard is a default hook (Non-Goals), and the documents exist only after an install. No absence rule is stated for the guard message, though the skill gets one (Q4). A project that never installed the add-on is pointed at a missing file.
  - **Prior artifact ignored:** `MECHANISMS.md:69` (absence clause), `MECHANISMS.md:70` (a missing required read names the path it looked for)
  - **Where in this contract:** `## Value Objects` Guard violation — "`[<rule>] <rule_id> (<document>) line N`"; `## Non-Goals` — "The guard is a default hook"
  - → Addressed by: the Guard violation footer now names the installed path when the file exists, and otherwise prints a "not installed" line naming the install skill. A Failure Mode and t6 tests cover both.
- **[WARN] The precedence sentence refers to itself**
  - **What is wrong:** each document is itself a `review.documents` entry (I-6), yet it says "its `review.documents` entries win over this document". It does not say which wins between a shipped document and a document the project wrote.
  - **Prior artifact ignored:** JOURNAL 2026-10-05 "Text delivered to the model must say which rule wins against a skill's gate"
  - **Where in this contract:** `## Data Shapes → Entities` Add-on document — "the project's own instructions and its `review.documents` entries win over this document"
  - → Addressed by: the precedence text now reads: project instructions win; a document the project wrote and lists in `review.documents` wins over this plugin document; the guard's verdict is final for what it checks.
- **[WARN] C1 contradicts its own exception (a) and the guard's text**
  - **What is wrong:** "Colours, backgrounds and borders are never inline under any exception" conflicts with exception (a), which allows run-time `[style.prop]` bindings. It also conflicts with the guard's hex-colour suggestion to "bind to a computed signal that reads var(--mat-sys-*)" for SVG charts, which t6 leaves unchanged.
  - **Prior artifact ignored:** `.claude/hooks/architecture-guard.py:489-493`; JOURNAL 2026-10-04 "Check a documented guard behaviour against the guard's code"
  - **Where in this contract:** `## Data Shapes → Settled rule texts` C1
  - → Addressed by: C1 now limits the colour ban to static `style`. A run-time binding may carry a token-derived chart colour, as the guard's suggestion says, and a fixed theme colour is a utility class (T-002).
- **[WARN] The C1(b) loosening has no failure mode for child elements or tags that span lines**
  - **What is wrong:** "a static `style` on an SVG element or on `<canvas>`" does not say whether SVG children (`<g>`, `<text>`, `<rect>`) count, which is where positioning usually sits. The guard also matches `style=` one line at a time, so a tag that spans lines hides its tag name. Neither case appears in Failure Modes. The only test plants the style on `<svg>`.
  - **Prior artifact ignored:** `.claude/hooks/architecture-guard.py:341,453`; JOURNAL 2026-10-17 "Loosening a guard rule must be checked against the guard's own test fixtures"
  - **Where in this contract:** `## Failure Modes & Mitigations` — "A test plants `style=\"fill:#fff; left:0\"` on `<svg>`"; Q11
  - → Addressed by: C1(b) now lists the SVG child tags, requires the tag name on the same line as `style=`, and adds Failure Mode tests for `<g>`, `<text>`, `<div>` and a split `<rect` tag.
- **[WARN] The guard rule map uses rule names the guard does not emit**
  - **What is wrong:** the guard emits `gray-utility:<label>`, `app-banned-class:<cls>` and `height-chain-warn:scroll-edge-no-root-height`. The map keys are "gray-utility", "per-app banned" and "height-chain", and how keys match (exact or by prefix) is not stated.
  - **Prior artifact ignored:** `.claude/hooks/architecture-guard.py:280,428,476,569`; JOURNAL 2026-10-04 "Check a documented guard behaviour against the guard's code"
  - **Where in this contract:** `## Implementation Handoff` t6 — "gray-utility T-003; … height-chain T-014; per-app banned T-022"
  - → Addressed by: a Guard rule map section now lists exact names and `gray-utility:`, `app-banned-class:`, `height-chain-warn:` and `external:` prefixes, verified against the guard's line numbers.
- **[WARN] The upgrade description skips the hook's former file name**
  - **What is wrong:** the hook was `architecture-advisor.py` before it was renamed. The Disabled hook entry carries one `hook` name, so neither `disabled-hook-present` nor `addon-remove` recognises a row that names the old file. The upgrade note describes only installs since 0.9.9.
  - **Prior artifact ignored:** `README.md:250` ("formerly `architecture-advisor.py`"); JOURNAL 2026-10-22 "Describe a broken install by the rows each install age really has"
  - **Where in this contract:** `## Lessons referenced` — "one `UserPromptSubmit` row since 0.9.9"; `## Data Shapes` Disabled hook entry
  - → Addressed by: the Disabled hook entry gains `former_names: ["architecture-advisor.py"]`. Both the refusal and the removal match it, t4 reads git history for every row form, and t8's note covers both install ages.
- **[WARN] Add-on removal is promoted as a separate mechanism on a justification the registry does not contain**
  - **What is wrong:** the justification cites a Preview-hash apply invariant, "never removes a row or a file", that does not appear in the registry entry. The entry's Extend-by line describes exactly this seam (a new subcommand that returns the same plan, apply and refusal dicts). The contract also lists the same change under Reused Mechanisms as an extension.
  - **Prior artifact ignored:** `MECHANISMS.md:58` (Preview-hash apply, "Extend by")
  - **Where in this contract:** `## New Mechanisms` Add-on removal — "the Preview-hash apply invariant is 'never removes a row or a file'"
  - → Addressed by: Add-on removal is removed from New Mechanisms and recorded as the Preview-hash apply extension through its own Extend-by seam. I-7 and I-8 are its stated invariants.
- **[NIT] No handoff tests acceptance criterion 2** — no TASK block asserts that a project that never ran the install gets neither the hook nor the documents.
  - → Addressed by: invariant I-10 and a named t3 test for a project that never ran the install.
- **[NIT] "Vendored-asset drift — consumed unchanged" is not accurate** — `plugin_doctor.py:517,535` read the manifest's `hooks` list, so `hooks: []` stops the presence-based comparison of old advisor copies. The follow-up stub records the effect, but Reused Mechanisms says the mechanism does not change.
  - → Addressed by: Reused Mechanisms now says "consumed, with one known effect" and names the loss of presence detection.
- **[NIT] Two weak spots from the issue are not recorded** — "documents and comments point at a global hooks folder … one design document cites a reference path that does not exist" and the `ui` keyword appear in neither Non-Goals nor the follow-up stub.
  - → Addressed by: both weak spots and the `ui` keyword are added to Non-Goals and the follow-up stub, and `DISABLED.md` records the keyword defect.
- **[NIT] The pattern enforcer is never mentioned** — the issue asks whether it ships. It does not ship (`.claude/hooks/` has no such hook), so catalogue rules it enforced (A-002, A-004, A-006, A-011, A-012) must read "not enforced", and the contract never says so.
  - → Addressed by: the Rule entry shape, a VERIFIED entry, Non-Goals and the t1 constraint now state that those five rules read `not enforced`.
- **[NIT] The removal's line-ending handling is stated for one comparison only** — I-8's "identical to the plugin's copy" does not state the fold that `released_sha256` uses. The failure is safe (the file is kept as `kept-differs`).
  - → Addressed by: I-8 defines "identical" through `_fold_text_bytes`, the same fold `released_sha256` uses.
- **[NIT] Chat Tool Impact does not use a sanctioned answer** — it reads "2. No. Reason: …" instead of `No — UI/admin-only with justification`. There is no endpoint, so this is not a blocker.
  - → Addressed by: Chat Tool Impact now reads "No — UI/admin-only" with a one-line justification.

### Applicable journal entries

- **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work** — heeded by the t7 live trial of the `skills:` preload spelling
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by `## Failure Modes` (tests for a placeholder slot, a `none` slot and a missing row)
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — partly heeded (t2's "Enforced by" check); see the timing, C1 and rule-map WARNs
- **2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control** — heeded by t2
- **2026-10-05 — Text delivered to the model must say which rule wins against a skill's gate** — heeded in form; see the precedence WARN
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded by t4
- **2026-10-15 — A script that reads a project-owned file must be told which project** — heeded by the `--project` payload
- **2026-10-16 — A "missing project file" refusal must cover both the unset root and the set-but-absent file** — heeded by `profile-slot-missing` ("no profile, or no `review.documents` row")
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** — heeded by t6; see the C1(b) WARN
- **2026-10-17 — Judge "identical to master" by git's view, not raw bytes, on Windows** — partly heeded (`released_sha256` folds line endings); see the NIT
- **2026-10-22 — Describe a broken install by the rows each install age really has** — partly heeded; see the former-file-name WARN
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — heeded by the approval note in `## Lessons referenced`

### What the critic did not check

- `INTEGRATION.md` is absent, and no registry has a project tier, so only the Universal tiers were checked.
- `derive_area.py` was not run. `.claude/area-mapping.json` holds `"areas": {}`, so a fallback-only result is assumed.
- The contract's size against its 12,000-token budget was not measured.
- No north-star folder exists, so checklist item 13 does not apply.

---

## Lessons referenced

- **2026-10-22 — Describe a broken install by the rows each install age really has** — heeded by I-5, I-7, `former_names`, Q6 and t8's upgrade note. The note lists the rows of add-on installs since 0.9.9, and of older installs that name `architecture-advisor.py`, as read from git history in t4.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** — heeded by t6. It runs `test_architecture_guard_scss.py` and `test_hook_data_files_project_first.py` unchanged and adds the C1(b) child-tag and split-tag rows.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded by the Guard rule map (verified against the emitted names), by the corrected timing statements, and by the "Enforced by" check in t2.
- **2026-10-05 — Text delivered to the model must say which rule wins against a skill's gate** — heeded by the precedence paragraph in every document and in the skill.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded by t4.
- **2026-10-17 — Judge "identical to master" by git's view, not raw bytes, on Windows** — heeded by I-8's single fold.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — heeded by this revision: each answer and each addressed finding is written into Data Shapes, the invariants or the handoff.
- **2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control** — heeded by t2.
- Orthogonal to north-stars: none active.

---

## Implementation Handoff

### 1. Rule documents (`ui-ux-designer`)

**Depends on:** none

**Files to touch:**
- `.claude/addons/angular-tailwind/documents/ANGULAR_CODE_RULES.md`
- `.claude/addons/angular-tailwind/documents/ANGULAR_MATERIAL_RULES.md`
- `.claude/addons/angular-tailwind/documents/TAILWINDCSS_RULES.md`
- `.claude/addons/angular-tailwind/documents/UI-UX-PATTERNS.md`
- `.claude/addons/angular-tailwind/snippets/scroll-edge.scss`
- `skills/website-design/references/foundation.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.cursor-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

**Pre-written TASK block:**
```
TASK: Write the four rule documents and the scroll-edge snippet from issue #84 companion 1, and bump the version.
CONTEXT: concept contract at .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md; the full issue text is quoted in its brief.
FILES: as listed.
CONSTRAINTS:
  - One "### <ID> — <title>" heading per catalogue ID, in the Rule entry shape.
  - A-025 (with the states markup) goes in UI-UX-PATTERNS.md. P-001 is the error banner. No P rule restates a catalogue rule.
  - A-002, A-004, A-006, A-011 and A-012 read "not enforced" (the pattern enforcer does not ship).
  - Use C1-C6 in meaning, including the C1(b) tag and property lists, and the precedence paragraph word for word.
  - TAILWINDCSS_RULES.md holds the snippet, where it goes, the table and plain-list usage markup, the height rule
    (T-014), the Ionic note (nested regions only; ion-content scrolls the page) and the install step.
  - foundation.md: reword only the "Inline Style Elimination" paragraph (C1) and the !important line (C3).
  - Version 0.9.22 in the four manifest files (Q10).
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
  contract_status: approved
```

### 2. Coverage test (`senior-test-engineer`)

**Depends on:** 1

**Files to touch:**
- `.claude/hooks/tests/test_angular_rule_coverage.py`

**Pre-written TASK block:**
```
TASK: Write the drift test proving that every rule the old hook printed is in the shipped documents.
CONTEXT: concept contract (Coverage row, Rule document set, Rule ID).
FILES: as listed.
CONSTRAINTS:
  - Read REMINDER and DESIGN_NUDGE from the kept advisor script with ast (never import it).
  - The coverage rows are companion 2's map, verbatim, as data. Each row asserts its IDs and literal fragments.
  - Also assert: every catalogue ID appears once across the set; P IDs are unique; every document has the boundary
    paragraph and the precedence paragraph word for word; no document carries a planted project token (the positive
    control uses a made-up name).
  - A positive control deletes one rule from a temporary copy and expects the failure to name it. No row is skipped.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
  contract_status: approved
```

### 3. Manifest and install (`python-ai-developer`)

**Depends on:** 1

**Files to touch:**
- `.claude/addons/angular-tailwind/addon.json`
- `.claude/addons/angular-tailwind/DISABLED.md`
- `.claude/addons/angular-tailwind/hooks/angular-tailwind-advisor.py`
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `.claude/scripts/tests/test_plugin_manifests.py`
- `.claude/hooks/tests/_addon_fixture.py`
- `.claude/hooks/tests/test_addons.py`
- `skills/auto-improve-angular-tailwind-install/SKILL.md`

**Pre-written TASK block:**
```
TASK: Extend the add-on manifest and the install with documents, profile registration and disabled hooks, and drop
the kill switch.
CONTEXT: concept contract (Add-on manifest, Disabled hook entry, I-1 to I-6, I-9, I-10, the Install command).
FILES: as listed.
CONSTRAINTS:
  - Checkers: I-1 to I-3 in _read_addon_manifest and in addon_problems. kill_switches is optional.
    "_all_addon_hook_files" counts disabled hooks and former names.
  - Documents copy to .claude/references/angular-tailwind/ and are registered under I-6. Refusals: profile-slot-missing
    and disabled-hook-present (matches hook and former_names). The plan hash covers the profile bytes.
  - The advisor script loses only its CLAUDE_ARCH_ADVISOR check and docstring lines. released_sha256 is computed with
    _fold_text_bytes over every git revision of the file under both names.
  - DISABLED.md: what it did; its cost (a Python start on EVERY prompt, since it is registered on UserPromptSubmit with
    no matcher, 123 ms median against a 50 ms bare start on one Windows workstation, plus about 400 words of context
    when a keyword matched); why it is off; the dead "ui" keyword; how to turn it back on.
  - Tests:
    - a project that never ran the install has no documents, no rows and an unchanged profile (I-10);
    - install twice: the second preview adds nothing, the apply returns nothing-to-do, the tree is byte-identical;
    - slot cases: placeholder, none, authored list, already-listed path, missing row.
  - test_addons: the advisor tests install through af.install_disabled. WriterHarness moves to strict-shell-gate.
  - The install skill text: documents, profile, no kill switch, the new refusals.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
  contract_status: approved
```

### 4. Add-on removal (`python-ai-developer`)

**Depends on:** 3

**Files to touch:**
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `.claude/scripts/tests/test_plugin_manifests.py`
- `.claude/hooks/tests/_addon_fixture.py`
- `.claude/addons/angular-tailwind/addon.json`
- `.claude/addons/codegraph/addon.json`
- `.claude/addons/strict-shell-gate/addon.json`
- `skills/auto-improve-angular-tailwind-uninstall/SKILL.md`
- `skills/auto-improve-codegraph-uninstall/SKILL.md`
- `skills/auto-improve-strict-shell-gate-uninstall/SKILL.md`
- `skills/auto-improve-angular-tailwind-install/SKILL.md`
- `skills/auto-improve-codegraph-install/SKILL.md`
- `skills/auto-improve-strict-shell-gate-install/SKILL.md`

**Pre-written TASK block:**
```
TASK: Add the addon-remove subcommand (the Preview-hash apply extension) and one uninstall skill per add-on.
CONTEXT: concept contract (Removal plan, I-6 to I-8, Q6-Q8, the ASSUMED rows under architecture-advisor.py).
FILES: as listed.
CONSTRAINTS:
  - Before writing fixtures, read the git history of .claude/hooks/hooks.json and of the add-on for every row that
    named angular-tailwind-advisor.py or architecture-advisor.py, and build one fixture per row form.
  - Preview, then apply with plan-sha256. Rows go first (with a backup), then the profile (the slot becomes none when
    empty), then the files. A second run returns nothing-to-do with a byte-identical tree.
  - Delete only files that are identical after the fold or match a released hash. Never delete helpers or the snippet.
    The kill switches of codegraph and strict-shell-gate are left as they are.
  - The uninstall skills copy the install skill's Step 0 lookup block unchanged. Run test_skill_script_lookup.py.
  - Tests: twice-run; a differing file kept; old installs under both names cleaned; a missing profile slot;
    rows-before-files ordering.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
  contract_status: approved
```

### 5. Stylesheet snippet install (`python-ai-developer`)

**Depends on:** 4

**Files to touch:**
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `skills/auto-improve-angular-tailwind-install/SKILL.md`

**Pre-written TASK block:**
```
TASK: Add the --stylesheet step that appends the scroll-edge snippet when the classes are missing.
CONTEXT: concept contract (Stylesheet snippet, I-9, Q7, Q12).
FILES: as listed.
CONSTRAINTS:
  - With no --stylesheet, the plan lists candidates (<each frontend.roots entry>/src/styles.scss or .css that exists)
    and writes nothing.
  - All three classes defined: present. None defined: append at the end, inside the markers. Some defined:
    stylesheet-partial-snippet.
  - Tests: all three definitions exist after the install; a second install changes nothing (byte-identical);
    a pre-existing project definition is reported as present.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
  contract_status: approved
```

### 6. Guard messages (`python-ai-developer`)

**Depends on:** 1

**Files to touch:**
- `.claude/hooks/architecture-guard.py`
- `.claude/hooks/tests/test_architecture_guard_messages.py`

**Pre-written TASK block:**
```
TASK: Make every guard block and warn line name its Rule ID, with a document footer that degrades when the document
is absent, and honour C1(b) and the sticky rule.
CONTEXT: concept contract (Guard rule map, Guard violation, C1, C4, Q11, Q13).
FILES: as listed.
CONSTRAINTS:
  - Match exact names and prefixes exactly as the Guard rule map states.
  - The footer names <project>/.claude/references/angular-tailwind/<doc> only when that file exists. Otherwise it
    prints the "not installed" line. Test both.
  - C1(b) tests: <svg> with fill blocks; <g> and <text> with left:0 are allowed; <div> with left:0 blocks; a split
    <rect tag blocks. Sticky: "sticky top-4" in a class attribute blocks; the word sticky in text does not.
  - Every mapped ID exists as a heading in the shipped documents. The inline-style suggestion stops citing w-[200px].
  - Run test_architecture_guard_scss.py and test_hook_data_files_project_first.py unchanged.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
  contract_status: approved
```

### 7. Agent rule delivery (`python-ai-developer`)

**Depends on:** 1

**Files to touch:**
- `skills/angular-ui-rules/SKILL.md`
- `agents/angular-senior-dev.md`
- `agents/ui-ux-designer.md`
- `.claude/scripts/tests/test_angular_rule_delivery.py`

**Pre-written TASK block:**
```
TASK: Ship the angular-ui-rules skill and preload it in both Angular agents. Prove delivery with a live trial.
CONTEXT: concept contract (Rule skill, Q4, Q5, Q14, C5, ASSUMED preload).
FILES: as listed.
CONSTRAINTS:
  - The skill content is exactly as the Rule skill section states.
  - angular-senior-dev: replace the inline rule list with the preload. Remove the project facts (isSuccess,
    /api/screeners/symbols) and the undeclared frontend.root-container slot (cite frontend.roots).
  - The test asserts: both agents' skills entries resolve to the plugin skill; the skill holds the sentinel, the
    precedence clause and the absence clause.
  - Trial (PowerShell): claude -p "Use the angular-senior-dev subagent; have it quote the first line of its preloaded
    skill" --output-format json. Bash: the same command. Try bare, then namespaced. Paste the output in the pull
    request. If both fail, stop and ask for a contract amendment for the SubagentStart fallback.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
  contract_status: approved
```

### 8. Release notes and upgrade path (`python-ai-developer`)

**Depends on:** 2, 3, 4, 5, 6, 7

**Files to touch:**
- `README.md`

**Pre-written TASK block:**
```
TASK: Write the 0.9.22 release note, the upgrade note, the timing record and the add-on table update.
CONTEXT: concept contract (Q6, Q10, Disabled hook entry, JOURNAL 2026-10-22).
FILES: README.md
CONSTRAINTS:
  - "Changed in 0.9.22": documents, the skill, guard Rule IDs and footer, uninstall skills, the disabled advisor.
  - Upgrade: list the rows each install age carries, as t4 found them (an add-on install since 0.9.9 has one
    UserPromptSubmit row on angular-tailwind-advisor.py; older installs name architecture-advisor.py). Run the
    uninstall skill, then the install skill, then start a new session.
  - Timing:
    - before: a Python start on every prompt (no matcher), 123 ms median of seven runs against a 50 ms bare start,
      measured once on one Windows workstation for issue #84, not re-measured;
    - after: no row on any per-prompt event, so no program starts for Angular rules. This is proven by the manifest
      checker and by the install test (zero UserPromptSubmit rows written), not by a timing run.
  - Say the kill switches of codegraph and strict-shell-gate are unchanged.
  - The README version line is 0.9.22. Update the skill list and counts.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
  contract_status: approved
```

### 9. Review (`fullstack-code-reviewer`)

**Depends on:** 8

**Files to touch:**
- `.claude/reviews/2026-10-28-angular-tailwind-rule-documents/t9-review-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review sub-tasks 1-8 against this contract and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
FILES: .claude/reviews/2026-10-28-angular-tailwind-rule-documents/t9-review-fullstack-code-reviewer.md
CONSTRAINTS:
  - Check: I-1 to I-10; C1-C6 in the shipped text; the Guard rule map; the coverage test is green; the trial evidence;
    the upgrade note under both file names; the version lines.
  - Write the six-section artefact. The file does NOT exist yet; you create it. Name the commit range base..head.
  - "## Evidence" lists the commands with their exit codes and is never empty.
  - The header ends with exactly one of: "**Verdict:** pass", "**Verdict:** pass-with-findings", "**Verdict:** blocked".
  - Write the Gate Output <artefact stem>.gate.json beside it, covering every Review checklist item.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
  contract_status: approved
```

---

## Review checklist (filled in after implementation)

- [ ] Implementation matches Data Shapes exactly
- [ ] Reused Mechanisms are actually reused (no parallel implementations introduced)
- [ ] New Mechanisms (if any) promoted to `MECHANISMS.md`
- [ ] New vocabulary terms promoted to `VOCABULARY.md`
- [ ] Integration surfaces reflected on both backend and frontend sides
- [ ] `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced
- [ ] No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface)
- [ ] `Status` flipped to `implemented`
