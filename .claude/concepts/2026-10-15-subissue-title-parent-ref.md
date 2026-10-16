# Concept Contract — Sub-issue titles carry their parent reference, and sub-issues can be hidden from the list

**Project:** claude-agentic-auto-improve
**Date:** 2026-10-15
**Requested by:** user
**Status:** approved
**Work Item Brief:** `.claude/work-items/2026-10-15-subissue-title-parent-ref.md`

> **Protocol:** filled in by `data-architect`. The lifecycle and the management commands are in `.claude/templates/concept-contract.md`.

---

## Business Concept

- **What is this thing, in domain language?**
  When `/flow` splits an approved contract into sub-tasks, `/task` (Parent-aware mode) opens one GitHub sub-issue per sub-task. Today that sub-issue's title is `[<TYPE>] <bare title>`, which names no parent. In a flat issue list, `[PERF] Screener (dotnet-backend-architect)` does not say which work item it belongs to. This contract adds a **Sub-issue title format** to the conventions file. It places the **Parent reference** (`P:#<n>`) and the **Sub-task ordinal** (`ST:<k>`) right after the effort tag, in the shape the user chose on 2026-10-16: `[PERF] P:#638 ST:16 - Fix Earnings Index (dotnet-backend-architect)`. `P` stands for the parent issue and `ST` for the sub-task, and the title must explain itself, so the legend is printed wherever the format is documented. Parent-aware mode builds every new sub-issue title from that format and refuses the create when no valid parent number or no valid sub-task ordinal is available. It never falls back to a title without the parent. Separately, the plugin tells the operator how to hide sub-issues from a list, and how to list one parent's children. GitHub already supports both through search qualifiers, so no new mechanism is needed.

- **Existing VOCABULARY.md terms that apply:**
  - **Merge direction** (Universal) — uses "sub-issue" and "parent branch" in the same sense this contract does.
  - **Flat worktree** / **Main checkout** (Universal) — not changed. They are named only because Parent-aware mode runs inside a flat worktree.
  - The terms "Parent Link" and "Sub-Task Work Item" appear in `parent-aware-mode.md` and `verify_parent_link.py` but are not in this repository's VOCABULARY.md. This contract uses them in the same sense and does not redefine them.

- **New terms proposed for VOCABULARY.md** (Universal tier, promoted after approval):
  - **Sub-issue title format** — the declared shape of a sub-issue's GitHub title, held once in `.claude/work-item-conventions.json` → `issueTitle.subIssue.format`. It is an `issueTitle` that also carries the Parent reference, so every sub-issue title still matches `issueTitle.pattern`. Only Parent-aware mode applies it, through `compose_subissue_title.py`.
  - **Parent reference** — the parent issue's number in a sub-issue title, written `P:#<n>` where `n` is a positive integer. GitHub turns the `#<n>` into a link. It is the number only, never the parent's title, because a number is stable and short, while a title can be edited and is long.
  - **Sub-task ordinal** — the position of the sub-task within the parent contract's plan, written `ST:<k>` where `k` is a positive integer (the `16` in sub-task `t16`). It is the ordinal and not the sub-issue's own number, because the title is composed before GitHub creates the issue, so that number does not exist yet (see OQ-4).

---

## End-User View

Not applicable. Reason: `Files to touch` has no Angular UI surface (component, template, stylesheet, state service, route or shared layout). The only visible change is the text of a GitHub issue title, which the Business Concept describes.

---

## Data Shapes

### Entities

| Name | Fields | Invariants | Ownership (aggregate) |
|------|--------|------------|-----------------------|
| (none new) | — | — | The GitHub sub-issue is an existing tracker record. This contract changes only the title string it is created with. |

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| **Sub-issue title format** (conventions block `issueTitle.subIssue`) | `$comment` (string). `legend` (string, the one-line explanation of `P` and `ST` that docs and the refusal remediation print). `format` (string template, `"[<EFFORT>] P:#<parent> ST:<subtask> - <Title>"`, chosen by the user, OQ-1). **Invariants:** the template holds each of `<EFFORT>`, `<parent>`, `<subtask>`, `<Title>` exactly once; it begins with `[<EFFORT>]`; any title rendered from it with a declared tag matches `issueTitle.pattern`. It carries no effort list and no regex of its own: the effort list and pattern stay in `issueTitle`, and restating them would create a second copy. | The single source of truth for the sub-issue title. It is read at call time by the helper and is never written as a literal in a skill. |
| **Parent reference input** | `raw` (string as supplied by `PARENT_ISSUE`) | Normalised by trimming surrounding whitespace and removing at most **one** leading `#`. What remains must be digits only, with an integer value ≥ 1. Accepted: `638`, `#638`, ` 638 `. Refused: empty, `#`, `##638`, `0`, `-3`, `638.0`, `abc`, `owner/repo#638`. |
| **Sub-task ordinal input** | `raw` (string as supplied) | Trimmed, then digits only with an integer value ≥ 1. Accepted: `16`, ` 3 `. Refused: empty, `0`, `-1`, `t16`, `16.0`. The caller derives it from the sub-task id in the contract's handoff plan (`t16` gives `16`); the helper does not parse contracts. |
| **Title composition request** | `effortTag` (enum, from Step 2.5's classification), `parent` (Parent reference input), `subTask` (Sub-task ordinal input), `bareTitle` (string, the sub-task name with no effort tag) | The helper's input. **Invariants:** `bareTitle` is trimmed; empty or whitespace-only, containing a line break or other control character, or already starting with an effort tag (`exactlyOne`) is refused as `bare-title-invalid`. `effortTag` is checked against `issueTitle.effortTypes` before rendering, and an undeclared tag is `pattern-mismatch`. The composed title is handed to `gh` through a shell variable filled from the helper's JSON and expanded inside double quotes (`--title "$TITLE"`), never spliced into the command text, so quotes, backticks and `$` in a bare title cannot alter the command. |
| **Title composition result** | `verdict` (enum: `composed` \| `refused`), `title` (string, present only when `composed`), `cause` (enum, present only when `refused`), `reason` (string), `remediation` (string, optional) | The helper's JSON output. Parent-aware mode branches on `verdict`. |
| **Refusal cause** (closed set, ordered — first match wins) | `conventions-missing` (file, `issueTitle` or `issueTitle.subIssue.format` absent/unreadable) → `format-malformed` (a placeholder missing or repeated, or not led by `[<EFFORT>]`) → `parent-missing` → `parent-not-positive-integer` → `subtask-missing` → `subtask-not-positive-integer` → `bare-title-invalid` → `pattern-mismatch` (the rendered title fails `issueTitle.pattern`, e.g. an undeclared tag) | Every refusal is named. No refusal path ever outputs a `title`. |

**Contract-wide invariants:**

- **I-1** Every `composed` title contains `P:#<n>` and `ST:<k>`, where `n` is the normalised parent and `k` the validated sub-task ordinal, and matches `issueTitle.pattern`.
- **I-2** A refusal never comes with a title. Neither the helper nor Parent-aware mode falls back to the old `[<TYPE>] <bare title>` shape. A refusal halts the create, and nothing is created.
- **I-3** The format is read from the conventions file at call time. Changing the fixture's `format` changes the output, and a test proves this. `parent-aware-mode.md` names the block and the helper and does not restate the template.
- **I-4** The helper is pure. It makes no `gh` call, writes no file and mutates no tracker record.
- **I-5** The brief's `title:` stays the **bare** sub-task name. The parent number lives only in `parent_issue:`, as today. A brief written in Parent-aware mode therefore never carries the Parent reference into `/ship`'s pull request title. (A later no-parent `/task` run on a sub-issue keeps the `P:#n ST:k` remainder as the bare title, so there it does reach the pull request title; that is accepted and stated in Failure Modes.)
- **I-6** The conventions file is read from an explicit `--conventions` path that a test can redirect. **Plugin-install guard:** Parent-aware mode passes `--conventions <project .claude/work-item-conventions.json>` explicitly. When `--conventions` is absent, the helper reads exactly `<CLAUDE_PROJECT_DIR>/.claude/work-item-conventions.json` and never the shared multi-root locator, so it cannot fall through to the plugin's own file. It refuses `conventions-missing` with the reason "project conventions root not determinable" when `CLAUDE_PROJECT_DIR` is unset, and with the reason naming the missing path when it is set but the project has no such file. Tests cover both cases. *(Amended after implementation review, 2026-10-16: the first draft only covered the unset case; the reviewer showed the variable set with no project file still read the plugin's file. This replaces the use of `work_item_conventions_path()` for the helper's own fallback.)*

### Events

| Name (past tense) | Emitter | Listeners | Payload |
|-------------------|---------|-----------|---------|
| (none) | — | — | Not applicable. Reason: the helper is a synchronous pure function with no subscribers. The create stays a request read back by the existing Parent Link check. |

### Commands (if any)

| Name (imperative) | Handler | Payload | Possible rejections |
|-------------------|---------|---------|---------------------|
| Compose sub-issue title | `.claude/scripts/compose_subissue_title.py` (CLI `--type <TAG> --parent <raw> --subtask <raw> --title <bare> [--json] [--conventions <path>]`. Exit 0 = composed, 2 = refused, the same halting exit code as `verify_parent_link.py`) | Title composition request | The eight Refusal causes, in the order above |

---

## Reused Mechanisms

- **Two-layer Claude path resolution** — deliberately NOT used by the helper (amended after implementation review, 2026-10-16). `verify_parent_link.py` reads the conventions file through `work_item_conventions_path()`. The new helper cannot, because under a plugin install that locator ranks the plugin's own folder ahead of the consumer's when the project variable is unset or the project has no file, and the `conventions-missing` refusal would never fire. The helper reads an explicit `--conventions` path, or exactly `<CLAUDE_PROJECT_DIR>/.claude/work-item-conventions.json`.
- **Conventions file as single source of truth** (`.claude/work-item-conventions.json`, `issueTitle` block, read by `/task` Step 2.5 and `/ship`) — **extended by** a nested `issueTitle.subIssue` block. Nesting it under `issueTitle` follows the `issueLink.parentLink` precedent: a nested block owns only what is new, and the outer block keeps the effort list and `pattern`. **Enum coverage check:** the effort tags are not touched, and `pattern` already accepts `[PERF] #638 - …` because `.+` follows the tag, and the same holds for `[PERF] P:#638 ST:16 - Fix Earnings Index (…)`. Verified by reading the regex.
- **Fail-loud conventions read** (INV-9 of `verify_parent_link.py`: a missing block returns a named `conventions-missing` cause, never a hard-coded fallback) — consumed as-is, as a pattern. The helper copies the same rule and the same cause name.
- **Parent-aware mode's script lookup** (the VPL resolution block in `parent-aware-mode.md`, handling either install mode) — **extended**, not duplicated. The block moves above the create, and the helper path is derived as the sibling of the resolved `VPL` in the same folder. A sibling that is missing (an older vendored copy) halts loud.
- **Plugin registry ownership model** — consumed as-is. The conventions file is project-authored (`plugin_doctor.py` scaffolds it with `authored=True` and never overwrites it), so an existing consumer does not receive the new block by sync. OQ-2 decides what happens then, and the Failure Modes cover it.
- **Skill-prose sync test** (`test_ship_skill_sync.py` pins `/ship` prose against `verify_issue_link.py`) — consumed as a pattern. The new suite pins `parent-aware-mode.md` against the helper: the prose names the helper, does not restate the template, and names every refusal cause.
- **Version-bump checker** (`check_version_bump.py`) — consumed as-is. All five manifest version entries move together.

---

## New Mechanisms (if any)

None. `compose_subissue_title.py` is a new **instance** of the shape `verify_parent_link.py` and `flat_worktree.py` already use: a small script that reads conventions, is the one tested way to do a skill step, and returns a closed-set verdict. It is not new machinery. Promotion to MECHANISMS.md: no.

**Why a helper rather than prose only (the intake's open question).** A prose-only change would have the model put three values into a template and validate a parent number in its head. Two acceptance criteria cannot be met that way. First, "a test asserts the composed title" for the normal case, the leading-`#` case and the refusal case: a test cannot assert what a model does with prose. Second, "refused with a named reason" needs a closed refusal vocabulary that something enforces. MECHANISMS.md's **Flat worktree helper** entry states the house rule this follows: when a skill step must be exactly right, it becomes "the one tested way", and the skill calls the script. A prose-only change would also put the template's shape back into `parent-aware-mode.md`, the second place AC-3 forbids.

---

## Extension Points

- `.claude/work-item-conventions.json` → add `issueTitle.subIssue` with `$comment` and `format`. The `$comment` names the helper as its reader and says that the effort list and pattern stay in the outer block.
- `.claude/scripts/plugin_doctor.py` → `SCAFFOLDS[".claude/work-item-conventions.json"]["issueTitle"]` gains the same `subIssue` block. This is the repository's second copy of the conventions shape (AC-7). Its separate missing-`parentLink` gap is deferred (see Adjacent Areas).
- `skills/task/references/parent-aware-mode.md`:
  - "Order of operations" gains a step between classify and create: **compose the title**. A `refused` result halts, names the cause, and creates nothing.
  - The script lookup block moves above the create.
  - The `gh issue create` line takes `--title "<the helper's composed title>"` instead of the literal template.
  - A short refusal table follows, in the same style as the four-verdict table.
- `skills/task/SKILL.md` → Step 2.5 gets one sentence: a sub-issue title (Parent-aware mode) adds the Parent reference through `issueTitle.subIssue`, and the brief's `title:` stays bare. It does not restate the format.
- `skills/flow/SKILL.md` → after step 4 ("Roll up"), add a short operator note titled "Finding sub-issues in the issue list":
  - the legend, printed once: `P` = parent issue, `ST` = sub-task (its position in the parent's plan), read from `issueTitle.subIssue.legend`
  - hide sub-issues: `gh issue list --search "no:parent-issue"`
  - list one parent's children: `gh issue list --search "parent-issue:<owner>/<repo>#<n>"`
  - or the `parentLink.parentListCommand` the conventions file already declares. The note cites it by name and does not restate it.
- Manifests: `plugin.json`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.claude-plugin/marketplace.json` (two entries) → `0.9.1`.

---

## Integration Surfaces

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---------------|---------------|-----------|------------|-----------|
| `/task` Parent-aware mode | `compose_subissue_title.py` | subprocess, JSON on stdout, exit code | Title composition request / result | skill → script → skill |
| `compose_subissue_title.py` | `.claude/work-item-conventions.json` | file read from the explicit `--conventions` path, or `<CLAUDE_PROJECT_DIR>/.claude/work-item-conventions.json` | Sub-issue title format | script reads config |
| `/task` Parent-aware mode | GitHub | `gh issue create --parent <n> --title <composed>` | issue title string | plugin → tracker |

**Changes to existing integration surfaces:**
- [ ] The `gh issue create` title argument in `skills/task/references/parent-aware-mode.md` now takes the helper's output. On the GitHub side the only change is the title string. No API shape changes and no C# or TypeScript side exists.

---

## Adjacent Areas

The cross-area scanner ran in the main session and found no adjacent areas: `.claude/area-mapping.json` declares an empty `areas` set, so every path maps to `uncategorized`. The architect found two adjacent items without the scanner:

| Area | Decision | Implication / Reason | Handle |
|------|----------|----------------------|--------|
| uncategorized — existing sub-issues in StockToolScalpingMachine | follow-up handle | The 37 existing sub-issues of #638 keep their old titles. The brief puts retitling them out of scope. | `.claude/concepts/followups/2026-10-15-retitle-existing-subissues.followup.md` |
| uncategorized — doctor scaffold of the conventions file | follow-up handle | The scaffold has no `issueLink.parentLink`, so a doctor-built project fails the Parent Link check. This defect existed before this work, in a block this contract does not own. | `.claude/concepts/followups/2026-10-15-doctor-scaffold-parentlink.followup.md` |

---

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces. The project has no `frontend.roots`, and the only change is a GitHub title string.

---

## Chat Tool Impact (REQUIRED when this contract adds or changes a REST endpoint or SignalR event)

Not applicable. Reason: no REST endpoint or SignalR event is added or changed.

---

## Non-Goals

- Retitling any existing issue, in this repository or another (follow-up stub).
- Changing how the bare title is derived from a handoff heading (e.g. `Gate (x) - t16-gate`).
- A `sub-task` label, a saved view, or any hiding mechanism beyond documenting GitHub's own `no:parent-issue` qualifier.
- Putting the parent's **title** into the sub-issue title.
- Changing `/ship`'s pull request title, the brief's `title:`, or `pr_merged.py` / `land_contract.py` title handling.
- Adding the missing `parentLink` block to the doctor's scaffold (follow-up stub).
- Syncing the new version into StockToolScalpingMachine's vendored copy.

---

## Confidence

Confidence: Medium. High on Data Shapes and reuse (verified against the conventions file, `verify_parent_link.py` and both skills). Medium on the `parent-issue:<owner>/<repo>#<n>` search qualifier, which was not run at intake (see Uncertain Assumptions). Raised to High once that qualifier has been run and its result recorded in the pull request.

---

## Alternatives Considered & Why Rejected

- **Option A (chosen):** nested `issueTitle.subIssue.format` template, rendered by a small pure helper with a closed refusal set, and called by Parent-aware mode before the create.
  - Why: one source of truth, testable for every acceptance case, and it follows two shipped precedents (`parentLink` nesting, `verify_parent_link.py`).
- **Option B (rejected):** prose only, with the template written inline in `parent-aware-mode.md`.
  - Why rejected: AC-5's test cannot assert prose, and the template would then live in a second place, which AC-3 forbids.
- **Option C (rejected):** a top-level `subIssueTitle` block with its own `pattern` and effort list.
  - Why rejected: it restates the effort list and pattern, and those two copies would drift, which is exactly what the conventions file's own `$comment` warns against.
- **Option D (rejected):** a built-in default format in the helper for when the block is missing.
  - Why rejected: it hides the template inside code, breaks the single source of truth and the INV-9 fail-loud precedent, and a stale consumer would get a format nobody declared.

---

## Uncertain Assumptions

- `VERIFIED via .claude/work-item-conventions.json:6`: `issueTitle.pattern` is `^\[(FEATURE|…|SPIKE)\] .+`, so `[PERF] #638 - Screener (dotnet-backend-architect)` matches.
- `VERIFIED via skills/task/references/parent-aware-mode.md:29-37,88`: the title is needed before the create and is currently built inline as `"[<TYPE>] <bare title>"`. The script lookup block sits after the create (lines 98-116) and must move.
- `VERIFIED via .claude/scripts/verify_parent_link.py:75,121-136`: conventions are read through `work_item_conventions_path()`, and a missing block returns `conventions-missing`.
- `VERIFIED via .claude/scripts/plugin_doctor.py:83-115`: the conventions file is scaffolded with `authored=True`, never overwritten, and the scaffold has no `parentLink` block.
- `VERIFIED via .claude/scripts/land_contract.py:1955-1962`: the landing pull request title comes from the parent brief's `title:`, not from any sub-issue title, so I-5 keeps it clean.
- `VERIFIED via .claude/scripts/check_version_bump.py:17-20`: four manifest files, five version entries, and `.claude/scripts/tests/` is exempt from the bump requirement.
- `VERIFIED at intake (Work Item Brief)`: `gh issue list --search "no:parent-issue"` hides sub-issues (66 results in StockToolScalpingMachine).
- `ASSUMED`: `gh issue list --search "parent-issue:<owner>/<repo>#<n>"` lists one parent's children. If wrong, the `/flow` note would teach a dead command. Verification path: the implementer runs it once, read-only, against a known parent (e.g. `lneninger/StockToolScalpingMachine#638`) and records the exit code and count in the pull request description. If it fails, the note keeps only the `parentListCommand` form.
- `ASSUMED`: no consumer parses sub-issue titles by position (e.g. assuming the bare title follows the tag directly). A search found only `land_contract.py`, which strips the tag from the parent brief's title. Verification path: the reviewer greps `skills/` and `.claude/scripts/` for `issueTitle` and `--json title`.

---

## Failure Modes & Mitigations

- **FM:** An existing consumer's project-owned conventions file lacks `issueTitle.subIssue`, so after upgrading, `/flow` cannot open sub-issues.
  - **Mitigation:** the helper refuses with `conventions-missing` and a remediation that names the exact block to add (INV-9 precedent). Never a silent old-style title. OQ-2 asks the user to confirm this trade-off.
- **FM:** A vendored copy carries `verify_parent_link.py` but not the new helper, so the lookup finds VPL and the sibling is absent.
  - **Mitigation:** Parent-aware mode checks the sibling exists and halts loud, naming the path and the fix: the consumer's sync configuration must list `.claude/scripts/compose_subissue_title.py` in its `files` array (a file no tree names is a local asset and is never synced). This follows JOURNAL 2026-10-04 "A root locator can return the consumer itself under vendoring": the helper is never looked up by a separate search that could resolve to a different copy.
- **FM:** A template edited to drop `<parent>` silently produces parent-less titles.
  - **Mitigation:** `format-malformed` refusal, tested.
- **FM:** A user-typed `#638` becomes `##638`.
  - **Mitigation:** normalisation strips at most one leading `#`. Tested as an accepted case, with `##638` tested as a refusal.
- **FM:** The bare title already carries ` - ` (`Gate (x) - t16-gate`), giving two separators.
  - **Mitigation:** the result is still parseable, because the Parent reference is fixed at the front. Changing the separator is a one-line conventions edit (OQ-1).
- **FM:** `/task` run later in no-parent mode on a sub-issue splits its title into the tag and `#638 - Screener …`, and Step 2.5 point 4 may offer to retitle it.
  - **Mitigation:** point 4 keeps the bare remainder as is, so the Parent reference survives. The reviewer verifies the Step 2.5 sentence added here says so.
- **FM:** The prose drifts from the helper's refusal set.
  - **Mitigation:** the skill-sync test asserts every cause in the helper's closed set is named in `parent-aware-mode.md`, and that the prose invents none.

---

## Open Questions for User

- [x] **OQ-1 — Title shape.** → **Answered by the user, 2026-10-16:** `[PERF] P:#638 ST:16 - Fix Earnings Index (dotnet-backend-architect)`, where `P` is the parent issue and `ST` is the sub-task, and "the title must be self-explanatory". This replaces the intake's `[TYPE] #<parent> - <bare title>`. Consequences taken into this contract: a second numeric input (the Sub-task ordinal) with its own two refusal causes, and a printed legend so a reader who has never seen the format can decode it. Many bare titles already contain ` - `, so a title can still carry two dashes; the template lives in the conventions file, so changing the separator later is a one-line edit.
- [x] **OQ-4 — What `ST:16` counts.** The user's wording was "ST: Sub-issue". The sub-issue's own number cannot appear in its title when the title is composed before GitHub creates the issue, so the contract reads `ST` as the sub-task's position in the parent's plan (`t16` gives `ST:16`). **Recommendation: keep this reading.** It stays stable, it matches the `t16` ids already in the bare titles, and it needs no second edit after the create. The alternative, writing the real sub-issue number, needs a create-then-retitle round trip and leaves a window where the issue has the old-style title. Please confirm or correct. → **Answered by the user, 2026-10-16: approved as recommended (`ST` is the sub-task ordinal).**
- [x] **OQ-2 — A project whose conventions file has no sub-issue format yet.** The conventions file is owned by each project and is not updated by sync, so StockToolScalpingMachine will lack the new block until someone adds it. Options: (a) refuse to open the sub-issue, naming the missing block and showing what to paste; (b) quietly build the title from a default written inside the script. **Recommendation: (a).** The brief forbids any title without the parent reference. A hidden default is a second copy of the format. And (a) matches how the Parent Link check already behaves when its block is missing. The cost is one paste per consuming project on upgrade. → **Answered by the user, 2026-10-16: approved as recommended (a).**
- [x] **OQ-3 — Helper script or prose only.** **Recommendation: helper script** (`compose_subissue_title.py`). The acceptance test for the composed title and the named refusal can only be written against code, and prose would put the format back into the skill. The full reasoning is in "New Mechanisms". → **Answered by the user, 2026-10-16: approved as recommended (helper script).**

---

## Critique

**Critic:** contract-critic
**Date:** 2026-10-15
**Verdict:** warnings-only

### Findings

- **[WARN] The conventions read can land on the plugin's own conventions file, which bypasses OQ-2's fail-loud path**
  - **What is wrong:** `work_item_conventions_path()` is `_first_root_containing("work-item-conventions.json")` (`.claude/hooks/_project_paths.py:225-234`), and rank 1 of `claude_roots()` is `SELF_ROOT`, the `.claude` folder the resolver itself sits in (`_project_paths.py:44,76`). Under a plugin install, the helper runs from the plugin cache. If `CLAUDE_PROJECT_DIR` is unset in the shell that runs it, rank 0 is absent, so the plugin's own conventions file wins over the consumer's. That file will carry the new `issueTitle.subIssue` block. The consumer's missing block then never produces `conventions-missing`, and the consumer's own `issueTitle.pattern` is silently replaced by the plugin's. I-6 and OQ-2 both assume the consumer's file is the one read. No test covers the plugin-install case.
  - **Prior artifact ignored:** `MECHANISMS.md:42` (Two-layer Claude path resolution: the selection rule and rank 1 `SELF_ROOT`). `VOCABULARY.md:29` (Claude data root: rank 0 is "unset in a plain shell"). `JOURNAL.md` 2026-10-04 "A root locator can return the consumer itself under vendoring" (the reverse case: here the locator returns the plugin itself). `JOURNAL.md` 2026-10-05 "A documented 'missing file means the default' must read one named location only".
  - **Where in this contract:** `## Data Shapes` I-6: "The conventions file is read through `work_item_conventions_path()` … never a literal path". `## Open Questions for User` OQ-2: "(a) refuse to open the sub-issue, naming the missing block".
  - → Addressed by: I-6 now requires an explicit `--conventions` path and refuses `conventions-missing` when the project root cannot be determined; a test covers it.
- **[WARN] Moving and extending the script lookup block conflicts with the test that pins every lookup block, and that test is not in the run list**
  - **What is wrong:** `test_skill_script_lookup.py` cuts every fenced bash block that holds the cache-search line at the FIRST `py -3 "$VAR"` line. It reads back that variable and compares it with the expected path of the script named in the block (`.claude/scripts/tests/test_skill_script_lookup.py:12-29, 89-100`). The contract moves the block above the create and adds a sibling-derived helper path. If the first run line in the moved block runs the helper rather than `VPL`, or if a non-`py` derivation line is placed inside the cut, the "one snippet shared by every copy" check breaks. The handoff's test list names four suites and leaves this one out.
  - **Prior artifact ignored:** `.claude/scripts/tests/test_skill_script_lookup.py:12-29` ("One snippet is shared by every copy", decision 8 cut rule). The contract it cites, `2026-10-12-dedupe-claude-config.md`, lives in the consuming repository.
  - **Where in this contract:** `## Extension Points`: "The script lookup block moves above the create". `## Implementation Handoff` CONSTRAINTS: "Run test_compose_subissue_title.py, test_verify_parent_link.py, test_plugin_doctor.py and test_check_version_bump.py".
  - → Addressed by: `test_skill_script_lookup.py` is in the run list and the VPL line stays first in its block.
- **[WARN] A vendored consumer never receives the new helper, and the only mitigation is a halt with no named fix**
  - **What is wrong:** A file under `.claude/scripts/` that no tree's `files` array names is a local asset and is never synced. A vendored consumer therefore keeps `verify_parent_link.py` and never gets `compose_subissue_title.py` until its sync configuration names the new file. The Failure Mode accepts a permanent halt of every sub-issue create for that consumer. Its remediation names a path but not the sync-configuration line that clears the halt, and the Non-Goals exclude the one known consumer.
  - **Prior artifact ignored:** `MECHANISMS.md:44` (Plugin registry ownership model: "A file … that no tree's `files` array names is a local asset by default"). `JOURNAL.md` 2026-10-04 "Detect an install mode by what the sync actually delivers".
  - **Where in this contract:** `## Failure Modes & Mitigations`: "Parent-aware mode checks the sibling exists and halts loud, naming the path."
  - → Addressed by: the halt names the sync-configuration entry that clears it; README upgrade note added.
- **[WARN] I-5 is contradicted by the contract's own Failure Mode for a later no-parent `/task` run**
  - **What is wrong:** I-5 says the Parent reference "never reaches `/ship`'s pull request title". The sixth Failure Mode, however, says a no-parent `/task` run on a sub-issue keeps `#638 - Screener …` as the bare remainder. Step 2.5 point 2 writes that remainder into the brief's `title:` (`skills/task/SKILL.md:230`), and `/ship` composes the pull request title from `title:`. In that path the Parent reference does reach the pull request title. I-5 only holds for briefs written in Parent-aware mode.
  - **Prior artifact ignored:** `skills/task/SKILL.md:230` (Step 2.5 point 2: "`title:` in the brief holds the bare title *without* the prefix").
  - **Where in this contract:** `## Data Shapes` I-5: "The Parent reference therefore never reaches `/ship`'s pull request title". `## Failure Modes & Mitigations`: "point 4 keeps the bare remainder as is, so the Parent reference survives."
  - → Addressed by: I-5 reworded to match the Failure Mode.
- **[WARN] Confidence is High while two Uncertain Assumptions are ASSUMED**
  - **What is wrong:** The verdict contradicts the uncertainty inventory. One of the ASSUMED entries (the `parent-issue:` qualifier) feeds an acceptance criterion directly (AC-6).
  - **Prior artifact ignored:** the critic checklist rule on Confidence vs ASSUMED. `JOURNAL.md` 2026-10-04 "A VERIFIED parser claim must be tested on the unfilled and the missing case" (the same calibration discipline).
  - **Where in this contract:** `## Confidence`: "Confidence: High." `## Uncertain Assumptions`: "`ASSUMED`: `gh issue list --search "parent-issue:<owner>/<repo>#<n>"` lists one parent's children" and "`ASSUMED`: no consumer parses sub-issue titles by position".
  - → Addressed by: Confidence lowered to Medium until the `parent-issue:` qualifier is run.
- **[WARN] The Title composition request row declares no invariants for `bareTitle` or `effortTag`**
  - **What is wrong:** The row does not say whether `bareTitle` is trimmed, whether whitespace-only counts as `bare-title-empty`, or whether line breaks, double quotes or backticks are refused. The composed title is put inside a double-quoted shell argument (`--title "<the helper's composed title>"`, replacing `skills/task/references/parent-aware-mode.md:88`). `effortTag` says "enum" but not whether the tag is checked against `issueTitle.effortTypes` before rendering or only through `pattern-mismatch` after it.
  - **Prior artifact ignored:** `VOCABULARY.md:24` (Invariant). `skills/task/references/parent-aware-mode.md:88` (the shell create line the output feeds).
  - **Where in this contract:** `## Data Shapes → Value Objects`, row "Title composition request": "`bareTitle` (string, the sub-task name with no effort tag) | The helper's input."
  - → Addressed by: invariants added for `bareTitle` and `effortTag`; cause renamed `bare-title-invalid`; title passed to `gh` through a quoted shell variable.
- **[NIT] `exactlyOne` is not enforced** — `pattern` ends in `.+`, so a `bareTitle` that still starts with a tag (`[PERF] X`) composes `[PERF] #638 - [PERF] X` and passes `pattern-mismatch`. The brief's AC-2 says "exactly one effort tag first", and `.claude/work-item-conventions.json:7` declares `"exactlyOne": true`. No refusal cause covers this case.
  - → Addressed by: a leading effort tag in `bareTitle` is refused as `bare-title-invalid`.
- **[NIT] Adjacent Areas still holds an instruction aimed at the main session** — "The main session should confirm this with `py -3 .claude/scripts/cross_area_scan.py …` before the critic runs." The orchestrator reports that the scan ran and found no adjacent areas, so this sentence is now stale process text in the contract body.
  - → Addressed by: sentence replaced with the scan result.
- **[NIT] The upgrade step for existing consumers is not documented anywhere** — OQ-2 (a) costs "one paste per consuming project", but `Files to touch` names no README or upgrade note. `README.md:559` ("Fill in the four templates") is where onboarding text about the conventions file already lives. The paste text exists only in the helper's runtime remediation.
  - → Addressed by: README upgrade note added to Files to touch.
- **[NIT] One lesson citation does not match its Apply-when** — `## Lessons referenced` cites "2026-10-04 — Check a documented guard behaviour against the guard's code" as heeded. That entry applies to "what a blocking guard does when its input is missing". The `/flow` note documents a GitHub search qualifier, not a guard.
  - → Deferred: harmless citation; left as is.
- **[NIT] Registry tiers are missing** — `MECHANISMS.md`, `VOCABULARY.md` and `JOURNAL.md` have no project section for this repository (the JOURNAL project area is the day-1 placeholder). `INTEGRATION.md` and `.claude/.scout-cache/registry-digest.md` do not exist. Reuse and vocabulary checks were run against the Universal tier only.

### Applicable journal entries

- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by `## Implementation Handoff` (missing file, missing `issueTitle`, missing `issueTitle.subIssue` and malformed template are all test cases).
- **2026-10-04 — A root locator can return the consumer itself under vendoring** — heeded for the script lookup by `## Reused Mechanisms` and `## Failure Modes & Mitigations` (the helper is derived as VPL's sibling). Not addressed for the conventions read, where the reverse case applies (see the first WARN).
- **2026-10-04 — Detect an install mode by what the sync actually delivers** — not addressed. The sibling-exists check depends on a file the sync does not deliver by default (see the third WARN).
- **2026-10-05 — A documented "missing file means the default" must read one named location only** — not addressed. The contract refuses rather than defaulting, but it reads through the shared multi-root locator, which the lesson warns against (see the first WARN).
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — cited as heeded, but the Apply-when does not strictly match (see NIT).
- **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work** — not addressed (the contract did not need to: no new host-read configuration, and the lookup block's variable forms already exist and are tested).
- **2026-10-05 — Neutralise every field echoed from untrusted input, not only the body** — not addressed (the contract did not need to: no lower-trust text is delivered next to higher-trust text. The shell-quoting gap on `bareTitle` is raised under the sixth WARN instead).

### What the critic did not check

- Checklist 7 (Chat Tool Impact), 9 (End-User View), 12 (UI Implications): no REST/SignalR/DTO surface and no Angular file in `Files to touch`. The "Not applicable" lines are honest.
- Checklist 11 (Adjacent Areas): `.claude/area-mapping.json` declares no areas, so derivation is fallback-only. Both follow-up stubs exist on disk under `.claude/concepts/followups/`. Checks 11.b to 11.e pass.
- Checklist 13 (north-stars): `.claude/north-stars/` holds no files, so no findings.
- Did not run `cross_area_scan.py` or `derive_area.py` (no shell); relied on the orchestrator's report.
- Did not check whether Claude Code sets `CLAUDE_PROJECT_DIR` in the Bash tool's environment. The first WARN holds whenever it is unset.

---

## Lessons referenced

- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by the Implementation Handoff: the test suite covers a missing file, a missing `issueTitle.subIssue`, and a malformed template, not only a filled fixture. Cross-reference: `.claude/registries/JOURNAL.md` § Universal.
- **2026-10-04 — A root locator can return the consumer itself under vendoring** — heeded by Reused Mechanisms / Failure Modes: the helper path is derived as the sibling of the already-resolved `VPL`, never through a second, independent lookup. Cross-reference: `.claude/registries/JOURNAL.md` § Universal.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded by Uncertain Assumptions: the `/flow` note documents GitHub search behaviour, so the one unverified qualifier is ASSUMED, with a read-only verification run required before it ships.
- Orthogonal to north-stars: none (the register holds no active thought).

---

## Implementation Handoff

### 1. Sub-issue title helper, conventions, skills and version (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/scripts/compose_subissue_title.py`
- `.claude/scripts/tests/test_compose_subissue_title.py`
- `.claude/work-item-conventions.json`
- `.claude/scripts/plugin_doctor.py`
- `README.md`
- `skills/task/references/parent-aware-mode.md`
- `skills/task/SKILL.md`
- `skills/flow/SKILL.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `.cursor-plugin/plugin.json`

**Pre-written TASK block:**
```
TASK: Build sub-issue titles with the parent reference from a declared format, refuse when the
      parent is invalid, and document how to hide or list sub-issues.
CONTEXT: concept contract at .claude/concepts/2026-10-15-subissue-title-parent-ref.md
FILES: the Files to touch list above
CONSTRAINTS:
  - TDD-first: write .claude/scripts/tests/test_compose_subissue_title.py RED before the helper.
    House style of test_verify_parent_link.py: plain runnable script, no pytest, check()
    accumulator, fixture conventions files under a temp dir, subject resolved via __file__.
  - Test cases, at minimum: normal (PERF, parent 638, subtask 16, "Fix Earnings Index
    (dotnet-backend-architect)") -> "[PERF] P:#638 ST:16 - Fix Earnings Index
    (dotnet-backend-architect)"; leading "#" ("#638") gives the same title; refusals
    parent-missing (""), parent-not-positive-integer ("0", "-3", "##638", "abc", "638.0",
    "owner/repo#638"), subtask-missing (""), subtask-not-positive-integer ("0", "t16",
    "16.0"), bare-title-invalid (empty, whitespace-only, contains a line break, already starts with an effort tag), pattern-mismatch (undeclared tag), format-malformed (template
    without <parent> or without <subtask>), conventions-missing (no file; no issueTitle; no
    issueTitle.subIssue). Every refusal carries no "title" key. A changed
    fixture format changes the output (I-3). Every composed title matches the fixture's
    issueTitle.pattern. One "real corpus" check: the shipped conventions file renders the
    normal case to the exact title above.
  - Skill-sync checks in the same suite (pattern of test_ship_skill_sync.py):
    parent-aware-mode.md names compose_subissue_title.py, names every refusal cause the
    helper defines and no other, and no longer contains the literal "[<TYPE>] <bare title>"
    title template.
  - Conventions: add issueTitle.subIssue {"$comment", "legend", "format"} (not just "format");
    the legend states what P and ST mean in one line, and the /flow note, the refusal
    remediation and parent-aware-mode.md print it from there instead of restating it.
  - The helper is pure (I-4): no subprocess, no file writes. Read conventions only through
    the explicit --conventions path, or exactly <CLAUDE_PROJECT_DIR>/.claude/work-item-conventions.json (never the shared locator).
    Refusal order and cause names exactly as the contract's Data Shapes. Exit 0 composed,
    2 refused. JSON keys: verdict, title (composed only), cause and remediation (refused only),
    reason.
  - Conventions: add issueTitle.subIssue {"$comment", "format"} only. Do not restate the
    effort list or pattern. Mirror the same block into plugin_doctor.py's scaffold. Do NOT add
    parentLink there (follow-up stub).
  - parent-aware-mode.md: add the "compose the title" step to Order of operations, move the
    VPL lookup block above the create, derive the helper as VPL's sibling and halt loud when
    it is missing, feed the composed title to gh issue create, and add a refusal table. Never
    fall back to a parent-less title.
  - task/SKILL.md Step 2.5: one sentence pointing at issueTitle.subIssue for sub-issues,
    stating that the brief's title: stays bare. Do not restate the format.
  - flow/SKILL.md: after step 4 "Roll up", add the "Finding sub-issues in the issue list" note
    (no:parent-issue; parent-issue:<owner>/<repo>#<n>; cite parentLink.parentListCommand by
    name). Before shipping, run the parent-issue: qualifier once read-only and record the result
    in the PR description; drop that line if it fails.
  - Bump the version to 0.9.1 in all five manifest entries; check_version_bump.py must pass.
  - Run test_compose_subissue_title.py, test_verify_parent_link.py, test_plugin_doctor.py,
    test_check_version_bump.py and test_skill_script_lookup.py; all green. The moved lookup block
    must keep the VPL line as the FIRST `py -3 "$VAR"` line of its fenced block (that test cuts
    the block there); derive the helper path from VPL in a separate, later block.
  - README.md: add a short upgrade note beside the conventions-file onboarding text (around
    line 559): existing projects must paste the issueTitle.subIssue block (legend and format)
    into their conventions file, and vendored projects must list the new helper in their sync
    configuration.
  - Do NOT retitle any existing issue. Do NOT invent new data shapes; the contract is
    authoritative.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-15-subissue-title-parent-ref.md
  contract_status: approved
```

### 2. Scope note on review

There is no separate review sub-task. The change is a single mergeable sub-task, so `/flow` opens no sub-issues for it. The ordinary `/ship` review applies. The reviewer checks I-1 to I-6, the ASSUMED `parent-issue:` qualifier result in the pull request description, and the Step 2.5 sentence named in Failure Modes. After merge it promotes the two vocabulary terms.

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
