# Concept Contract — Memory-system client boundary and cloud engineering capability

**Project:** claude-agentic-auto-improve (the `agentic-auto-improve` plugin's own repository)
**Date:** 2026-11-01
**Requested by:** user
**Status:** approved
**Revision:** 9 (2026-11-03). Revision 9 is approved by the user on 2026-11-03, including Question 33. The user answered Open Questions 29-32 and asked for the `## Critique (Revision 9)` warnings to be folded in; both are written into blocks 19 and 20 (see block 19). Revision 9 appends a fix block 19 and its re-review 20 after the landing halted at gate P3 on block 18's `blocked` review. Revision 8 (2026-11-03) appends a remedy block 17 and its review 18 after the landing halted at gate P7. Revision 7 (2026-11-02): Revisions 2-4 answered three critique rounds and Open Questions 1-21. Revision 5 removes the deployment-authorization mechanism at the user's instruction (Decision note in Business Concept) and renumbers the handoff blocks. Revisions 6 and 7 (2026-11-02, notes under Handoff 11) append fix and re-review blocks after two blocked reviews; Revision 7 also adds the user's Project history record requirement, and was amended after the `## Critique (Revision 7)` round with the user's answers to Open Questions 22 and 23.
**Work Item Brief:** .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md
**Tracking issue:** #161
**Budget:** 20,000 tokens. This is raised from the template's 12,000 because the brief asks for the full audit to sit inside the contract. Open Question 14 offers to move the appendices out.

> **Protocol:** filled in by `data-architect`. Implementers refuse to run unless `Status: approved`. `concept-gate.py` reads `Files to touch`.
> **How to read this contract.** The design sections come first. **Appendix A** holds the audit, **Appendix B** the token-efficiency findings and **Appendix C** the prioritised plan. All three are at the end.

---

## Business Concept

- **What is this thing, in domain language?**
  There are two optional capabilities. Each is off until a project switches it on in its project profile.

  **1. Memory client boundary.** A *Central Memory System* is a separate product, in another repository, that holds engineering knowledge across projects. The plugin reaches it through MCP (Model Context Protocol, the way Claude Code talks to external tool servers). This contract makes the plugin a careful *client* of that system.
  - **Retrieval.** At design time the plugin asks for a small, targeted set of *memory items*. It shows each item to the user with two labels: its scope (global or project) and its status (proposed, validated, superseded or conflicting). The user records which items apply to this project **before** the architect drafts. The architect receives only the items the user marked as applying.
  - **Capture.** When a contract is delivered, the plugin offers to send back the lessons this work already wrote into its registries. The offer is **its own question**, asked only after the delivery's writing run has returned `flipped`, on both `/pr-merged` and `/flow`. It is never folded into the earlier records confirmation and never built from the dry run. Each lesson carries its provenance, at the weakest level the evidence supports. The plugin always sends a lesson as `proposed`.
  - **The record.** The Work Item Brief records every item used and every item sent, with ids and versions.
  - **What it does not do.** It stores no memory, runs nothing in the background and adds no hook. If memory is off, every brief and every flow is byte-for-byte what it is today. If memory is switched on but the server is unreachable or hangs, design shows one line and goes on.

  **2. Cloud engineering capability.** Today the plugin has none (Appendix A.6). The contract adds a provider-independent capability. It covers Azure, AWS and Google Cloud, plus Terraform, Bicep, Docker and Kubernetes. A project switches it on per provider in its profile. It brings one cloud skill whose provider references are read only for the providers the project selected, one cloud implementer agent, an infrastructure-as-code checklist in the existing security reviewer, and deployment validation through the existing verification runner. The skill and agent design, review, validate (non-mutating commands only) and troubleshoot. They never run a deploy, apply, create, update or destroy command against a live environment; they write it out for the user to run. An external cloud-management MCP server gets a configuration slot now. Its adapter is deferred.

  **Decision note (Revision 5, 2026-11-01).** The user said "dont create that permission mechanism". Revisions 1-4 had designed a deployment-authorization mechanism, and Revision 5 removes it entirely. The pieces removed are:
  - the `cloud-permissions` subcommand of `auto_improve_finish_install.py` and its `--check`;
  - the `permissions.ask` rows written to settings;
  - the live trial and the brief's `## Permissions trial` section;
  - the fail-closed refusal in the cloud skill and agent;
  - the conditional deploy-guard add-on fallback.

  It is replaced by a text-only rule. The cloud skill and agent never run a live-changing command; they hand it to the user. The user's normal Claude Code permission prompts and the existing destructive-operation guards apply unchanged. `test_cloud_text_scans.py` checks the rule in the shipped text. The critique sections below keep the earlier design as history and use the handoff numbering before Revision 5. In that numbering, old 8 was deployment authorization (now removed), old 9-12 are now 8-11, and old 13 is removed.

- **Existing VOCABULARY.md terms that apply:** *Port*, *Adapter*, *Invariant*, *Value Object* (Universal); *Working agreement*; *Plugin-delivered asset*; *Install mode*; *Placeholder slot*; *Add-on*; *Guard deference*; *Contract Delivery*; *Completion Verdict*; *Tracking Issue*; *Records pull request*; *Parent Branch Delivery Rule*. Two terms from `MECHANISMS.md` are also used: *Project profile* and *Two-tier registry*.

- **New terms proposed for VOCABULARY.md (Universal tier):**
  - **Central Memory System** — an external knowledge service in another repository, reached only over MCP. The plugin is its client and never its store. It is not *agent memory* (the `memory:` frontmatter folders under `.claude/agent-memory/`), not the *memory pager* (`memory-pager.py`, the always-on file budget) and not the user's private auto-memory.
  - **Memory item** — one unit of knowledge returned by the Central Memory System. It carries an id, a version, a **Memory scope** and a **Memory status**.
  - **Memory scope** — `global` (holds across projects) or `project` (holds for one project). A capture candidate starts from its registry tier: Universal gives `global`, Project gives `project`. The project-name check can lower `global` to `project`, never the reverse. The word `global` is used only for memory scope, never as a name for the Universal tier.
  - **Memory status** — `proposed`, `validated`, `superseded` or `conflicting`, as the Central Memory System reports it on retrieval. The plugin never changes an item's status. When it captures, it only *claims* `proposed`.
  - **Applicability decision** — the user's recorded answer, before the draft, to "does this memory item apply to this project?": `applies` or `does-not-apply`. For an `applies` item the adapter then derives `cited` (the contract's Lessons referenced names it) or `not-cited` (it does not). A user answer never comes from the architect.
  - **Capture provenance** — where captured knowledge came from: `user-decision`, `source-code-fact`, `test-confirmed` or `ai-hypothesis`. It is always the weakest value the evidence supports.
  - **Memory adapter** — the one place that knows the Central Memory System's tool names and shapes: `memory_boundary.py` plus the profile slots it reads.
  - **Memory shape profile** — a named version of the request and response shapes the adapter speaks (first `v0`). The `memory.shape` slot selects it.
  - **Memory exchange outcome**, **Retrieval request**, **Capture candidate**, **Capture receipt**, **Memory change notice** — the value objects defined under Data Shapes, proposed with the definitions given there. *Memory change notice* is chosen over any "drift" wording, because "drift" already names vendored-asset drift (`VOCABULARY.md:36`).
  - **Cloud capability** — the cloud skill, agent and checklist, active for a project only when its `cloud.providers` slot names at least one provider.
  - **Hand-off command** — a deploy, apply, create, update or destroy command that the cloud skill or the cloud agent writes out for the user to run themselves, and never runs. The user's normal Claude Code permission prompts and the existing destructive-operation guards apply to it unchanged. No new authorization mechanism exists (Decision note, Revision 5).
  - **Project history record** *(Revision 7; the user chose this name over "Project memory", critique Revision 7)* — a project's own file-based record of its design history, committed in its repository: the registries under `.claude/registries/` (`MECHANISMS.md`, `VOCABULARY.md`, `JOURNAL.md`, and `INTEGRATION.md` where the project keeps one), the concept contracts and follow-up stubs under `.claude/concepts/`, and the Work Item Briefs under `.claude/work-items/`. `/design-first` and the data-architect read it on every design, in every memory state. Confirmed steps append to it: `/task` writes the brief, the data-architect writes the contract, `/design-first` Steps 3 and 5 append the critic findings the user confirmed to `JOURNAL.md`, `fullstack-code-reviewer` appends on a justified contract divergence (and, as janitor, to `MECHANISMS.md` and `VOCABULARY.md`), and `/journal-add` appends a manual lesson. Routes with no design step (an XS/S direct edit, `/debug`, `/git-commit`, `/ship`) neither read nor append it by this definition. The **Central Memory System** only supplements it: an item never replaces, hides or skips a read of it, and a local entry wins a conflict until the user decides (Open Question 9). Not to be confused with `memory: project` agent memory (the folders under `.claude/agent-memory/`).

---

## End-User View

Not applicable. Reason: `Files to touch` holds no Angular component, template, stylesheet, state service, route or layout. The plugin's users are engineers working in Claude Code, and their view is covered in Appendix C and the README block (Handoff 9).

---

## Data Shapes

### Entities

| Name | Fields | Invariants | Ownership (aggregate) |
|------|--------|------------|-----------------------|
| Work Item Brief (existing, extended) | Existing frontmatter unchanged. New body section `## Memory used`, holding these line kinds: one `Memory:` state line; `Retrieved:` lines; `Reported:` lines (changed or conflicting items); `Captured:` and `Not sent:` lines | I-M0: **with memory `disabled`, no brief is touched.** No section and no line is written, and `/task`'s brief template is unchanged. I-M1: the section exists only when the state was `enabled` or `unconfigured` at evaluation. A brief without it means memory was off, which is also true of every brief written before this contract. I-M2: every `Retrieved:` line carries id, version, scope, status and the user's applicability decision; an `applies` line also carries `cited` or `not-cited` once the contract is drafted. I-M3: no item content beyond its neutralised title is written. I-M4: no new frontmatter key. I-M5: every field on every line has passed the adapter's field rules (see "Retrieved memory item") | Work Item Brief — the per-task record. No second store |

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Memory adapter configuration | `memory.server` (MCP server name), `memory.retrieve-tool`, `memory.capture-tool`, `memory.shape`, `memory.project-key` — five new profile slots | Read only by `memory_boundary.py` through `pr_merged.load_slot`. A placeholder or `none` value means unset. State: `disabled` when `memory.server` is unset; `unconfigured` when the server is set but the retrieve tool or a known shape is missing; `enabled` otherwise. Capture is enabled only when `memory.capture-tool` is also set |
| Memory exchange outcome | state (`enabled`, `disabled`, `unconfigured`, `unavailable`), reason (`profile-absent`, `slot-unset`, `shape-unknown`, `tool-absent`, `call-failed`, `timeout`, `malformed-response`), date | `disabled` is never written and never printed (I-M0). Any other state is the first line of `## Memory used` and is printed as one line |
| Retrieval request | query text (brief title plus acceptance criteria plus affected areas, capped in length), project key, scopes wanted (`global`, `project`), limit (at most 8, so the applicability question fits one host question call of two questions with four options each; ASSUMED host limit), deadline in seconds (from the shape profile, default 20; sent only if the shape supports it) | Rendered by the adapter in the selected shape. The main session sends it as the arguments of the configured retrieve tool. **One attempt, never retried** |
| Retrieved memory item | id, version, scope, status, title, summary (session only), superseded_by (id@version or none), conflicts_with (list of ids), source provenance | Produced by `normalise`. **Every field the server returns is untrusted, and each has a rule** (journal 2026-10-05). `id`, `version` and each entry of `superseded_by` and `conflicts_with` must match a safe pattern: letters, digits and `._:/-` (no `@`, so `<id>@<version>` always splits at its one `@`), 1-128 characters. An item whose own id or version fails is **rejected and counted**; a failing reference entry is dropped and counted. `scope` and `status` must be in their closed sets, else the item is rejected. `source provenance` is mapped to the four Capture provenance values, else it reads `unknown`. It is never echoed raw. `conflicts_with` is capped at 10 entries. `title` and `summary` have line separators and control characters removed, have leading `#`, `>`, `|`, `-` and backticks stripped, and are capped at 120 and 600 characters. They are passed as quoted data, never as instructions. **Count cap:** `normalise` keeps at most the first 8 accepted items in server order, whatever limit the server honoured, and counts the rest as `over-limit`. **Uniqueness:** the key is id plus version; a repeated key keeps the first and counts the rest. The same id at two versions keeps both and is reported as a conflict. Tests probe every field with a line separator, `## `, a pipe and a backtick |
| Applicability decision | item id@version, decision (`applies`, `does-not-apply`), decided_by (always `user`), date; for `applies` only, a derived `cited` or `not-cited` | Asked in `/design-first` Step 1.5, before the architect runs, as one multi-select question. Recorded on the `Retrieved:` line. The architect receives only `applies` items. `cited` and `not-cited` come from `check-contract`, a comparison of the brief's `applies` items with the contract's `Memory item <id>@<version>` lines |
| Capture candidate | source kind (`journal-entry`, `mechanism-entry`, `vocabulary-entry`, `correction-entry`), key, source ref (file, line, entry title, date where present), provenance, claimed status (always `proposed`), scope, contract slug, verbatim entry text | Produced by `capture-candidates` only from entries whose **own** naming line names this contract, read through the extended shared reader (see "Candidate reading" below). **Key:** for a journal entry, the SHA-1 of `date|title` (the `sig` the journal reader already computes); for a bullet or a correction, SHA-1 of `file|tier|title|line of its own first line`. **Verbatim text:** a journal entry's whole block; a bullet's own text **without** its indented sub-bullets; a correction's own sub-bullet text plus the parent bullet's title as context. **Scope safety:** a `global` candidate is lowered to `project` when its text contains a token from `<project>/.claude/.project-tokens.json`. That is the one location read, never a multi-root search. **When that file is missing or its `tokens` list is empty, every candidate is lowered to `project`** (fail closed). The confirmation shows each lowering and its reason |
| Capture receipt | key, source ref, returned id@version or the reason not sent, date | A `Captured:` or `Not sent:` line in the linked brief, keyed by candidate key |
| Memory change notice | item id, the version a brief recorded as `applies`, the current version or status, the briefs that recorded it | Produced by `changed-items`. Its input is the normalised items plus the `## Memory used` sections of `.claude/work-items/*.md` in the **current worktree**, which is a snapshot of the branch base. Briefs merged later are not seen; that is a stated limitation. It can only become a follow-up stub, after the user agrees at the Step 3 gate |
| Cloud profile | `cloud.providers` (`azure`, `aws`, `gcp`, or `none`), `cloud.iac` (`terraform`, `bicep`, `docker`, `kubernetes`, or `none`), `cloud.roots` (infrastructure source roots, or `none`), `cloud.mcp-server` (an external cloud-management MCP server name, or `none`) — four new profile slots | Read by the cloud skill, the cloud agent and the security auditor. `cloud.providers` = `none` means the capability is off |

**Provenance mapping.** A candidate gets the weakest value its evidence supports, never a stronger one. The JOURNAL header lists three Triggers (`pre-approval critic`, `post-impl divergence`, `manual`); `/journal-add` adds a fourth, `post-approval`. All four are covered:

| Existing source | Evidence available | Provenance |
|---|---|---|
| JOURNAL `Trigger: pre-approval critic` | `/design-first` Step 3 appends only findings the user confirmed, and the user's answer sits under the finding in the source contract's Critique | `user-decision` |
| JOURNAL `Trigger: post-impl divergence`, when the **live writing run** in this capture step returned `flipped` for this contract | the run that just wrote `Status: implemented` verified every sub-task merged, so the divergence is between the contract and merged code. The flip is in the branch being recorded, before it reaches `origin/<default>` | `source-code-fact` |
| MECHANISMS, VOCABULARY or Correction entry naming this contract, same condition | it describes files that same run verified as merged | `source-code-fact` |
| either of the two rows above, without a live `flipped` result for this contract | — | not a candidate (`not-flipped`) |
| JOURNAL `Trigger: manual` or `post-approval` | drafted by the session from the user's answers; nothing records that the user validated the wording | `ai-hypothesis` — not offered in v1 (Open Question 18) |
| A contract's `ASSUMED` line | the architect's guess | `ai-hypothesis` — not offered |
| any source | — | `test-confirmed` is **never claimed in v1**. No registry entry links to a test run, so the value cannot be derived |

**Trigger matching (Revision 7, review W3).** A Trigger maps only when its whole trimmed value (case-folded, surrounding backticks removed) equals one of the four canonical values. Any other text, such as `manual (follow-up to a pre-approval critic finding)`, is not a candidate and is skipped as `unknown-trigger`. Matching by substring is ruled out, because it can give a stronger provenance than the table allows.

**Candidate reading: the existing readers are extended, not bypassed.** Capture needs things neither existing reader provides:
- each entry's **full text**, including where a bullet ends and its indented `**Correction**` sub-bullets (for example `MECHANISMS.md:16,44,47,59-60,68-69`);
- a journal entry's **tier and line together with** its Trigger, Source contract and `sig`.

`tier_split` returns only `(title, line)`. `parse_entries` returns no line and no tier. Joining them would be new parsing, and the two use different heading patterns (`DATED` matches `#{2,3}`, `ENTRY_HEADER` only `###`). So the contract **extends the shared reader in its existing file** rather than writing a parser in the adapter:
- **In `.claude/scripts/generate_registry_digest.py`** (importable by name; `main` runs only under `__main__`), add two functions:
  - `entry_blocks(text, pattern, per_domain=False)` returns, per top-level entry: title, first line, tier, its own text (up to its first indented sub-bullet) and a list of indented sub-bullets, each with its line and text. An entry ends at the next top-level match or a `##` heading. **Its own text also ends at a blank line followed by a non-indented line that is not a top-level match** (Revision 7, review I1); such a note paragraph belongs to no entry, so it can never make the bullet above it a capture candidate.
    - Tier follows the existing rule: `## Universal…` gives Universal, and `## Project:…` gives Project.
    - **An entry before any tier heading is Project**, as `tier_split` already files it (`generate_registry_digest.py:57,67`).
    - `per_domain=True` (a file under `<REGISTRY>/<domain>.md`) makes every entry Project.
  - `journal_entries(text, per_domain=False)` returns, per `###` dated entry: `sig`, date, title, line, tier (same rules), trigger, source contract and the whole block text.
  - **Both take text, not a path.** The hook already holds the edited file's text (`journal-post-approval-tracker.py:171-176`), so its `parse_entries(text)` keeps its signature and passes the text through. Path-based callers read the file with the module's existing `read()` and pass its text.
  - `tier_split(path, pattern)` keeps its signature and `(title, line)` return shape and becomes a thin call: `read()`, then `entry_blocks`. `emit_group` is untouched.
  - **The byte-identical test.** The pre-change `tier_split` is copied verbatim into the test. The test runs `main()` twice, with the working directory set to a temporary copy of `.claude/registries/` (so the cwd-relative `OUT` lands in the temporary tree): once with `tier_split` patched to the old copy, once with the new one. It compares the two outputs byte for byte. It runs on the current registries and on fixture registries that have a pre-heading entry and Correction sub-bullets. There is no golden file, so registry appends never break it.
- **Journal tier for capture.** The digest labels every journal entry `Universal` (`generate_registry_digest.py:128-130`), and the contract no longer claims otherwise. That label is not used here. For capture, `journal_entries` derives the tier from JOURNAL.md's own headings: entries under `## Universal lessons` are Universal, entries under `## Project: <name>` are Project, and entries in `JOURNAL/<domain>.md` are Project. The digest's own labelling is left unchanged.
- **The hook becomes a thin caller.** `.claude/hooks/journal-post-approval-tracker.py` keeps its name and behaviour, but its `parse_entries(text)` delegates to `journal_entries(text)` and keeps the keys it returns today. It imports normally from the scripts folder the hook already puts on its path (it already imports `derive_area` and `accuracy_update` from there). It binds with `getattr` after a fail-soft import, per Guard fallback mode: a missing or stale reader makes the advisory hook skip, logged. `memory_boundary.py` never loads the hook file. No `importlib` loading anywhere.
- **Source contract forms (journal 2026-11-01, "a shared reader reused by a stricter consumer").** The forms the old `SOURCE_LINE` (`[^\s`]+`) mis-read are each pinned by a test:
  - a path with spaces is captured to the end of the line, with backticks and trailing spaces trimmed;
  - `N/A`, `none`, an empty value and a `<…>` placeholder read as unset;
  - an absolute Windows path (`JOURNAL.md:308`) is captured whole.

  The hook's own behaviour changes only for those forms, and the tests list the change: an `N/A` source no longer feeds `derive_areas` a non-path.
- **"Names this contract" uses the entry's own line only.** A journal entry is a candidate when its own `Source contract` value names the slug, by the stem rule of `pr_merged.brief_names_contract` (last path component minus `.md`, both `/` and `\` as separators). A bullet is a candidate when **its own text, excluding sub-bullets,** holds `.claude/concepts/<slug>.md` or `Contract:` followed by the slug. A Correction sub-bullet naming this contract is its own `correction-entry` candidate. It never makes the bullet above it a candidate, so `MECHANISMS.md:44,47,68` would offer only their corrections when `2026-10-12-dedupe-claude-config` is delivered.
- **Ownership of the filtering.** All of this lives in the two shared functions, with their tests (Handoff 2). The adapter only selects by contract and maps provenance.

**Duplicate protection.** A capture is offered only in the capture step, on a live writing run that returned `flipped`, which happens once per contract. A later run reads `already-implemented` and offers nothing. An entry is eligible only for the contract its own line names. Within the step, keys already on a `Captured:` line of the linked brief are skipped. A `Not sent:` key is not offered again automatically: v1 has no retry (Known limitations). **Stop rule:** at the first send that fails or times out, the step stops sending. It writes every remaining confirmed candidate as `Not sent: (stopped after <reason>)` and goes on with delivery, so a hung server costs at most one host timeout. **Pending-then-flip:** the step is keyed on the writing run's result only. A dry run that read `pending` (cleared by the owner's confirmation) followed by a writing run that flips still gets the capture step.

### Events

These are recorded as lines in the brief. There is no event bus.

| Name (past tense) | Emitter | Listeners | Payload |
|-------------------|---------|-----------|---------|
| MemoryEvaluated | `/design-first` Step 1.5 (via the adapter's `status`) | brief `## Memory used` and one printed line — **only when the state is not `disabled`** | Memory exchange outcome |
| MemoryRetrieved | `/design-first` Step 1.5 | the user (applicability question), brief | Retrieved memory items, rejected count |
| ApplicabilityDecided | `/design-first` Step 1.5 (user answer, before Step 2) | brief `Retrieved:` lines; `data-architect` receives `applies` items only | Applicability decision |
| MemoryChangeNoticed | adapter `changed-items` during Step 1.5 | `/design-first` Step 3, which asks whether to write a follow-up stub | Memory change notice |
| CaptureSent | the capture question, asked on its own after the live writing run returned `flipped` (`/pr-merged` step 5a; the same question under `/flow`, after Step 8's earlier confirmation and its writing run) | linked brief `Captured:` / `Not sent:` lines | Capture receipt |

### Commands

| Name (imperative) | Handler | Payload | Possible rejections |
|-------------------|---------|---------|---------------------|
| Report memory state | `memory_boundary.py status --project <root>` | project root (explicit) | none by design: it exits 0 and prints a state. Its imports are fail-soft with `getattr` binding (Guard fallback mode), and it appends to `sys.path`, never inserts. **Whatever any caller sees, any non-zero exit, crash, timeout or missing script reads as memory off**: one printed line, nothing written, and the run continues |
| Render retrieval request | `memory_boundary.py retrieve-request --project <root> --brief <path>` | brief | `not-enabled`, `empty-query`, `shape-unknown` |
| Normalise response | `memory_boundary.py normalise --project <root> --input <file>` | raw tool response saved to a file | `malformed-response` (whole response); per-item rejections are counted, not fatal |
| List capture candidates | `memory_boundary.py capture-candidates --project <root> --contract <slug> --run-report <file>` | contract slug; the **live writing run's** JSON report (its completion verdict and `written_files`) | `capture-not-enabled`; `not-flipped` (the report's verdict for this contract is not `flipped`); `brief-not-carried` (no linked brief, or the linked brief is not in `written_files`); `default-branch-unknown` (Revision 7, review I2: no `--default-branch` was given and `pr_merged.default_branch_or_none(cwd=<project>)` cannot read the project's `origin/HEAD`; the adapter never falls back to a fixed name). Every refusal comes **before** anything is offered or sent, so nothing is ever sent without a receipt path |
| Render capture request | `memory_boundary.py capture-request --project <root> --candidate <file>` | one confirmed candidate | `ai-hypothesis-refused`, `status-not-proposed`, `capture-not-enabled` |
| Record outcome | `memory_boundary.py record --project <root> --brief <path> --outcome <file> [--receipts --run-report <file>]` | outcome, items, decisions; with `--receipts`, the receipts plus the **same live writing run's report**, whose `written_files` is the list checked | `not-enabled` (state `disabled`: **writes nothing**; with `--receipts`, any state but `enabled`). Under state `unconfigured` it is not refused: it writes only the `Memory: unconfigured (<reason>) \| <date>` line, with the reason read from the profile, never from the outcome (Revision 7), `brief-not-found`, `would-add-frontmatter`, `brief-not-carried` (receipts only: the brief is not in the report's `written_files`) |
| Check citations | `memory_boundary.py check-contract --project <root> --brief <path> --contract <path>` | brief, contract | none. It prints `cited` / `not-cited` per `applies` item, plus any `Memory item` line naming an item that is not `applies` (reported as `uncleared-item`) |
| List changed items | `memory_boundary.py changed-items --project <root> --input <normalised file>` | normalised items (the file `normalise` wrote, never the raw response). It applies the same per-item rules as `normalise` to its input, so an item `normalise` rejects never raises a notice, and it compares versions as the normalised strings (Revision 7, review W2) | none. It prints zero or more Memory change notices |
| Deploy / apply / destroy (cloud) | the user only, after the host's "ask" prompt | command line | the agent never issues it; the host asks |

Every subcommand is pure except `record`. It writes only the one brief it is given, with the replace-then-rename write the scripts already use.

---

## Reused Mechanisms

What each part extends (acceptance criterion: "a reviewer can name the existing mechanism each part attaches to"):

| Part of the design | Existing mechanism it extends |
|---|---|
| On/off switch and every tool name | **Project profile**, extended by nine slots (five memory, four cloud). It is read through `pr_merged.load_slot`, whose docstring says "never a second configuration file competing with the profile". Placeholder and `none` already read as unset (`pr_merged.py:85-98`), so "off by default" needs no new code |
| Where retrieved items and decisions are recorded | **Work Item Brief**, extended by the `## Memory used` body section |
| Global vs project labels | **Two-tier registry** (Universal vs Project tier), read through the extended shared reader (`entry_blocks`, `journal_entries`). The tier is the starting scope, and the project-name check can only lower it |
| "Never auto-adopted; the user decides" | `/design-first`'s communication gate, consumed as-is, asked earlier: at Step 1.5, before the draft, not only at Step 3 |
| Recording which knowledge shaped a design | The contract's `## Lessons referenced`, extended by a `Memory item <id>@<version>` line format, which `check-contract` reads |
| Reading registry entries for capture | **Two-tier registry with a generated complete index**, extended: `generate_registry_digest.py` gains `entry_blocks` and `journal_entries`, and `tier_split` becomes a thin wrapper with the same output. `journal-post-approval-tracker.py`'s `parse_entries` becomes a thin caller of `journal_entries`. One shared reader, in its existing file, used by the digest, the hook and the adapter |
| What may be captured, and its provenance | **Adaptive Engineering Journal** triggers plus the MECHANISMS and VOCABULARY janitor appends and their Correction sub-bullets. They are the only candidate sources |
| When capture happens, and how its receipts are committed | `/pr-merged`'s **Completion Verdict** `flipped`, read from the **live writing run**, and the **Records pull request**, consumed as-is. On a flip with a linked brief, the brief is in that run's `written_files` (`pr_merged.py:3851`, `4796`). The capture step checks that first (`brief-not-carried`). Receipts written to the brief before step 7's copy ride in the same records pull request |
| Finding the brief for a contract | **Brief linkage selector and matcher** (`select_linked_brief`), consumed as-is |
| Keeping project names out of global memory | **Project-name check** token list, read from `<project>/.claude/.project-tokens.json` only. It is inert when that file is empty (the template ships `"tokens": []`), so an empty or missing list fails closed (everything is lowered to `project`) |
| A changed memory may only propose work | **Follow-up stub**, with `Parent contract:` set to the contract being designed and `Derived from:` "memory change notice, briefs <list>". It is written only after the user agrees at Step 3; Step 3.4 opens the tracking issue |
| Graceful degradation | `/task` Step 1's tracker cascade rule ("check the tool list; do not assume"), consumed as-is, plus the new one-attempt, no-retry rule |
| Script location under any install mode | The standard script lookup block, pinned by `test_skill_script_lookup.py`, consumed as-is |
| The procedure text, read only when memory is enabled | **Sibling skill reference file** (`pr-merged` reads `../design-first/references/central-memory.md`), plus the "When X applies, read references/Y.md" pattern |
| The adapter itself | **Port / Adapter (Universal)**. The port is the plugin-side interface the adapter's subcommands expose (retrieve, normalise, capture, record); `memory_boundary.py` is its one adapter to the external Central Memory System |
| "Only one file names the memory tools" | `test_plugin_text_scans.py`, extended by one scan over the files `check_version_bump.is_shipped` calls shipped. The registries and `.claude/hooks/tests/` are shipped and get no exemption. Instead, every registry entry about memory (the Memory adapter mechanism, the vocabulary terms and any journal lesson from these critiques) avoids the literal tool names and says "the configured retrieve tool" and "the configured capture tool" |
| Cloud provider reference loading | the domain pattern-skill precedent (`sql-server-patterns`), with references read conditionally |
| Cloud deployment validation | `land_contract.py --verify-here` with `contractLanding.verification.steps` in `.claude/work-item-conventions.json` (line 90), consumed as-is. The project adds non-mutating steps; the skill documents them |
| Live cloud changes | **No mechanism (design decision, Revision 5).** The cloud skill and agent never run a deploy, apply, create, update or destroy command against a live environment; they write it out as a Hand-off command. The user's normal Claude Code permission prompts and the existing destructive-operation guards apply unchanged. Enforced in text and by `test_cloud_text_scans.py` |
| Cloud review | `security-auditor` agent, extended by an infrastructure-as-code checklist section |
| Telling a host project that its Project history record is what to use (Revision 7) | **Two-tier registry** and the concept-contract folder, consumed as-is; the **plugin doctor** (`plugin_doctor.py`), consumed as-is in report mode, with `--fix` run only after the user confirms the list it would create (Open Question 23); **Session-start context delivery** (`MECHANISMS.md`, "Extend by: adding a markdown file to the plugin's folder (plus its name in the suite's required-file test)"), extended by one shipped agreement; the `/auto-improve-finish-install` skill and the Step 1.5 printed lines, extended by text only. No new store, hook, seed or frontmatter key |
| Existing destructive database guards | `db-destructive-guard.py` and `db-research-readonly-guard.py`, consumed as-is and never weakened |

**Persistence check (consumed as-is):** `load_slot` reads one profile table and treats an unfilled slot as empty (verified at `pr_merged.py:85-98`). The brief linkage reader filters `none`, `UNKNOWN` and placeholders. The journal header defines three Triggers and `/journal-add` a fourth (`post-approval`); the provenance table covers all four. The project-name check list is a plain `tokens` array, empty in the shipped template.

---

## New Mechanisms (if any)

- **Name:** Memory adapter (`memory_boundary.py` plus the `memory.*` profile slots).
- **Purpose:** the one place that knows the Central Memory System's tool names and request and response shapes. It turns a brief into a retrieval request, and a response into labelled items with every field neutralised. It selects capture candidates from the entries the extended shared registry reader returns (it parses no registry itself). It enforces the provenance and scope rules, compares the brief's `applies` items with the contract's citations, and records outcomes in the brief (never when memory is disabled).
- **Why an existing mechanism was not sufficient:** no mechanism exchanges knowledge with an external system. The nearest is `/task`'s tracker cascade. It fetches *work items* from GitHub, Jira or Azure DevOps, and it holds no shape validation, labelling, provenance or recording. Stretching it would mix two lifecycles the brief keeps apart. Port/Adapter says to add an adapter to an existing port first. No plugin-side interface for external knowledge exists, so this declares the first one (its subcommands) and its single adapter. Everything around it (switch, record, gate, sources, timing, stubs) reuses existing mechanisms (table above).
- **Proposed location:** `.claude/scripts/memory_boundary.py`, with tests at `.claude/scripts/tests/test_memory_boundary.py`. The procedure text lives at `skills/design-first/references/central-memory.md`.
- **Extension seam:** a new response shape is one new shape profile inside the script plus a slot value. A new capture source is one entry in the source-kind table. Nothing else names a memory tool, and a scan enforces that.
- **Will this be promoted to `MECHANISMS.md` after implementation?** yes.

No other new mechanism. The cloud skill and agent are assets, not mechanisms. No permission mechanism is created (Decision note, Revision 5).

---

## Extension Points

- `.claude/project-profile.md` (template): nine rows in the Slots table. Every value starts as the italic placeholder, so the capability is off.
- `/design-first` new **Step 1.5 "Consult the Central Memory System"**. It runs only for non-trivial tasks.
  1. Locate the script and run `status`. On `disabled`, or an empty lookup, **print nothing, write nothing** and go to Step 2 exactly as today.
  2. **Any non-zero exit, crash, timeout or unreadable output of any adapter subcommand, at any point in this step:** print one line naming the subcommand and its exit code, write nothing further, treat memory as off for the rest of this run, and go to Step 2.
  3. On `unconfigured`, print the status line, then record it with `record` into the brief whose `branch:` is the branch you are on (the same rule as point 4). `record` accepts this state and writes only the state line (Revision 7, review B1). With no such brief, print one line saying the memory record was skipped for want of a brief and go to Step 2: that is not a failure. Only a refusal or non-zero exit from `record` when a brief was found is a failure under point 2.
  - **The Project history record comes first, in every state (Revision 7).** The step's text states that the project's design history is its Project history record (registries, concept contracts, briefs), which Step 2 and the architect read whatever the memory state. The Central Memory System only supplements it. On `disabled` this is a sentence in the skill text only: nothing is printed and nothing is written (I-M0). Every line the step prints in any other state (the point 2 failure line, the point 3 status line and skipped line, the point 4 skipped line, and the reference's `unavailable` lines) ends with the fixed suffix `; design continues from the project history record (registries and concept contracts)`. The skill text appends the suffix when it prints; `memory_boundary.py` does not change for it. The recorded brief line keeps its format.
  4. On `enabled`, read `references/central-memory.md` and follow it:
     - Check the session tool list for the configured tool.
     - Make **one** call with the rendered request. The bound on that call is the host's MCP tool timeout. No retry. Any error, timeout or absent tool records `unavailable (<reason>)`, prints one line and goes to Step 2.
     - Normalise the response and run `changed-items`.
     - Ask the user **one** question call: at most 8 items, in up to two multi-select questions of four options. Record the answers.
     - Pass only `applies` items as PRIOR_FINDINGS `memory_items`.
  5. At Step 3, run `check-contract`. Show `not-cited` and `uncleared-item` results and any change notices. A change notice becomes a follow-up stub only on the user's yes.
- `/flow`: its "Always the operator's call" list (`skills/flow/SKILL.md:539-546`) gains one line: "The memory applicability question in `/design-first` Step 1.5, asked only when memory is enabled and items came back". It is edited in the same block as design-first (Handoff 3).
- `/auto-improve-finish-install` (Revision 7, text only): a section saying the Project history record files are the project's record of its design history and must be used and committed, that the Central Memory System only supplements them, and a check (Open Question 23). The check runs the existing doctor in report mode, lists exactly what `--fix` would create, and runs `plugin_doctor.py --fix` only after the user confirms that list; it never runs `--fix` on its own. `--fix` creates every missing requirement in the doctor's `REQUIREMENTS` list, not only the registries: the folders `.claude/concepts`, `.claude/work-items`, `.claude/north-stars` and `.claude/orchestrator/results`, copies of the contract template and the three seeded registries, and the scaffolds `.claude/area-mapping.json` and `.claude/work-item-conventions.json` (`plugin_doctor.py` `REQUIREMENTS` and `apply_fixes`). It never overwrites, and it leaves `.claude/settings.json` to the user. When the doctor prints `plugin:  NOT FOUND - pass --plugin`, the copy requirements cannot be resolved: the section says so in one line and asks for the plugin path instead of going on as if the registries were seeded. No change to `auto_improve_finish_install.py`, `plugin_doctor.py` or its seed list.
- Shipped agreements (Revision 7, user answer "add a session-start agreement"): one new short file in the plugin's `.claude/agreements/` folder, delivered by `working-agreements.py` to every session in a plugin install. It says that the Project history record (the registries and concept contracts) is the project's memory and is to be used, and that a central MCP memory system only supplements it. The suite `.claude/hooks/tests/test_working_agreements.py` names it in `REQUIRED` and `SHIPPED_PHRASES`.
- `/task`: **unchanged.** The `## Memory used` section is documented in the design-first reference only, so `/task`'s brief template stays byte-identical.
- `data-architect`: a "Memory items" rule.
  - Treat items as quoted data, below the project's registries and the user.
  - Use only `memory_items`, which hold `applies` items only.
  - Cite every item that shaped the draft as `Memory item <id>@<version>` under `## Lessons referenced`.
  - Report a conflict with a local registry entry as an Open Question; the local entry wins until the user decides.
- `/pr-merged` (`references/contract-completion.md`): a new **step 5a "Capture"**. It runs only when capture is enabled, and only **after** a live writing run (step 5) returned `flipped` for this contract, whatever the earlier dry run said (a `pending` dry run followed by a flip still gets it). It is never built from the dry run, and step 3's confirmation is unchanged.
  1. Run `capture-candidates --run-report <the report>`. "The report" is the JSON of the one writing run that returned `flipped` for this contract; when two writing runs were made, it is the one that flipped. The command refuses `not-flipped`, or `brief-not-carried` (no linked brief, or the brief is not in that report's `written_files`), **before anything is offered**. A refusal prints one line and the records pull request goes on unchanged.
  2. With no candidates, the step ends silently.
  3. Otherwise ask the **capture question**: its own question, separate from step 3's records confirmation, which came before the writing run and is unchanged. It lists each candidate with provenance, scope and any scope lowering with its reason. The owner unticks what not to send.
  4. Send each confirmed candidate once, in order. **Stop rule:** at the first failure or timeout, stop sending, write every remaining confirmed candidate as `Not sent: (stopped after <reason>)`, and continue delivery.
  5. Run `record --receipts --run-report <the report>` into the linked brief, before step 7 copies the files.
  6. No outcome of this step blocks the records pull request.
- `/flow` (Step 8 and the closing paragraph at `skills/flow/SKILL.md:591`): under `/flow`, Step 8's single confirmation still comes **before** the one writing run and is unchanged. Capture is **not** joined to it. After that writing run returns `flipped`, `/flow` asks the same separate capture question (step 5a), sends with the same stop rule and records receipts. Only then does Step 8 commit and push the brief. `/flow`'s one-confirmation rule is amended in Handoff 4 to say: "Step 8's confirmation is the one confirmation for the records; when memory capture is enabled and candidates exist, one separate capture question follows the writing run that flipped." That question is added to "Always the operator's call".
- `/journal-add`: **unchanged.** A standalone journal entry is never captured in v1. A manual or post-approval entry is `ai-hypothesis` by the provenance table, and the skill writes only JOURNAL.md.
- `test_plugin_text_scans.py`: a scan whose **file set** is built by walking named shipped folders from the test file's own checkout root, `Path(__file__).parents[3]` (never the current directory, never a walk from the repo root). The folders are `agents/`, `skills/`, `.claude/hooks/`, `.claude/scripts/`, `.claude/templates/`, `.claude/references/`, `.claude/registries/`, `.claude/agreements/`, `.claude/addons/` and `.claude/agent-memory/`, plus the root manifests. That is the same named-folder pattern as `test_plugin_text_scans.py:102`. Any path holding a `.claude/worktrees/` segment is excluded, and the set is then filtered by `check_version_bump.is_shipped`. None may contain `memory_retrieve` or `memory_capture` except `.claude/scripts/memory_boundary.py`. README, CONTRIBUTING, contracts, briefs and `.claude/scripts/tests/` are not shipped by that definition. The registries, `.claude/hooks/tests/` and `.claude/agent-memory/` are shipped and are **not** exempt, so registry entries about memory avoid the literal names. A made-up file is planted as the positive control.
- `generate_registry_digest.py` (`entry_blocks`, `journal_entries`, `tier_split` as a wrapper) and `journal-post-approval-tracker.py` (`parse_entries` as a thin caller): see "Candidate reading".
- `skills/cloud-engineering/` (new skill) with `references/`. `agents/cloud-engineer.md` (new agent). `pr_merged.DEFAULT_IMPLEMENTERS` gains `cloud-engineer`.
- `agents/security-auditor.md`: an infrastructure-as-code section, active when `cloud.providers` is not `none`.
- `skills/debug/SKILL.md`: the container and infrastructure route names `cloud-engineer` (it currently names the unshipped `docker-master-goat`).
- **The cloud scope rule (design decision, Revision 5)**, written into both the cloud skill and the cloud agent: they do design, review, validation (non-mutating commands only) and troubleshooting. They never run a deploy, apply, create, update or destroy command against a live environment; they write it out as a Hand-off command for the user to run. The user's normal Claude Code permission prompts and the existing destructive-operation guards apply unchanged. Nothing is written to any settings file.
- A cloud text scan (`.claude/scripts/tests/test_cloud_text_scans.py`): no shipped cloud skill, reference or agent line presents a mutating command (`apply`, `create`, `update`, `destroy`, `delete`, `deploy`, `install`, `upgrade`, `uninstall`, `push`) as something to run. Mutating commands appear only inside a block labelled "for the user to run". A planted line serves as the positive control.

**Delivery routes (journal 2026-10-30, "name every route"):**

| Route | Memory retrieval | Capture |
|---|---|---|
| `/task` → `/design-first` (M/L/XL) | Step 1.5 | `/pr-merged` step 5a, after the live writing run returns `flipped` |
| `/flow` → `/task` → `/design-first` | same Step 1.5, not repeated in `/flow`; its question is listed among `/flow`'s operator stops | a separate capture question after the writing run (made after Step 8's confirmation) returns `flipped`; Step 8's confirmation itself is unchanged |
| `/design-first` run directly | Step 1.5 | `/pr-merged` step 5a |
| `/pr-merged` with a `pending` dry run, then a flipping writing run | — | step 5a, keyed on the writing run |
| XS/S direct edit or `/debug` | none (no design step; keeps retrieval targeted) | none (no contract flips) |
| Parent-aware sub-task (`/advance`) | none (the parent contract already decided) | at the parent's flip only |
| `/journal-add` standalone | none | none in v1 |
| `/pr-merged --record-delivery` (one-branch delivery) | — | step 5a, when that writing run flips |
| flip with no linked brief | — | none: step 5a refuses `brief-not-carried` before offering, and nothing is sent |

---

## Integration Surfaces

`.claude/registries/INTEGRATION.md` does not exist in this repository. These surfaces are new and cross the plugin boundary.

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---------------|---------------|-----------|------------|-----------|
| Main session (`/design-first` Step 1.5) | Central Memory MCP server | the tool named by `memory.retrieve-tool` | Retrieval request → raw response | plugin → memory → plugin |
| Main session (`/pr-merged` step 5a, or `/flow` after its writing run flips) | Central Memory MCP server | the tool named by `memory.capture-tool` | Capture candidate → receipt | plugin → memory |
| `memory_boundary.py` | Work Item Brief | file write (`record`) | `## Memory used` lines | script → repository |
| Cloud skill, main session only | external cloud-management MCP server | the slot `cloud.mcp-server` (adapter deferred) | none yet | plugin → cloud (read-only, deferred) |

**Changes to existing integration surfaces:** none. No REST endpoint, SignalR event or DTO exists in this plugin.
- [ ] Not applicable on both sides (no C# or TypeScript).

**Rule:** a configured MCP server is called only from the main session, never from a subagent. A plugin agent's `tools:` line is fixed text and cannot name a server the project chooses. Subagents receive results as PRIOR_FINDINGS.

---

## Adjacent Areas

Not applicable. Reason: cross-area scan returned no signal above the threshold.

---

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces. The plugin has no `frontend.roots`.

---

## Chat Tool Impact

2. **No — this contract adds no REST endpoint or SignalR event, so there is nothing to wrap as a chat tool.**

---

## Non-Goals

- The Memory Engine, Neo4j, the Memory MCP server and its schema. These live in another repository.
- Any database, cache, index, background process, scheduler or hook for memory.
- Delivering Central Memory System items at session start, or into always-on files. Session-start delivery is untargeted and capped at 9,500 characters. The one shipped agreement Revision 7 adds is a fixed rule (use the Project history record), not memory content, and it carries no item.
- Reading or writing agent memory (`.claude/agent-memory/`, `memory:` frontmatter), the memory pager or the user's auto-memory. They stay unchanged.
- Capturing AI hypotheses (including manual and post-approval journal entries in v1), chat transcripts, diffs or agent notes.
- Any change to `/task` or `/journal-add`.
- A retry or resend queue for capture.
- Finding changed items that the current targeted query does not return. Only re-returned items are compared; this is a stated limitation.
- Any automatic code edit triggered by a memory change.
- Running deploy, apply or destroy commands from any agent, and any production-access automation.
- The cloud-management MCP adapter. Only its slot is added (Open Question 12).
- The token-efficiency fixes and the other audit defects (follow-up stub).
- Cursor and Codex MCP naming (Known limitation in the docs).

---

## Confidence

Confidence: Medium. High on reuse mapping and degradation (verified against `load_slot`, the brief linkage reader, journal triggers and the verification runner). Medium on the MCP tool id form and response shape (the schema is unknown by design; the shape profile absorbs it). High on the cloud boundary, which is now a text-only rule pinned by a text scan, with no host matching assumption.

---

## Alternatives Considered & Why Rejected

- **Option A (chosen):** one script adapter plus profile slots. Call sites only in `/design-first` and `/pr-merged` (and `/flow` Step 8 through it). The brief is the record. No hook.
  - Why: every part attaches to an existing mechanism. With memory disabled, one silent `status` call is the whole cost, and no file changes.
- **Option B (rejected):** extend `registry-scout` so it also queries the memory server.
  - Why rejected: a subagent's `tools:` line cannot name a project-chosen MCP server. The scout's contract is "the index is complete", which a remote, partial result would break.
- **Option C (rejected):** a SessionStart or UserPromptSubmit hook that pre-fetches memory.
  - Why rejected: untargeted, it costs a process every session or prompt, and hooks cannot call MCP tools.
- **Option D (rejected):** memory as an add-on with install and uninstall skills.
  - Why rejected: nothing needs copying into the project. It would add two skill descriptions to every session. A profile slot already gives "off until the project asks".
- **Option E (rejected):** keep a local mirror of retrieved items under `.claude/state/`.
  - Why rejected: it would be a second store, which the brief forbids.
- **Cloud, Option F (rejected):** cloud provider documents as add-on documents in `review.documents`.
  - Why rejected: every reviewer would read every listed document on every review. A skill reads only the selected providers' references.
- **Cloud, Option G (rejected):** a new `cloud-destructive-guard.py` hook.
  - Why rejected: it adds a process per shell command, and the user ruled out a permission mechanism (Revision 5).
- **Cloud, Option H (rejected, Revision 5):** `permissions.ask` rows written by a `cloud-permissions` finish-install subcommand, checked fail-closed by the cloud skill and agent.
  - Why rejected: the user's instruction, "dont create that permission mechanism". The text-only rule plus the user's normal permission prompts and the existing guards is the chosen design.
- **Project history record, Option I (rejected as the only channel, Revision 7):** state the rule only in `/auto-improve-finish-install` and `/design-first` Step 1.5.
  - Why rejected: finish-install runs once (and not at all when a plugin install skips it), and Step 1.5 runs only for non-trivial designs. An XS/S direct edit, `/debug`, `/journal-add` and any session that never designs would get no instruction (critique Revision 7, WARN 1).
- **Project history record, Option J (chosen with Option I, Revision 7):** also add one shipped agreement through **Session-start context delivery**, so every session in a plugin install hears the rule before its first reply.
  - Why: it is the plugin's existing channel for standing guidance, extended exactly as its registry entry says (one markdown file plus its name in the suite's required-file test), with no new code. Cost: one short agreement, about 400 characters, inside the 9,000-character limit that the suite pins. Limits: a vendored copy of the hook delivers nothing (`vendored-unsupported`), so finish-install and Step 1.5 still carry the rule for those installs.
- **Project history record, Option K (rejected, Revision 7):** a new SessionStart hook or a `CLAUDE.md` edit in the host project.
  - Why rejected: a hook adds a process per session for text the agreements hook already delivers, and the plugin never writes a host's `CLAUDE.md`.

---

## Uncertain Assumptions

- `ASSUMED`: Claude Code exposes a project- or plugin-configured MCP tool as `mcp__<server>__<tool>`. Matters because the adapter composes the id from the two slots. Verification path: one session with a stub server, list the tools (Handoff 3 precondition).
- `ASSUMED`: the Central Memory System returns structured items carrying id, version, scope and status. Matters because `normalise` rejects anything else. The decision whether to build before the schema exists is Open Question 17.
- `ASSUMED`: the host bounds an MCP tool call with its own timeout (the `MCP_TOOL_TIMEOUT` environment setting), and an expired call returns an error to the model. Matters because no plugin component can measure the call. Verification path: context7 Claude Code docs, plus the Handoff 3 stub-server trial with a server that never answers. If it fails, the README documents the setting as required for memory.
- `VERIFIED via pr_merged.py:3851,4796`: on a flip, the linked brief's path is added to `written_files`, so the records pull request carries it.
- `VERIFIED via generate_registry_digest.py:55-68,128-130` and `journal-post-approval-tracker.py:49-125`:
  - `tier_split` returns only `(title, line)` and splits on `## Universal` / `## Project:`.
  - The digest labels every journal entry Universal.
  - `parse_entries` returns `sig`, `trigger` and `source_contract`, with no line and no tier.
  - `SOURCE_LINE` stops at the first space and captures `N/A` as a value.
  - The hook already inserts the scripts folder on its path and imports `derive_area` and `accuracy_update` from it.
- `ASSUMED`: the host question tool takes up to four options per question and several questions per call. Matters because the applicability question is capped at 8 items in one call. Verification path: the Handoff 3 trial. If the limit is lower, lower the cap in the shape profile.
- `VERIFIED via check_version_bump.py:29-39`: `is_shipped` exempts `README.md`, `CONTRIBUTING.md`, `.claude/scripts/tests/`, `.claude/concepts/` and `.claude/work-items/`.
- `ASSUMED`: Python scripts cannot use the session's MCP connections, so the model must make the tool call. Matters because it fixes the split "script renders and validates, model calls". Verification path: Claude Code MCP documentation (context7).
- `VERIFIED via pr_merged.py:73-98`: `load_slot` returns nothing for placeholder, `none` and missing rows.
- `VERIFIED via .claude/work-item-conventions.json:87-103`: `contractLanding.verification.steps` is the configured verification runner input.
- `VERIFIED via grep of agents/, skills/, .claude/hooks/, .claude/scripts/`: no Terraform, Bicep, Kubernetes, AWS, Azure-cloud or GCP coverage exists.
- `VERIFIED via agents/*.md frontmatter`: every plugin agent declares a fixed `tools:` line; eight declare `memory: project` and two `memory: user`.
- `VERIFIED via .claude/area-mapping.json:14`: the area map is empty.
- `VERIFIED via glob`: `.claude/.scout-cache/registry-digest.md` and `.claude/registries/INTEGRATION.md` do not exist here.
- `ASSUMED` (Revision 8): `master` is at 8ea2dd4, with version 0.14.x, as fetched on 2026-11-03. The conflict list in block 17 was computed against that commit. Matters because a later `master` can add conflicts, or reach 0.15 and move the landing raise to 0.16.0. Verification path: block 17 lists git's own conflicts before resolving and aborts on an unlisted one; the landing's `--raise` always reads `origin/master` at landing time.
- `VERIFIED via the t18 review` (Revision 9): block 17 merged `master` at 274bf1e (#219, version 0.14.2), a descendant of 8ea2dd4, and git's conflict list was the five files block 17 named. `ASSUMED` (Revision 9): `origin/master` is at 0061212 (0.14.3), and its two commits after 274bf1e touch the four manifests, two test files, `.claude/work-item-conventions.json` and a brief, none of them a registry, `README.md`, a file block 17 resolved by hand, or a file block 17 text-fixed after the merge (`CONTRIBUTING.md`, `skills/auto-improve-finish-install/SKILL.md`) (t18 review I2, extended to the text-fix files). Matters because a file that both those commits and the parent branch changed after 274bf1e would make the landing's second merge conflict. Verification path: block 19 quotes `git diff --name-only 274bf1e origin/master` before editing and stops on an overlap with its stop list; block 20 runs `git merge-tree --write-tree --name-only <block 19 head> origin/master` and quotes the result.

---

## Failure Modes & Mitigations

- **FM:** memory server down, missing from the session, or hanging.
  - **Mitigation:** the tracker-cascade rule (check the tool list first), then one attempt only, bounded by the host's MCP timeout, with a deadline argument when the shape supports one. Any error or timeout records `unavailable (<reason>)`, prints one line and goes to Step 2. Never retried, never a blocking question.
- **FM:** any server-supplied field carries instructions or forges a brief line.
  - **Mitigation:** every field has a rule (safe-pattern ids, versions and references; closed sets for scope, status and provenance; cleaned and capped title and summary). Tests probe each field (journal 2026-10-05). Items are quoted data ranked below registries and the user.
- **FM:** an item shapes the draft before the user decides, or is used without being cited.
  - **Mitigation:** the applicability question comes before Step 2, and the architect receives only `applies` items. `check-contract` shows `not-cited` and `uncleared-item` at Step 3.
- **FM:** a stale or superseded item is applied silently.
  - **Mitigation:** the brief pins id@version. `changed-items` reports changes, and the only consequence is a follow-up stub the user agreed to.
- **FM:** a project name leaks into global memory.
  - **Mitigation:** a token hit lowers the scope to `project`. A missing or empty token list lowers every candidate (fail closed).
- **FM:** the same lesson is captured twice, or its receipt is lost.
  - **Mitigation:** capture happens only in step 5a, on the single live writing run that returned `flipped`. An entry is eligible only for the contract its own line names. Before anything is offered, `capture-candidates` checks that the linked brief is in `written_files` and refuses `brief-not-carried` otherwise, so nothing is sent without a receipt path. Receipts ride in the records pull request.
- **FM:** a capture server that hangs stalls delivery once per candidate.
  - **Mitigation:** the stop rule. At the first failure or timeout the step stops sending, writes the rest as `Not sent: (stopped after <reason>)` and continues delivery, so the cost is at most one host timeout.
- **FM:** memory off still changes a brief or a flow.
  - **Mitigation:** I-M0. `record` refuses `not-enabled`. The parity test compares fixture briefs byte-for-byte and pins `/task`'s brief template.
- **FM:** capture turns into indiscriminate logging.
  - **Mitigation:** only registry entries that name this contract are eligible, the user confirms each batch, and nothing is captured with memory disabled.
- **FM:** a tool rename in the memory repository breaks the plugin.
  - **Mitigation:** the names are slots, and the shapes are one profile in one script. The text scan proves no other file names them.
- **FM:** an agent runs `terraform apply` or deletes a cloud database.
  - **Mitigation:** the scope rule in the skill and agent text says they never run such a command and hand it to the user instead. `test_cloud_text_scans.py` pins that the shipped text never presents one as something to run. The user's normal Claude Code permission prompts and the existing database guards apply unchanged. Verification uses only non-mutating steps. Residual risk, accepted by the user's instruction: no new hook or rule enforces this at run time.
- **FM:** a `/design-first` run in a project without the script (old vendored copy).
  - **Mitigation:** the lookup block returns empty, which reads as `disabled`. Never a halt, because memory is optional.
- **FM (Revision 7):** finish-install's doctor check cannot find the plugin root and prints `plugin:  NOT FOUND - pass --plugin`, so the registry copies would be left `UNRESOLVED` while the skill goes on.
  - **Mitigation:** the **plugin doctor**'s own report line is the signal (`plugin_doctor.py` report mode, `apply_fixes` `unresolved` list). The finish-install section reads it, says in one line that the registries cannot be seeded, and asks for the plugin path to pass as `--plugin` before offering `--fix`. It never reports the registries as present.
- **FM (Revision 7):** `record` refuses, or no brief exists, on the `unconfigured` path of Step 1.5.
  - **Mitigation:** the **Brief linkage** rule already used by point 4 (the brief whose `branch:` is the current branch) picks the brief. With no brief, one "skipped for want of a brief" line is printed and design continues; this is not a failure. A refusal when a brief was found falls to point 2's one-line failure rule (tracker-cascade degradation, consumed as-is), and design continues from the Project history record.
- **FM (Revision 7):** `plugin_doctor.py --fix` creates more than the user expected (north-stars and orchestrator folders, the contract template, the `area-mapping.json` and `work-item-conventions.json` scaffolds).
  - **Mitigation:** report then ask. The **plugin doctor**'s report mode lists every `missing` entry first; finish-install shows that list as what `--fix` would create and runs `--fix` only on the user's yes, matching the skill's own "It proposes, you confirm, and only then does it write". `apply_fixes` never overwrites and leaves `.claude/settings.json` to the user.
- **FM (Revision 8):** while resolving a registry conflict by hand (block 17), an entry of either side is dropped, duplicated or edited.
  - **Mitigation:** append-only registries (registry "Maintained by" rule). Block 18 compares every entry heading against `git show origin/master:<path>` and against the pre-merge parent tip. Each must appear once, unedited, with master's entries first.
- **FM (Revision 8):** an auto-merged script or test defines a name twice or drops an import.
  - **Mitigation:** the **Parent Branch Delivery Rule** review gate (block 18) checks for duplicates. The landing's own verification step (`contractLanding.verification.steps`, `test_pr_merged.py`) runs on the merged tree, and block 17 stops instead of hand-editing an auto-merged file.
- **FM (Revision 8):** `master` appends to a registry tail again after block 17, so the landing halts at P7 a second time.
  - **Mitigation:** the landing's P7 gate (`land_contract.py`) reports it with the same remedy. A further remedy block on the same pattern merges again; nothing reaches `master` in a broken state.
- **FM (Revision 8):** README counts are wrong after the merge (each side's count is copied, or the two are added).
  - **Mitigation:** block 17 rewrites every count from the merged tree and from each suite's own output (journal 2026-11-01, "After merging a base..."). Block 18 re-checks the counts, and `test_plugin_manifests.py` checks the README counts it pins.
- **FM (Revision 9):** deleting the stale steps 6-9 silently widens a pinned test. `test_parent_branch_rule_text.py` (class `CaptureAtDeliveryTextTests`, the step 5a test) ends step 5a's section at the heading `6. **Cut the branch`, which block 19 deletes. Its `section` helper then runs to the end of the file and still passes, so it stops pinning step 5a alone.
  - **Mitigation:** block 19 moves the end marker to master's step 6 heading (`6. **Put the stable branch`) and adds a pin that each numbered step of the records procedure appears exactly once and in order (journal 2026-10-15, "A skill that edits a block pinned by a lookup-block test must name that test").
- **FM (Revision 9):** a `master` commit after 274bf1e changes a file the parent branch changed after 274bf1e (block 19's files, the three registries, or block 17's text-fix files `CONTRIBUTING.md` and `skills/auto-improve-finish-install/SKILL.md`), so the landing's second merge conflicts.
  - **Mitigation:** block 19 checks the overlap against that stop list before editing and stops on one; block 20 quotes `git merge-tree` against `origin/master`; the landing's P7 gate (`land_contract.py`) remains the backstop, with the Revision 8 remedy pattern.
- **FM (Revision 9):** the re-review passes, but the landing still reads block 18's `blocked` artefact as effective and halts at P3 again.
  - **Mitigation:** the review layer's supersession edge (`read_review_set` in `pr_merged.py`, the Gate Output `supersedes` field), used by blocks 13 and 16. Block 20's Gate Output lists the t18 artefact in `supersedes`.
- **FM (Revision 9):** a review artefact is committed with a placeholder evidence row (the t18 artefact's `SUITES_PENDING`), so a reader cannot tell a suite that passed from one that never ran.
  - **Mitigation:** block 20's constraints forbid placeholder rows: every suite gets a row with its exit code and case count, and a suite that could not finish gets a row stating that, reported as a finding.

---

## Open Questions for User

All 21 questions are resolved and shrunk to one line each, as the template's revision rule asks. Revisions 3 and 4 add no new Open Question. Revision 4 amends the recorded answer to question 6 (capture becomes its own question after the flip), as the user accepted with the round-3 recommendations.

- [x] **1. Parent issue** — open one. Answered: accepted recommendation (user, 2026-11-01). The main session is opening it; the number goes into the brief.
- [x] **2. Captured status always `proposed`** — Answered: accepted recommendation (user, 2026-11-01).
- [x] **3. `ASSUMED` lines never captured in v1** — Answered: accepted recommendation (user, 2026-11-01).
- [x] **4. Brief holds ids, versions, labels, titles and decisions only, no content** — Answered: accepted recommendation (user, 2026-11-01).
- [x] **5. Retrieval only at `/design-first` Step 1.5** — Answered: accepted recommendation (user, 2026-11-01).
- [x] **6. Capture at the `/pr-merged` flip, one confirmation per batch** — Answered: accepted recommendation (user, 2026-11-01). Amended in Revision 2: the "plus `/journal-add`" half is withdrawn, because the critic showed it has no data path, contradicts that skill's own limits and would send unshipped knowledge. Amended again in Revision 4 (critic round 3): the batch is offered in **its own question, asked after the writing run returns `flipped`**, on both `/pr-merged` and `/flow`. It is not folded into the earlier records confirmation, because that confirmation precedes the flip. This changes when the one-confirmation-per-batch is asked, not that it is one; the user accepted it with the round-3 recommendations (2026-11-01).
- [x] **7. Shapes live in a shape profile inside `memory_boundary.py`** — Answered: accepted recommendation (user, 2026-11-01).
- [x] **8. Project-name hit lowers scope to `project`, shown in the confirmation** — Answered: accepted recommendation (user, 2026-11-01).
- [x] **9. A local registry entry wins over a conflicting item until the user decides** — Answered: accepted recommendation (user, 2026-11-01).
- [x] **10. New `cloud-engineer` agent; review in `security-auditor`** — Answered: accepted recommendation (user, 2026-11-01).
- [x] **11. Deployment authorization mechanism** — Answered: user removed the mechanism (2026-11-01). The earlier accepted answer (host `permissions.ask` rows after a live trial, with an add-on hook as fallback) is withdrawn. The text-only rule replaces it (Decision note).
- [x] **12. Only the `cloud.mcp-server` slot now; adapter deferred** — Answered: accepted recommendation (user, 2026-11-01).
- [x] **13. Token-efficiency fixes in a separate contract** — Answered: accepted recommendation (user, 2026-11-01).
- [x] **14. Keep the appendices until approval, then move them to `.claude/contract-history/`** — Answered: accepted recommendation (user, 2026-11-01).
- [x] **15. The landing corrects the manifest counts** — Answered: accepted recommendation (user, 2026-11-01).
- [x] **16. Unreachable mid-task: one line and continue** — Answered: accepted recommendation (user, 2026-11-01).
- [x] **17. Build against provisional shape `v0` now; `memory.shape` set only once the memory repository confirms it** — Answered: accepted recommendation (user, 2026-11-01).
- [x] **18. Manual and post-approval journal entries are not captured in v1** — Answered: accepted recommendation (user, 2026-11-01).
- [x] **19. A missing or empty project-name token list lowers every candidate to `project` (fail closed)** — Answered: accepted recommendation (user, 2026-11-01).
- [x] **20. Registry appends in the documentation block, not in its review gate** — Answered: accepted recommendation (user, 2026-11-01). After the Revision 5 renumbering, these are Handoffs 9 and 10.
- [x] **21. Accept the Step 1.5 applicability question as a `/flow` stop (only when memory is enabled and items came back)** — Answered: accepted recommendation (user, 2026-11-01). It is now listed in `/flow`'s operator stops (Handoff 3).

Revision 7 adds two questions. The user answered both on 2026-11-02, and the answers are written into the body below.

- [x] **22. `INTEGRATION.md` has no seed.** Answered: "Name it, add no seed" (user, 2026-11-02). The term lists `INTEGRATION.md` "where the project keeps one"; this contract adds no seed or template for it.
  → Addressed by: Business Concept term **Project history record**; block 15 TASK point 1 and the shipped agreement; block 15 CONSTRAINTS (no seed, no change to the doctor's `REQUIREMENTS`).
- [x] **23. Registries missing in a project that already has a profile.** Answered: "Report, then ask before --fix" (user, 2026-11-02). Finish-install runs the doctor in report mode, lists exactly what `--fix` would create, and writes only after the user confirms. It never runs `--fix` on its own. `--fix` creates every missing requirement in `plugin_doctor.py` `REQUIREMENTS` (via `apply_fixes`), including `.claude/north-stars`, `.claude/orchestrator/results`, `area-mapping.json`, `work-item-conventions.json` and the contract template, not only the registries.
  → Addressed by: Extension Points bullet `/auto-improve-finish-install`; Failure Modes entries on `NOT FOUND - pass --plugin` and on `--fix` creating more than expected; block 15 TASK point 1.

Revision 8 adds five questions. The user answered all five on 2026-11-03, and the answers are written into block 17. Only the final approval is still open.

- [x] **24. The conflicting-file list.** Answered by a computed fact (2026-11-03, `master` at 8ea2dd4). `git merge-tree` reports conflicts in exactly JOURNAL.md, MECHANISMS.md, VOCABULARY.md, README.md and `skills/pr-merged/references/contract-completion.md`. It auto-merges `pr_merged.py`, `test_pr_merged.py`, `skills/flow/SKILL.md` and `skills/pr-merged/SKILL.md`.
  → Addressed by: block 17, "Conflicting files" and Files to touch (the five conflicts plus the two text-fix files); block 18's file-scope rule; the stop-and-`git merge --abort` fallback kept.
- [x] **25. Which Revision 7 critic findings get a journal entry (t10 W2).** Answered: append J1-J10. The parent brief records "no new entry" for the five findings that re-apply existing lessons, and that critique rounds 1-3 were not journaled (user, 2026-11-03).
  → Addressed by: block 17, "Journal entries" and the W2 bullet of its TASK; "Main-session actions".
- [x] **26. Append the t10 review's proposed entry (J11).** Answered: yes, verbatim from t10 Disposition 7 (user, 2026-11-03).
  → Addressed by: block 17, J11 and the W2 bullet of its TASK.
- [x] **27. Fix the same false sentence in finish-install (t10 I3).** Answered: yes, in both `README.md` and `skills/auto-improve-finish-install/SKILL.md`. Everything else left over (t16 W1 and I1-I5; t10 I4 and I6) goes into one follow-up stub (user, 2026-11-03).
  → Addressed by: block 17's I3 bullet and Files to touch; "Deferred review leftovers" names `.claude/concepts/followups/2026-11-03-memory-boundary-review-leftovers.followup.md`, `**Issue:** pending`.
- [x] **28. The version after the remedy.** Answered: accepted (user, 2026-11-03). The remedy pull requests keep merged `master`'s 0.14.x, no version file is edited by hand, and the landing raises to 0.15.0 while `master` is on 0.14.
  → Addressed by: block 17, "Version".

Revision 9 adds five questions. The user answered 29-32 on 2026-11-03, accepting each recommendation, and the answers are written into blocks 19 and 20. Question 33 was added when the `## Critique (Revision 9)` warnings were folded in, and the user answered it the same day: one small pull request to `master` after the landing.

- [x] **29. What happens to the t18 review artefact, which still holds the placeholder row `SUITES_PENDING` and a stale "hook suites: see Evidence" bullet?** Recommendation: leave it unedited, as the recorded `blocked` verdict it is. Block 20's new artefact supersedes it through its Gate Output, the way block 16 superseded block 5 and block 13 superseded block 8. Block 20's Evidence carries the full suite table, and the Revision 9 note under block 19 keeps the rows the t18 reviewer reported in its hand-back. Why not edit it: a review artefact is the loop's record of what one gate saw at one commit, and rewriting it after the fact makes "reviewed" and "patched later" indistinguishable. The alternative is to add the t18 file to block 19's Files to touch and replace the two lines.
  Answered: no edit. Leave the t18 review file untouched as the recorded `blocked` verdict; block 20's new review supersedes it (user, 2026-11-03).
  → Written into: block 20 (Supersedes, Gate Output `supersedes`, "do not edit the t18 artefact"); block 19 CONSTRAINTS.
- [x] **30. Pinning the README folder-tree counts in `test_repo_consistency.py` (the t18 reviewer's F2).** Recommendation: a follow-up stub, not a block. Block 19 rewrites the four wrong counts. The pin is a new check with design choices of its own: which tree lines it reads, how it tells a helper module from a workflow script, and whether every future pull request that adds a test must edit the README. It also does not fix anything the review blocked on (journal 2026-11-02, "Keep a review-fix block to the review's findings"). Stub: `.claude/concepts/followups/2026-11-03-readme-tree-counts-and-step-pins.followup.md`, `**Issue:** pending`. Its file name is kept as first written; the step pin itself is delivered by block 19 (Question 31), and the stub says so.
  Answered: a follow-up stub, not a block (user, 2026-11-03).
  → Written into: block 19 (no `test_repo_consistency.py` change); the stub.
- [x] **31. Add a pin for the records-procedure step order in block 19 (t18 Disposition 1).** Recommendation: yes. Block 19 already has to edit `test_parent_branch_rule_text.py`, because the step 5a test ends its section at the heading block 19 deletes. A test that each of steps 1-9 and 5a appears exactly once and in order, plus a control with a planted duplicate step, is what would have caught B1. No suite caught it, because every line master added was present. The alternative is to fix only the end marker and add the pin to the Question 30 stub.
  Answered: yes, block 19 adds the step-order test (user, 2026-11-03).
  → Written into: block 19 TASK, "Test" bullet.
- [x] **32. The B1 journal entry (J12).** Recommendation: append it in block 19, verbatim from the t18 artefact's Disposition item 4, as Trigger `post-impl divergence`. It rides in the sub-task commit for the reasons block 17 gave for J1-J11: an entry appended after the landing's flip is never offered for capture, and the landing's raise commit carries only the manifests. No version file is touched; the landing raises once (Parent Branch Delivery Rule). The alternative is to leave it to the main session at the landing.
  Answered: yes, block 19 appends J12 word for word (user, 2026-11-03).
  → Written into: block 19 TASK, "J12" bullet, and Files to touch.
- [x] **33. Who corrects the manifest descriptions, which still say "28 skills" (and 14 agents) while the tree has 33 skills and 15 agents (t18 I1)?** Block 11 and Open Question 15 say the landing corrects them, but the landing's only manifest write is `check_version_bump.py` `raise_manifests`, which rewrites the `"version"` fields alone (Critique Revision 9). No sub-task may list a version file, so no block of this contract can fix them either. Recommendation: one small pull request to `master` after the landing, which corrects the description strings in `plugin.json`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json` and `.claude-plugin/marketplace.json` from the tree's own counts and takes the patch raise the version rule requires (0.15.1 if the landing raises to 0.15.0). It is recorded in the stub (`2026-11-03-readme-tree-counts-and-step-pins.followup.md`), so it has a tracking issue. Alternatives: under `landing: manual`, the operator edits the descriptions in the landing's raise commit, which saves one release but is a hand edit no gate reviews; or the landing script gains a description rewrite, which is a change to `land_contract.py` and its own contract. Blocks 19 and 20 are the same under every answer; this question does not hold up their dispatch.
  Answered: one small pull request to `master` after the landing, as recommended (user, 2026-11-03).
  → Written into: the stub; the Revision 9 pointer under block 11; block 19's Revision 9 note.

Revision 7 also took one decision outside the numbered questions: "Yes, add a session-start agreement" (user, 2026-11-02), in answer to the critic's WARN on reach. → Addressed by: Extension Points bullet "Shipped agreements"; Alternatives Considered Options I, J and K; block 15 TASK point 5. The user also renamed the proposed term "Project memory" to **Project history record** and narrowed its definition. → Addressed by: Business Concept, and every Revision 7 mention in this contract outside the critique sections, which keep the old name as history.

---

## Critique

**Critic:** contract-critic
**Date:** 2026-11-01
**Verdict:** blockers-found

### Findings

- **[BLOCKER] `capture-candidates` adds a third registry-entry parser beside two that already split tiers and read Trigger and Source contract**
  - **What is wrong:** the design has the adapter read MECHANISMS, VOCABULARY and JOURNAL itself (tier gives scope, Trigger gives provenance, the entry must "name this contract"). Two existing readers already do that work. `generate_registry_digest.py:55-68` (`tier_split`, `BULLET` and `DATED` patterns) splits the Universal and Project tiers. `.claude/hooks/journal-post-approval-tracker.py:68-70,94` (`ENTRY_HEADER`, `TRIGGER_LINE`, `SOURCE_LINE`, `parse_entries`) reads the Trigger and the Source contract, backticks included. Neither is cited. A new parser will also miss forms the existing ones were built around, such as JOURNAL.md:308, where the Source contract is an absolute Windows path, not `.claude/concepts/<slug>.md`. The contract also never says which project-tier layout the adapter reads: the `## Project:` heading (MECHANISMS.md:52) or the per-domain files (MECHANISMS.md:63). Neither exists in this repository.
  - **Prior artifact ignored:** `MECHANISMS.md:63` (Two-tier registry with a generated complete index: "add a registry and it needs one emit_group call plus its entry pattern"); `JOURNAL.md` 2026-10-15 "Reuse the existing brief-linkage reader; a second one misses edge cases"; 2026-10-30 "One shared reader must own the filtering, not only the selection".
  - **Where in this contract:** `## Data Shapes → Value Objects` "Capture candidate": "Produced by `capture-candidates` only from registry entries that name this contract"; `## New Mechanisms` "turns registry entries into capture candidates".
  → Addressed by: Data Shapes "Candidate reading": the adapter reuses `tier_split` (`## Universal` / `## Project:` layout, plus per-domain files as the digest generator treats them) and `parse_entries`, loaded by path. Slugs match by the `brief_names_contract` stem rule with both separators, so an absolute Windows path matches. Any missing form is fixed in those functions, never re-parsed.
- **[BLOCKER] Capture receipts written at `/pr-merged` are not carried by the records pull request, so the anti-duplicate invariant and a clean tree both fail**
  - **What is wrong:** the records pull request carries "exactly the union of `written_files`" from `pr_merged.py` writing runs, after "the one confirmation". `memory_boundary.py record` writes `Captured:` lines into the brief outside those runs, and the contract never says whether this happens before or after step 6 or 7. If it happens before, the brief change is not in `written_files` and is dropped. If after, it is left uncommitted in the starting tree. Either way the receipt never reaches `origin/<default>`, so the next run offers the same entry again (the "same lesson is captured twice" Failure Mode is not mitigated). The leftover edit also keeps the tree from Delivery cleanup, which removes only clean or landed-identical trees. Under `/flow`, Step 8 is the single confirmation, and the extra multi-select question breaks that.
  - **Prior artifact ignored:** `skills/pr-merged/references/contract-completion.md:45-59`; `MECHANISMS.md:75` (Delivery cleanup: clean status / Landed untracked file); `JOURNAL.md` 2026-10-30 "A delivery rule must name every route into delivery" (the `/flow` route of capture is not in the route table).
  - **Where in this contract:** `## Extension Points`: "after the verdict `flipped` ... offer the candidates once ... Send the chosen ones and record the receipts"; Handoff 4 constraint "never resend a receipted entry".
  → Addressed by: the candidates join step 3's one confirmation (and `/flow` Step 8's), with no second question. Sending and `record --receipts` run between step 5 and step 7, into the linked brief, which a flip already puts in `written_files` (`pr_merged.py:3851,4796`). `record` refuses `brief-not-carried` otherwise. No repeat: capture happens only on the single flip, entries are eligible only for the contract they name, and keys already on `Captured:` lines are skipped.
- **[BLOCKER] Only the title and summary are neutralised, but the brief and the Open Questions also echo other fields that come from the memory server**
  - **What is wrong:** the Data Shapes row and the Handoff 2 TASK block neutralise "Title and summary" only. The `Retrieved:` lines and the Open Questions also echo `id`, `version`, `superseded_by`, `conflicts_with` and "source provenance as the memory system reports it". Those are not closed sets, and nothing neutralises them. A line separator in `version` forges a brief line, and the brief is committed. `## Lessons referenced` says "(title, summary, ids)", which contradicts the Data Shapes row the implementer follows.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-05 "Neutralise every field echoed from untrusted input, not only the body" ("List every output field built from untrusted input and probe each with the payload").
  - **Where in this contract:** `## Data Shapes → Value Objects` "Retrieved memory item": "Title and summary are neutralised"; Handoff 2: "neutralises titles and summaries".
  → Addressed by: the "Retrieved memory item" row now gives a rule for every field (safe-pattern id, version, superseded_by and conflicts_with; closed sets for scope, status and provenance; cleaned and capped title and summary), with uniqueness and a per-field probe test. Handoff 2 and Lessons referenced match it.
- **[BLOCKER] With memory off, every design still writes a new brief section, which contradicts the acceptance criterion, and the "test proves this" covers only the script**
  - **What is wrong:** the brief requires that with memory off "every existing skill and flow behaves as it does today. A test proves this." Step 1.5 still runs a script and writes a `Memory: disabled` line into every brief when memory is off (Handoff 3: "otherwise record the one Memory line and go on"; Handoff 2's degradation test: "record writes exactly one Memory: line"). The only proof offered is a unit test of the script. Appendix C's criterion, "a disabled project's `/design-first` text path is unchanged apart from one guarded step", cannot be checked mechanically.
  - **Prior artifact ignored:** `.claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md:30` (acceptance criterion 3).
  - **Where in this contract:** `## Data Shapes → Entities` I-M1; Handoff 3 TASK; Appendix C P2 "Validation criterion".
  → Addressed by: I-M0 (disabled writes and prints nothing; `/task` is untouched; `record` refuses `not-enabled`). Handoff 3 adds `test_memory_off_parity.py`. It runs the Step 1.5 commands with memory off against copies of every existing brief and the fixture briefs, diffs each byte-for-byte against the original, checks no file appeared, and pins the hash of `/task`'s brief template block taken at `master` 6d1ca0c.
- **[WARN] The provenance mapping overstates where knowledge came from, and `test-confirmed` cannot be derived**
  - **What is wrong:** it maps `manual` and `post-approval` to `user-decision`, but `/journal-add` entries are drafted by the main session and only collected through questions. It maps `post-impl divergence` to `source-code-fact`, but that Trigger is an agent's judgement. It requires `test-confirmed` to come from "the source review artefact's `## Evidence`", but the journal entry shape has no field that links an entry to a review artefact, and the capture "evidence (merged pull-request link, review artefact path)" has no source field either. The claim "The journal Trigger set already contains every value" is also false: the journal header lists three Triggers, and `post-approval` exists only in `/journal-add`.
  - **Prior artifact ignored:** `JOURNAL.md:20` (entry shape); `MECHANISMS.md:41` (three triggers); `skills/journal-add/SKILL.md:28-34`.
  - **Where in this contract:** `## Data Shapes` "Provenance mapping" table; `## Reused Mechanisms` "Persistence check".
  → Addressed by: the provenance table now takes the weakest value the evidence supports. `manual` and `post-approval` become `ai-hypothesis` (not offered; Open Question 18). `post-impl divergence` is `source-code-fact` only when the contract is implemented at origin. `test-confirmed` is never claimed in v1. The "every value" claim is corrected to three plus `post-approval`.
- **[WARN] `/journal-add` Step 4.5 has no specified data path and contradicts the skill's own limits**
  - **What is wrong:** `/journal-add` declares that it "Does NOT write to any file other than JOURNAL.md" and "Does NOT trigger any agent or downstream workflow". A standalone run has no brief to hold a `Captured:` receipt. The only candidate command, `capture-candidates --contract <slug>`, refuses with `contract-not-implemented`. A `post-approval` entry on a contract that has not been delivered would also be sent before merge, the exact case Open Question 6 rejects as "unshipped knowledge".
  - **Prior artifact ignored:** `skills/journal-add/SKILL.md:108,111`.
  - **Where in this contract:** `## Extension Points` "`/journal-add` new Step 4.5"; `## Data Shapes → Commands` "List capture candidates".
  → Addressed by: `/journal-add` is no longer touched. Step 4.5 is removed, Handoff 4 drops the file, the route table shows "none in v1", and Open Question 6 is amended.
- **[WARN] The project-name downgrade does nothing by default**
  - **What is wrong:** `.claude/.project-tokens.json` ships as a TEMPLATE with `"tokens": []`, and the sync tool owns it. A plugin-install consumer may not have it at all. The contract gives neither the location it reads nor the behaviour when the file is missing or empty. The Failure Mode "a project name leaks into global memory" is therefore unmitigated unless the project has filled the list.
  - **Prior artifact ignored:** `MECHANISMS.md:54` (Project-name check); `JOURNAL.md` 2026-10-05 "A documented 'missing file means the default' must read one named location only".
  - **Where in this contract:** `## Failure Modes & Mitigations`: "the project-name check tokens downgrade a hit to `project` scope".
  → Addressed by: the list is read from `<project>/.claude/.project-tokens.json` only. The contract states that an empty list makes the token check inert, and makes a missing or empty list fail closed: every candidate is lowered to `project` (Open Question 19).
- **[WARN] A slow memory server can stall design, because nothing owns a timeout**
  - **What is wrong:** the model makes the MCP call at Step 1.5, before the architect runs. The outcome reason `timeout` exists, but no component measures time or sets a bound. The cited mitigation, the tracker-cascade rule, covers only whether the tool is present. A server that is present but hangs makes every M/L/XL design wait on memory.
  - **Prior artifact ignored:** `skills/task/SKILL.md:51` (availability means "the tool exists in this session", which says nothing about latency).
  - **Where in this contract:** `## Failure Modes & Mitigations`: "the tracker-cascade availability rule. Check the tool list first."
  → Addressed by: one attempt, no retry. The bound is the host MCP timeout, plus a deadline argument where the shape supports it. Expiry or error means one line and continue. An ASSUMED item gives the verification path, and the Handoff 3 trial includes a server that never answers.
- **[WARN] Drift notices become follow-up stubs that do not fit the stub template and are filed under the wrong contract**
  - **What is wrong:** the stub template requires `**Parent contract:**` and `**Derived from:** Adjacent Areas scan, area, score`. At Step 1.5 the current contract does not exist yet, and the drift belongs to other briefs' items. Step 3.4 only opens an issue for stubs the current contract cites, as "Follow-ups from <this contract>", so the drift is filed against the wrong contract. Nobody asks the user before a stub is written. Drift is found only for items that the current targeted query happens to return again, so the acceptance criterion "superseded entries are reported" is met only partly.
  - **Prior artifact ignored:** `.claude/templates/followup-stub.md:3-4`; `skills/design-first/SKILL.md:237`.
  - **Where in this contract:** `## Reused Mechanisms`: "**Follow-up stub** ... consumed as-is"; `## Data Shapes → Events` "MemoryDriftNoticed".
  → Addressed by: change notices are shown at Step 3, and a stub is written only on the user's yes. Its `Parent contract:` is the contract being designed (it does exist by Step 3) and `Derived from:` names the change notice and the affected briefs, so Step 3.4 files it correctly. Partial coverage (only re-returned items) is now a stated Non-Goal and limitation.
- **[WARN] The architect decides `not-used` for itself, so whether a retrieved item silently influenced the draft cannot be checked**
  - **What is wrong:** the architect receives every item in its PRIOR_FINDINGS at Step 2 and drafts with them before the user decides anything. Only the items the architect *says* it relied on become Open Questions. `not-used` is recorded on the architect's own word. If the user answers `does-not-apply`, the draft body still reflects the item.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-22 "An accepted critic WARN or answered Open Question must amend the contract body before approval".
  - **Where in this contract:** `## Business Concept` "Applicability decision": "`not-used` marks an item that influenced nothing and so needed no decision".
  → Addressed by: applicability is asked at Step 1.5, before the draft, and the architect receives only `applies` items. `not-used` is replaced by the derived `cited` / `not-cited` from `check-contract`, which also reports `uncleared-item`. The new stop is Open Question 21.
- **[WARN] When `cloud-permissions` has not been run, deployment authorization fails open**
  - **What is wrong:** the host "ask" rows exist only if the user runs the optional finish-install subcommand. Setting `cloud.providers` turns the agent on whether or not the rows exist, and neither the agent nor the doctor checks for them. What remains is agent text alone, the option Open Question 11 rejects.
  - **Prior artifact ignored:** `MECHANISMS.md:56` (Guard rules file: "A hook that BLOCKS fails closed"); brief acceptance criterion 11 (line 38).
  - **Where in this contract:** `## Business Concept` "Deployment authorization ... The host asks for it"; Handoff 7 refusal conditions, which do not mention the rows.
  → Addressed by: `cloud-permissions --check` (read-only). The cloud agent and skill refuse on any non-zero exit, a missing script or a timeout (fail closed). Handoff 8 now comes before Handoff 7 in the dependency order, and Handoff 7's refusal conditions name the check.
- **[WARN] The single-adapter scan defines no file set, and Handoff 10 may break it**
  - **What is wrong:** "no shipped file except `memory_boundary.py`" does not define "shipped". The two test files in Handoff 2 contain the literals, and Handoff 10's README must document the boundary in the acceptance criterion's own words (`memory_retrieve`, `memory_capture`). Handoff 10 does not mention the scan. Appendix C P5's "no mutating instruction (text scan)" has no handoff block that writes that scan.
  - **Prior artifact ignored:** `.claude/scripts/check_version_bump.py:29-39` (the only defined `is_shipped`, which exempts README.md and tests).
  - **Where in this contract:** Handoff 2 scan constraint; Handoff 10 TASK; Appendix C P5.
  → Addressed by: the scan's file set is every path `check_version_bump.is_shipped` returns true for. README, CONTRIBUTING and tests are exempt by that rule, so Handoff 10 may name the tools; Handoff 10 now says so. The mutating-instruction scan is `test_cloud_text_scans.py`, in Handoff 6.
- **[WARN] The bare word `drift` gets a third meaning**
  - **What is wrong:** the subcommand `drift`, the event `MemoryDriftNoticed` and the shape "Memory drift notice" add a meaning the registry already warns against. "Memory drift notice" is also missing from the proposed terms.
  - **Prior artifact ignored:** `VOCABULARY.md:36` (Vendored-asset drift: "the bare word *drift* already means generated output no longer matching its source").
  - **Where in this contract:** `## Data Shapes → Commands` "Detect drift".
  → Addressed by: the subcommand is renamed `changed-items`, the event `MemoryChangeNoticed` and the shape "Memory change notice", now in the proposed terms.
- **[WARN] Shape `v0` is called a guess, but the adapter is built and tested against it**
  - **What is wrong:** whether Handoff 2 should wait for the memory repository's published schema is an open decision. The contract records it as an assumption instead of an Open Question.
  - **Prior artifact ignored:** `agents/contract-critic.md` checklist item 4 (hidden Open Questions).
  - **Where in this contract:** `## Uncertain Assumptions`: "until then shape `v0` is a guess".
  → Addressed by: the decision is now Open Question 17 with a recommendation (build now; `v0` provisional; the state stays `unconfigured` until the memory repository confirms the shape).
- **[WARN] The registry appends in Handoff 11 are not in its Files to touch**
  - **What is wrong:** a review-gate block names exactly one path, the review artefact. Handoff 11 still tells the reviewer to append to MECHANISMS and VOCABULARY, and section 12 says "Registry appends ... ride with block 11".
  - **Prior artifact ignored:** `.claude/concepts/2026-10-22-registries-version-gap.md` (Critique BLOCKER: a review sub-task must not append to registries; report the append in its handoff instead).
  - **Where in this contract:** Handoff 11 constraint "As janitor, append the Memory adapter mechanism and the confirmed vocabulary to the registries".
  → Addressed by: the appends moved to Handoff 10 (an implementer block whose Files to touch now lists `.claude/registries/MECHANISMS.md` and `VOCABULARY.md`). Handoff 11 keeps its one artefact path and only checks the appends. This differs from the coordinator's literal request; see Open Question 20.
- **[NIT] Calling the Central Memory System "the port" misuses the term** — a Port is "an interface declared by the domain" (`VOCABULARY.md:22`), not the external system.
- **[NIT] "The plugin never sets it" contradicts the capture candidate's `claimed status (always proposed)`** — `## Business Concept` "Memory status".
- **[NIT] Scope is said to map "one-to-one" to the tiers, but the token downgrade breaks that mapping, and `global` is used as a synonym for the Universal tier** — `## Business Concept` "Memory scope".
- **[NIT] Five new value objects are not proposed for VOCABULARY.md** — Memory exchange outcome, Retrieval request, Capture candidate, Capture receipt, Memory drift notice.
- **[NIT] The Value Object rows do not state uniqueness** — for example, two items with the same id but different versions or scopes in one response, and the key of a Capture receipt.
- **[NIT] Handoffs 3 and 4 edit sentence-pinned skills without listing the test that pins them** — `test_repo_consistency.py:54-56` (`SENTENCE_PLACEMENT`) pins sentences in `skills/design-first/SKILL.md` and `skills/journal-add/SKILL.md`.
- **[NIT] Adjacent Areas is not the exact single exception line** — the extra note defers a confirmation scan to the main session. The area map is empty, so no area can score.
- **[NIT] Chat Tool Impact uses the wording "2. No.", not one of the three sanctioned answers** — no REST, SignalR or DTO surface exists, so this is wording only.

### Applicable journal entries

- **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work** — heeded by the Handoff 3 and Handoff 8 preconditions.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded; `pr_merged.py:85-103` confirmed for placeholder, `none` and missing row.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded by Handoff 11.
- **2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control** — heeded by the planted made-up file in Handoff 2.
- **2026-10-05 — Text delivered to the model must say which rule wins against a skill's gate** — heeded by the data-architect "Memory items" rule.
- **2026-10-05 — Neutralise every field echoed from untrusted input, not only the body** — violated, see BLOCKER above.
- **2026-10-05 — A documented "missing file means the default" must read one named location only** — not addressed for `.project-tokens.json`, see WARN above.
- **2026-10-15 — A script that reads a project-owned file must be told which project** — heeded by `--project <root>` on every subcommand.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded in Handoffs 3 and 4.
- **2026-10-15 — Reuse the existing brief-linkage reader** — heeded for briefs (`select_linked_brief`); the same lesson is violated for registry entries, see BLOCKER above.
- **2026-10-16 — A "missing project file" refusal must cover both the unset root and the set-but-absent file** — heeded, deliberately fail-soft.
- **2026-10-16 — Never let free text start an argument handed to a native program from Git Bash** — heeded; the query and responses pass through files (`--brief`, `--input`).
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body** — noted for approval; see the `not-used` WARN.
- **2026-10-28 — State the real trigger of a hook** — heeded; no hook is added.
- **2026-10-28 — A new term's definition must be true against every existing member** — heeded for *Central Memory System*; *Deployment authorization* ("The host asks") is not true without the rows, see WARN.
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam** — heeded; `cloud-permissions` extends Preview-hash apply, as its Extend-by line in `MECHANISMS.md:64` allows.
- **2026-10-30 — A delivery rule must name every route into delivery** — partly heeded by the route table; the `/flow` Step 8 capture route is missing, see BLOCKER above.
- **2026-10-30 — One shared reader must own the filtering** — violated for registry entries, see BLOCKER above.
- **2026-11-01 — A shared reader reused by a stricter consumer must be re-checked** — not addressed, but the contract did not need to: `load_slot` is reused for the kind of value it already reads.

### What the critic did not check

- `pr_merged.py --contract <slug> --status --json` (checklist item 14): the critic has no shell. No handoff block lists a file from `MANIFESTS` (`check_version_bump.py:25`). Open Question 1 (parent issue `pending`) will raise the `no-parent-issue` Layout defect until it is answered.
- `derive_area.py` / `cross_area_scan.py`: no shell. `.claude/area-mapping.json` is empty, so no area can score.
- North-star alignment: `.claude/north-stars/` does not exist, so item 13 produces no findings.
- The architect's claims about missing registries are confirmed: `.claude/registries/` holds only MECHANISMS.md, VOCABULARY.md and JOURNAL.md, with no project tier and no per-domain files, and neither `INTEGRATION.md` nor `.claude/.scout-cache/registry-digest.md` exists. Only the Universal-tier reuse and vocabulary checks were applied.
- Claude Code MCP tool naming and `permissions.ask` matching for compound commands were not checked against host documentation. Both are left to the trials the contract names.

---

## Critique (revision 2)

**Critic:** contract-critic (second pass, cold context)
**Date:** 2026-11-01
**Verdict:** blockers-found

Each "Addressed by" line in the first critique was checked against the contract body and the code it cites. Verified as fixed: the per-field neutralisation (Data Shapes row, Handoff 2, Lessons referenced all agree), I-M0 plus `test_memory_off_parity.py` in Handoff 3, the `/journal-add` withdrawal, the token-list location and fail-closed rule, the timeout ASSUMED line and trial, the change-notice stub fields, applicability before the draft, cloud `--check` in Handoffs 6 and 7 with block 8 ahead of them, the `drift` rename, Open Question 17, and the registry appends moved to Handoff 10. The handoff graph (1→2→3→4→5; 1→8→6→7→9; 5,9→10→11) has no cycle, and no block lists a `MANIFESTS` file. Two fixes are only partial (first and second BLOCKER below). The rest are new defects the revision introduced.

### Findings

- **[BLOCKER] "No third parser" cannot hold: `tier_split` returns only titles and line numbers, but capture needs each entry's full text**
  - **What is wrong:** `tier_split` (`generate_registry_digest.py:55-68`) returns `(title, line)` pairs and nothing else. `capture-candidates` needs the full text of each MECHANISMS and VOCABULARY bullet for three things: the "names this contract" test (`.claude/concepts/<slug>.md` or `Contract:` in the text), the project-token scan, and the "verbatim entry text" field. Nothing that exists finds where a bullet ends, and bullets carry indented `**Correction**` sub-bullets (`MECHANISMS.md:16,44,47,59-60,68-69`). For JOURNAL, `tier_split(…, DATED)` gives tier by line, and `parse_entries` gives `sig`, trigger and source with no line number. Joining the two is new code the contract never specifies, and the two use different patterns (`DATED` matches `#{2,3}`, `ENTRY_HEADER` only `###`). The contract's fix route ("fixed **in** that function, with a test") cannot be followed inside the plan: Handoff 2's Files to touch lists neither `generate_registry_digest.py` nor the hook file. Changing `tier_split`'s return shape would also break the generator's own `emit_group` callers (`:108-124`). So Handoff 2 tells the implementer both "produce verbatim bullet text" and "Write NO new registry parser", and those two orders contradict each other. The claim "exactly as the generator treats it" is also false for JOURNAL: the generator never tier-splits JOURNAL. It emits every journal entry as `Universal` (`generate_registry_digest.py:128-130`).
  - **Prior artifact ignored:** `MECHANISMS.md:63` (Two-tier registry with a generated complete index); `JOURNAL.md` 2026-10-30 "One shared reader must own the filtering, not only the selection"; first critique BLOCKER 1 above.
  - **Where in this contract:** `## Data Shapes` "Candidate reading (no new registry parser)"; Handoff 2 CONSTRAINTS "Write NO new registry parser. A form those functions miss is reported, not re-parsed here."
  → Addressed by: the "no third parser" claim is dropped. The contract now states that capture needs full entry text, including Correction sub-bullets, plus a tier, line and Trigger join that neither reader gives. The shared reader is extended in its existing file: `generate_registry_digest.py` gains `entry_blocks` and `journal_entries`, and `tier_split` becomes a wrapper with byte-identical digest output. The hook's `parse_entries` becomes a thin normal-import caller. Both files and their tests are in Handoff 2. The journal tier comes from JOURNAL.md's own headings, and the contract states that the digest labels all journal entries Universal.
- **[BLOCKER] At step 3, `capture-candidates` refuses because the contract is not yet implemented, and `source-code-fact` needs `implemented` at `origin/<default>`, which never holds when capture runs**
  - **What is wrong:** step 3's one confirmation is built from the **dry run** (`contract-completion.md:49-51`), and the dry run returns `would-flip` before anything is written (`pr_merged.py:3815-3816`). The contract is therefore still `approved` when Handoff 4 says the candidates are listed, and `capture-candidates` refuses that case with `contract-not-implemented` (Commands table). The send itself runs between step 5 and step 7. At that point the flip exists only in the starting tree, and it reaches `origin/<default>` only when the records pull request merges later. Two Provenance rows require the source contract to read `implemented` at `origin/<default>`: post-impl divergence, and MECHANISMS or VOCABULARY entries. For this contract's own entries those rows can never match at capture time. The table has no row for "not yet implemented at origin", so the provenance of the main candidate kind is undefined.
  - **Prior artifact ignored:** `skills/pr-merged/references/contract-completion.md:49-55` (dry run first, confirmation from the dry run, flip only in step 5); `JOURNAL.md` 2026-10-15 "A cleanup wired to run before its own trigger event has fired never runs".
  - **Where in this contract:** `## Data Shapes → Commands` "List capture candidates … `contract-not-implemented`"; Provenance mapping rows 2-3; Handoff 4 TASK "Only when capture is enabled and the dry run reads would-flip: add the capture candidates … to step 3's ONE confirmation".
  → Addressed by: capture moved to its own step 5a, after the live writing run returns `flipped`, never built from the dry run. It has one confirmation, joined to Step 8's under `/flow`. `capture-candidates` reads that run's report. `source-code-fact` rests on the live `flipped` result (the flip is in the branch being recorded), not on `origin/<default>`, and a non-flipped run gives `not-flipped`.
- **[WARN] When the dry run reads `pending` but the writing run flips, capture is lost for good**
  - **What is wrong:** a `pending` dry run does not stop the flow, "because the confirmation is what clears an `owner_confirmation_needed` report" (`contract-completion.md:50`), so the writing run can still read `flipped`. Handoff 4 shows candidates only when the dry run reads `would-flip`. Duplicate protection says a later run reads `already-implemented` and offers nothing. The contract's lessons are then never offered, and nothing records that.
  - **Prior artifact ignored:** `skills/pr-merged/references/contract-completion.md:50`; `JOURNAL.md` 2026-10-30 "A delivery rule must name every route into delivery".
  - **Where in this contract:** Handoff 4 TASK "the dry run reads would-flip"; `## Data Shapes` "Duplicate protection".
  → Addressed by: step 5a is keyed on the writing run's result only, so a `pending` dry run followed by a flip gets the capture step. Added to Duplicate protection and the route table.
- **[WARN] Candidates are sent before the receipt check, and "on a flip it always is" is false when no brief is linked**
  - **What is wrong:** the order is "send each confirmed candidate, then run `record --receipts`", and only `record` checks for `brief-not-carried`. A flip with no linked brief adds only the contract to `written_files` (`pr_merged.py:3850-3853`). In that case every send succeeds, the receipt is refused, and the acceptance criterion "every item sent is recorded in its brief" fails with nothing written to show it.
  - **Prior artifact ignored:** `pr_merged.py:3850-3853`; brief acceptance criterion at `.claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md:35`.
  - **Where in this contract:** `## Extension Points` "/pr-merged … On a flip it always is."; Reused Mechanisms "On a flip the linked brief is already in the writing run's `written_files`".
  → Addressed by: `capture-candidates` refuses `brief-not-carried` (no linked brief, or the brief is not in `written_files`) before anything is offered or sent. "On a flip it always is" is removed, and the no-linked-brief route is in the route table.
- **[WARN] Loading the journal hook by `importlib` runs its module top level, which pushes two folders to the front of the import path and imports `derive_area` and `accuracy_update`**
  - **What is wrong:** `journal-post-approval-tracker.py:49-65` runs `sys.path.insert(0, …)` for both `hooks/` and `scripts/` and imports two unrelated modules at load time. Inside `memory_boundary.py`, which `status` runs on every design, that reorders the import path for the rest of the process and couples a memory-off design to modules memory never uses. The Commands row promises `status` "always exits 0", yet a top-level import of `pr_merged`, `generate_registry_digest` or `check_version_bump` that fails or predates a name in an old vendored copy raises before `status` can print anything. Step 1.5 covers only `disabled` and an empty lookup, not a non-zero exit.
  - **Prior artifact ignored:** `MECHANISMS.md:43` (Two-layer Claude path resolution: "**appends** it to `sys.path` (never `insert(0, …)`)"); `MECHANISMS.md:58` (Guard fallback mode: bind each needed function with `getattr` after a fail-soft import).
  - **Where in this contract:** `## Data Shapes` "Candidate reading": "loaded by file path with `importlib.util.spec_from_file_location` … The hook's own optional imports already fail soft"; Commands "Report memory state … It always exits 0"; Extension Points Step 1.5 item 1.
  → Addressed by: no `importlib` loading. The adapter imports the shared reader from `generate_registry_digest.py` and never loads the hook. Its imports are fail-soft with `getattr` binding, and it appends to `sys.path`. Step 1.5 item 2 treats any non-zero exit, crash, timeout or unreadable output as memory off, with one line, and continues.
- **[WARN] `parse_entries` and the stem rule are reused for a stricter consumer, but the contract does not list the forms they mis-read**
  - **What is wrong:** `SOURCE_LINE` captures `[^\s`]+`, so it stops at the first space. A Source contract path with a space is cut short, and the template's `N/A` (`JOURNAL.md:21`) is captured as a value. Those mis-reads were harmless to the accuracy tracker, but here they decide what is sent to a cross-project store. This is the exact pattern the newest journal entry names. The first critique marked that entry "did not need to". Revision 2's reuse of `parse_entries` makes it apply now.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-01 "A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for".
  - **Where in this contract:** `## Data Shapes` "Candidate reading", "Names this contract" bullet.
  → Addressed by: `journal_entries` reads the Source contract to end of line (paths with spaces), treats `N/A`, `none`, empty and placeholders as unset, and keeps absolute Windows paths whole. Each form is a pinned test, and the hook's changed behaviour for those forms is listed in the test.
- **[WARN] A bullet "names the contract" when a Correction under it does, so a whole older entry becomes this contract's candidate**
  - **What is wrong:** the rule is "a bullet names the contract when its text holds `.claude/concepts/<slug>.md`". Corrections appended later sit inside the parent bullet's text. For example, `MECHANISMS.md:44,47,68` name `2026-10-12-dedupe-claude-config.md` under entries from other contracts. Delivering that contract would offer the CodeGraph, Two-layer and Main-checkout entries whole, as `source-code-fact` knowledge of a contract that did not write them.
  - **Prior artifact ignored:** `MECHANISMS.md:41` (Adaptive Engineering Journal / registry rule "if a lesson is refined, append a new entry referencing the old"), with the Correction sub-bullets at `MECHANISMS.md:16,44,47,59-60,68-69`.
  - **Where in this contract:** `## Data Shapes` "Candidate reading": "A MECHANISMS or VOCABULARY bullet names the contract when its text holds `.claude/concepts/<slug>.md`".
  → Addressed by: an entry is a candidate only when its own line names the contract: the journal's own Source contract line, or the bullet's text excluding sub-bullets. A Correction naming a contract is its own `correction-entry` candidate and never makes the parent one. The `MECHANISMS.md:44,47,68` example is stated.
- **[WARN] The single-adapter scan covers the registries, and Handoff 10 is told to append the Memory adapter entry to them**
  - **What is wrong:** `is_shipped` exempts only `README.md`, `CONTRIBUTING.md`, top-level `*.md` files and the listed prefixes (`check_version_bump.py:29-39`). `.claude/registries/MECHANISMS.md`, `VOCABULARY.md` and `JOURNAL.md` are shipped, and so are `.claude/hooks/tests/` and `.claude/agent-memory/`. A Memory adapter entry that names its default tools, or a journal lesson confirmed from these critiques that quotes the acceptance criterion's `memory_retrieve`, fails block 2's scan. Handoff 10 names only README and CONTRIBUTING as exempt.
  - **Prior artifact ignored:** `.claude/scripts/check_version_bump.py:29-39`; first critique WARN "The single-adapter scan defines no file set".
  - **Where in this contract:** Handoff 10 CONSTRAINTS "README and CONTRIBUTING are exempt from the single-adapter scan by is_shipped"; TASK "Append the Memory adapter entry to the Universal tier of MECHANISMS.md".
  → Addressed by: no exemption is added. The registries, hook tests and agent memory stay scanned, and every memory-related registry entry (adapter mechanism, vocabulary, journal lessons) avoids the literal tool names, saying "the configured retrieve/capture tool". This is stated in Reused Mechanisms, Extension Points and Handoff 10.
- **[WARN] The new Step 1.5 question is a stop under `/flow`, but no block changes `/flow`'s list of where the run stops**
  - **What is wrong:** `/flow` names design-first's Step 3 as "the one human gate" (`skills/flow/SKILL.md:81`). Its "Where the run stops" list (`:539-546`) does not include an applicability question before the architect. Handoff 3 does not touch `skills/flow/SKILL.md`, and Handoff 4 touches it only for capture. Open Question 21 asks whether to accept the stop, but no block documents it on the `/flow` route, so an operator who has walked away during design is held up before any draft exists.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "A delivery rule must name every route into delivery"; `skills/flow/SKILL.md:525-546`.
  - **Where in this contract:** `## Extension Points` route table row "`/flow` → `/task` → `/design-first` | same Step 1.5, not repeated in `/flow`"; Open Question 21.
  → Addressed by: Handoff 3 (the block that edits design-first) now edits `skills/flow/SKILL.md`, adding the Step 1.5 applicability question to "Always the operator's call". The route table says so.
- **[WARN] The answer to Open Question 11 ("add-on hook as fallback") has no block, so a failed trial stalls blocks 6 to 9**
  - **What is wrong:** Handoff 8's precondition is a live trial. Blocks 6 and 7 depend on 8's `--check`, and block 9 depends on all three. If the trial shows that compound forms escape `permissions.ask`, the accepted fallback (Alternative G) has no block, no follow-up stub and no stated decision point. The cloud half of the contract then has no way forward.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-22 "An accepted critic WARN or answered Open Question must amend the contract body before approval".
  - **Where in this contract:** Open Question 11 "add-on hook as fallback"; `## Alternatives Considered` Option G "Kept as the fallback if the trial fails"; Handoff 8 **Preconditions**.
  → Addressed by: Handoff 8 no longer stalls on the trial. It always delivers `--check` and records the trial result. Handoff 13 is a conditional block, written in full as a scope note, promoted by amendment only if the trial fails. It depends on 8 and is depended on only by 9, so the graph stays acyclic. If it is promoted, `--check` also accepts the add-on's hook row.
- **[WARN] `cloud-permissions --check` reads one settings file, so rows the user placed in another settings layer make the cloud capability refuse**
  - **What is wrong:** `--check` exits 0 only when every row is present "in the project's `.claude/settings.json`". The host also honours `settings.local.json` and the user layer, and Preview-hash apply already treats the settings layer as an input. With fail-closed refusal, rows a user added by hand in another layer block all cloud work, including authoring and non-mutating validation.
  - **Prior artifact ignored:** `MECHANISMS.md:64` (Preview-hash apply: "a changed flag, settings layer …").
  - **Where in this contract:** `## Extension Points` "`cloud-permissions --check` is read-only: exit 0 when every expected row is present"; Handoff 8 TASK.
  → Addressed by: `--check` reads project, project-local and user settings, the layers the Install mode term already names, and accepts a row in any of them. Managed settings are not read; a row found only there gives `managed-layer-not-read` with a remedy, and an unreadable layer counts as empty. This is stated in Reused Mechanisms and Handoff 8.
- **[WARN] The header still reads `Tracking issue: pending`, but the brief records issue #161**
  - **What is wrong:** Open Question 1 is marked answered, and the brief's frontmatter holds `id: 161` and the issue url. The contract header was not amended. A multi-block contract with an unresolved parent issue raises the `no-parent-issue` layout defect.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-22 "An accepted critic WARN or answered Open Question must amend the contract body before approval"; `.claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md:2,8`.
  - **Where in this contract:** header "**Tracking issue:** pending (see Open Question 1)".
  → Addressed by: the header now reads `**Tracking issue:** #161`.
- **[NIT] Handoffs 3 and 4 edit text pinned by `test_parent_branch_rule_text.py` without naming it** — it pins sentences in `skills/design-first/SKILL.md`, `skills/flow/SKILL.md`, `skills/pr-merged/SKILL.md` and `references/contract-completion.md` (`:153,201-216,306-319`). This is JOURNAL 2026-10-15 "A skill that edits a block pinned by a lookup-block test must name that test".
- **[NIT] The id pattern allows `@`, so `Memory item <id>@<version>` and `superseded_by` (id@version) are ambiguous to parse** — `## Data Shapes` "Retrieved memory item" safe pattern "letters, digits and `._:@/-`".
- **[NIT] "One multi-select question" may not fit the host question tool when more items come back than one question can list** — the limit is "capped by the shape profile" with no number tied to the question form. The critic has no in-repository source for the host limit.
- **[NIT] `changed-items` must read other briefs' `## Memory used` sections, but its input set is not defined** — Commands gives the payload as "normalised items" only. It does not say which work-items folder is read, or at which ref, and inside a worktree that folder is a snapshot of the branch base.
- **[NIT] `test_memory_off_parity.py` pins the `/task` brief template by its hash at 6d1ca0c** — any later edit to that block breaks a memory test that has nothing to do with the edit. The follow-up stub `2026-11-01-token-efficiency-and-audit-defects.followup.md` already plans `/task` edits.
- **[NIT] The contract is about 39,500 tokens against its own 20,000 Budget, and round 1's critique was not moved out** — `.claude/templates/concept-contract.md:22` ("every superseded critique round moves out of the contract to `.claude/contract-history/<slug>.round-<n>.md`"). This second round is appended here as the caller instructed.

### Applicable journal entries

- **2026-10-05 — Neutralise every field echoed from untrusted input, not only the body**: heeded by the "Retrieved memory item" row and the Handoff 2 per-field probe.
- **2026-10-05 — A documented "missing file means the default" must read one named location only**: heeded by `.project-tokens.json` being read from the project only, failing closed.
- **2026-10-15 — A cleanup wired to run before its own trigger event has fired never runs**: violated. Candidates are listed at step 3, before the flip they require (see BLOCKER above).
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test**: heeded for `test_skill_script_lookup.py` and `test_repo_consistency.py`; not addressed for `test_parent_branch_rule_text.py` (NIT).
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval**: violated for Open Question 1 (header) and Open Question 11 (no fallback block); see the WARNs above.
- **2026-10-30 — A delivery rule must name every route into delivery**: partly heeded by the route table. The `pending`-then-flip route and the `/flow` stop list are missing (see the WARNs above).
- **2026-10-30 — One shared reader must own the filtering, not only the selection**: violated. Body extraction and the tier join fall outside the reused readers (see BLOCKER above).
- **2026-11-01 — A shared reader reused by a stricter consumer must be re-checked**: now applicable through `parse_entries`; not addressed (see WARN above).
- **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work**: heeded by the Handoff 3 and Handoff 8 trials.

### What the critic did not check

- `pr_merged.py --contract <slug> --status --json` (item 14) and `derive_area.py`: the critic has no shell. The area map is still empty.
- North-star alignment: `.claude/north-stars/` does not exist.
- Host behaviour (MCP tool id form, MCP timeout, `permissions.ask` matching for compound commands, the question-tool option limit) was not checked against host documentation.

---

## Critique (revision 3)

**Critic:** contract-critic (third pass, cold context)
**Date:** 2026-11-01
**Verdict:** blockers-found

The critic checked each revision-2 finding against the contract body and the code. These are fixed in the body: the shared reader is extended in its own file (`generate_registry_digest.py` and the hook are in Handoff 2's files; the hook already puts `scripts/` on its path and imports `derive_area` and `accuracy_update`, `journal-post-approval-tracker.py:49-65`; the digest labels all journal entries Universal, `:128-130`); no `importlib` loading, imports fail soft, and Step 1.5 item 2 treats any failure as memory off; the Source contract forms are each pinned by a test; a Correction is its own candidate, never its parent's; the registries stay scanned and their entries avoid the literal names; the `/flow` stop list is edited in Handoff 3 (`skills/flow/SKILL.md:539-546` is the right list); `--check` reads three settings layers; the header reads `#161`; `/pr-merged` step 5a runs after a live `flipped` writing run (`pr_merged.py:3849-3856,4796,4803` confirm that the brief is in `written_files` only when one is linked) and refuses `brief-not-carried` before offering; a `pending` dry run followed by a flip still gets the capture step; `@` is out of the id pattern; the applicability cap is 8 (ASSUMED); `changed-items` names its input; the `/task` hash pin is replaced by a content check; and `test_parent_branch_rule_text.py` is named in Handoffs 3 and 4. Handoff 13 is valid in the block graph. `classify_handoff` (`pr_merged.py:328-362`) reads it as a `scope-note`, because no backticked agent is in its heading and its body has no `**Files to touch:**` line. Block 9's `**Depends on:** 6, 7, 8 — …` parses as `[6, 7, 8]`, because `_parse_depends_on` (`:283-289`) splits at the em dash, and neither block 6 nor block 9 puts a digit before its dash. The `` `Depends on: 8` `` bullet inside block 13 does not match `^\*\*Depends on:\*\*`. The edges 1→2→3→4→5, 1→8→6→7→9, 5,9→10→11 and the promoted 8→13→9 have no cycle. One revision-2 BLOCKER is fixed only on the `/pr-merged` route (below).

### Findings

- **[BLOCKER] On the `/flow` route, capture is still offered before the flip it depends on. The premise that "Step 8's confirmation already comes after the writing run" is false**
  - **What is wrong:** under `/flow`, Step 8's confirmation *replaces* `/pr-merged` step 3, so it comes **before** the writing run. The sources say so directly. `contract-completion.md:47` and `:59` say "the confirmation always comes before any writing run", and "follow the same order with Step 8's confirmation as the one confirmation". `skills/flow/SKILL.md:591` says the dry run reaches Step 8's confirmation, and "After the owner answers, make ONE writing run". So when Step 8 asks, no live writing run has returned `flipped`, and `capture-candidates --run-report` has no report to read. Capture then has only two ways to happen under `/flow`. It can be built from the dry run, which is the defect revision 2 removed. Or it can be asked as a second question after the writing run, which breaks Handoff 4's own constraint "Under /flow, Step 8 stays one question". Otherwise it never happens.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-15 "A cleanup wired to run before its own trigger event has fired never runs"; `skills/pr-merged/references/contract-completion.md:47,59`; `skills/flow/SKILL.md:591`; revision-2 BLOCKER 2 above.
  - **Where in this contract:** `## Extension Points` "`/flow` Step 8: … joined to Step 8's single confirmation, which already comes after the writing run, because Step 8 sorts files that exist"; Handoff 4 TASK "(which already comes after the writing run)"; route table row "`/flow` → `/task` → `/design-first` … joined to `/flow` Step 8's one confirmation".
  → Addressed by: under `/flow`, Step 8's confirmation stays before the one writing run and is unchanged. Capture is its own question, asked only after that writing run returns `flipped`, never built from the dry run. Handoff 4 amends `/flow`'s one-confirmation text (`skills/flow/SKILL.md:591` and Step 8) and `contract-completion.md:47,59` to say so, and the route table's `/flow` row is corrected.
- **[WARN] Revision 3 adds a second question at `/pr-merged`, but four places in the body still say capture rides inside the one existing confirmation**
  - **What is wrong:** Handoff 4 says "Under /pr-merged, step 5a adds exactly one question", and Extension Points calls it "the step's only question", asked after step 5. Four places say the opposite. `## Business Concept` says "The offer is part of the delivery's one existing confirmation". Open Question 6, as amended, says "The batch rides inside the existing one confirmation". Appendix C P3 says "Capture inside the delivery's one confirmation … no second question under `/pr-merged` or `/flow`". And `contract-completion.md:47` says the confirmation comes before any writing run. The user's recorded answer to Open Question 6 therefore no longer matches the design, and the header says "Revision 3 adds no new Open Question".
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-22 "An accepted critic WARN or answered Open Question must amend the contract body before approval".
  - **Where in this contract:** `## Business Concept` item 1 "Capture"; `## Open Questions for User` item 6; Appendix C row P3; Handoff 4 CONSTRAINTS.
  → Addressed by: every place now says capture is its own question after the flip: Business Concept, the Open Question 6 amendment, Appendix C P3, the Events row, Extension Points, the Handoff 4 TASK and constraints (including the `contract-completion.md` text it edits) and the Handoff 5 check. The "Step 8 stays one question" statement is replaced by "the records confirmation is unchanged; one separate capture question follows the flip".
- **[WARN] After a failed trial, `--check` still passes on the rows alone, and nothing in the loop stops to promote Handoff 13**
  - **What is wrong:** Handoff 8 says that if the trial failed, "--check also accepts the Handoff 13 add-on hook row". "Also" means either the rows or the hook row satisfies the check. The `permissions.ask` rows that the trial just showed miss compound forms are therefore still enough to pass, so "Deployment authorization … fails closed" stops being true once the trial fails. The promotion itself is triggered only by a note in block 8's pull request ("say so in the block's pull request"). No step in `/advance` or `/pr-merged` reads that note. Blocks 6 and 7 are released when 8 merges, and block 9 can run before anyone amends the contract.
  - **Prior artifact ignored:** `MECHANISMS.md:56` (Guard rules file: a blocking guard fails closed); `JOURNAL.md` 2026-10-22 "An accepted critic WARN or answered Open Question must amend the contract body before approval" (Open Question 11's fallback is in the body, but nothing triggers it).
  - **Where in this contract:** Handoff 8 TASK "If the trial failed, --check also accepts the Handoff 13 add-on hook row as authorization"; Handoff 8 CONSTRAINTS "say so in the block's pull request, so the contract is amended to promote Handoff 13"; Handoff 13 "the contract is amended before Handoff 9 runs".
  → Addressed by: after a failed trial, `--check` requires the add-on hook row alone; the rows alone fail, and a test pins this. As its done-criterion, Handoff 8 writes a `**Trial:** passed|failed` line to the parent brief (now in its Files to touch). Handoff 9's `Preconditions:` names that line and the promoted block's completion record, and its gate returns `blocked` when either is missing.
- **[WARN] A hanging capture server can stall delivery for one host timeout per candidate**
  - **What is wrong:** retrieval has a stop-the-run rule: "treat memory as off for the rest of this run". Capture has none. Step 5a says "Send each confirmed candidate once", and a failure writes `Not sent:` and goes on to the next candidate. If the server is present but never answers, each candidate waits out the host MCP timeout in turn, before step 7 copies files and the records pull request opens. So delivery depends on how quickly the memory server answers. The brief requires that with the server unreachable, "every existing skill and flow behaves as it does today".
  - **Prior artifact ignored:** `.claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md:30` (acceptance criterion 3); the contract's own Step 1.5 item 2 rule.
  - **Where in this contract:** `## Extension Points` `/pr-merged` step 5a items 4-5; Handoff 4 CONSTRAINTS "A send failure writes a 'Not sent:' line and never blocks the records pull request".
  → Addressed by: a stop rule. At the first send failure or timeout, sending stops, the remaining candidates are written as `Not sent: (stopped after <reason>)` and delivery continues. This is in Duplicate protection, Extension Points step 5a item 4, Failure Modes and Handoff 4.
- **[WARN] The single-adapter scan still has no file set. `is_shipped` is a test that takes one path; it does not list the files**
  - **What is wrong:** `is_shipped` (`check_version_bump.py:35-39`) answers for one path at a time. It exempts only the prefixes in `:29-31`, and `.claude/worktrees/` is not one of them. The contract says the scan covers "every path is_shipped() returns true for", but it never says where those paths come from. A filesystem walk from the main checkout reaches `.claude/worktrees/*/.claude/scripts/memory_boundary.py` and its tests in every live worktree, and this contract's own worktree is one of them. The scan then fails in the main checkout whenever a worktree exists. The existing scans walk named folders instead (`test_plugin_text_scans.py:102`). The first-round WARN "The single-adapter scan defines no file set" is therefore only partly fixed.
  - **Prior artifact ignored:** `.claude/scripts/tests/test_plugin_text_scans.py:102`; `check_version_bump.py:29-39`; first-round WARN above.
  - **Where in this contract:** `## Extension Points` "a scan over every file `check_version_bump.is_shipped` returns true for"; Handoff 2 CONSTRAINTS "over every path is_shipped() returns true for".
  → Addressed by: the file set is now built by walking named shipped folders from `Path(__file__).parents[3]`, as `test_plugin_text_scans.py:102` does. Every `.claude/worktrees/` path is excluded and the rest is filtered by `is_shipped`; there is no walk from the repo root or the current directory. A planted copy under `.claude/worktrees/x/` is a second control and must be ignored.
- **[NIT] The hook's `parse_entries(text)` cannot just pass through to `journal_entries(path)`.** The hook parses the text of the edited target (`journal-post-approval-tracker.py:171-176`), but `journal_entries` takes a path. No handoff says which of the two signatures changes.
- **[NIT] The byte-identical digest test is not pinned to a method.** Pinned to a golden file, it breaks on block 10's registry appends and on every journal append. And `main()` writes to the cwd-relative `OUT` path (`generate_registry_digest.py:29-30,147-149`). This is the same class of problem as the revision-2 NIT about the `/task` hash pin.
- **[NIT] `entry_blocks`'s tier rule does not cover an entry that comes before any tier heading.** `tier_split` files such an entry as Project (`generate_registry_digest.py:57,67`), so the wrapper has to keep that. The contract states only the Universal and Project heading cases.
- **[NIT] Nothing makes `normalise` cap the item count at 8.** The retrieval `limit` is a request to an untrusted server. Handoff 2 says only "the applicability limit is 8", and a server that ignores the limit overflows the one question call.
- **[NIT] `record --receipts` has no declared input for `written_files`, and step 5a says "the union of `written_files`" while `capture-candidates` reads one `--run-report`.** The Commands row "Record outcome" lists only outcome, items, decisions and receipts.
- **[NIT] The contract is now about 52,000 tokens against its 20,000 Budget, and neither earlier critique round has moved to `.claude/contract-history/`.** See `.claude/templates/concept-contract.md:22`. This round is appended here because the caller asked for that.

### Applicable journal entries

- **2026-10-15 — A cleanup wired to run before its own trigger event has fired never runs**: heeded on the `/pr-merged` route (step 5a); violated on the `/flow` route, see BLOCKER above.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval**: heeded for the tracking issue and the Open Question 11 block; violated for Open Question 6's wording and the Handoff 13 trigger, see WARNs above.
- **2026-10-30 — A delivery rule must name every route into delivery**: heeded; `pending`-then-flip and the no-linked-brief route are in the table. The `/flow` row is wrong, see BLOCKER.
- **2026-10-30 — One shared reader must own the filtering, not only the selection**: heeded by `entry_blocks` and `journal_entries` in `generate_registry_digest.py`, with the hook as a thin caller.
- **2026-11-01 — A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for**: heeded by the Source contract form tests and the sig/trigger/source parity test on the current JOURNAL.md (that test also protects the hook's seen-signature cache).
- **2026-10-05 — Neutralise every field echoed from untrusted input, not only the body**: heeded. The item count is a NIT above.

### What the critic did not check

- `pr_merged.py --contract <slug> --status --json` was not run: the critic has no shell, and `C:\Users\lneni\.claude\jobs\9c474e74\tmp\status.json` does not exist. Instead, the block graph was checked by reading `classify_handoff` and `_parse_depends_on` directly.
- Host behaviour (MCP tool id form, `MCP_TOOL_TIMEOUT`, `permissions.ask` compound matching, question-tool limits) was not checked against host documentation.
- North-star alignment was not checked, because `.claude/north-stars/` does not exist.

---

## Lessons referenced

- **2026-10-15 — A script that reads a project-owned file must be told which project, not search for one** — heeded by every `memory_boundary.py` subcommand taking `--project <root>` explicitly. Read with the plugin's own placeholder profile, it would read `disabled` and silently hide a real configuration.
- **2026-10-16 — A "missing project file" refusal must cover both the unset root and the set-but-absent file** — heeded in the opposite direction, on purpose: both cases read `disabled` (fail-soft), because memory is optional. This is tested for both cases.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded: Handoffs 3 and 4 list `test_skill_script_lookup.py`.
- **2026-10-05 — Neutralise every field echoed from untrusted input, not only the body** — heeded by `normalise`, which has a rule for every server field (id, version, scope, status, title, summary, superseded_by, conflicts_with, provenance) and a probe test per field.
- **2026-10-30 — One shared reader must own the filtering** and **2026-10-15 — Reuse the existing brief-linkage reader** (applied to registry entries too) — heeded by Candidate reading: one shared reader, extended in `generate_registry_digest.py`, used by the digest, the hook and the adapter.
- **2026-11-01 — A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for** — heeded: the Source contract forms (spaces, `N/A`, placeholders, Windows paths) are listed and each is pinned by a test.
- **2026-10-15 — A cleanup wired to run before its own trigger event has fired never runs** — heeded: capture runs only on `flipped`, inside the run that writes the records.
- **2026-10-05 — Text delivered to the model must say which rule wins against a skill's gate** — heeded by the data-architect rule: memory ranks below the registries and the user.
- **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work** — heeded by the live-trial precondition for the MCP tool id (Handoff 3).
- **2026-10-28 — A new term's definition must be true against every existing member** — heeded by defining *Central Memory System* against the three existing "memory" things.
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam** — heeded: only the adapter is new.
- **2026-10-28 — State the real trigger of a hook** — heeded: no hook is added, and the cost of the disabled path is stated as one silent script call per design.
- **2026-10-30 — A delivery rule must name every route into delivery** — heeded by the route table under Extension Points.
- **2026-10-30 — One shared reader must own the filtering** and **2026-10-15 — Reuse the existing brief-linkage reader** — heeded: `load_slot` and `select_linked_brief` are reused, with no new reader.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — noted for the approval pass; heeded again in the Revision 7 amendment, which writes the answers to Open Questions 22 and 23 into the body and removes block 15's "the user's answer wins" hand-off.
- **2026-10-28 — A new term's definition must be true against every existing member** — heeded in Revision 7 by renaming "Project memory" to **Project history record** and naming exactly who reads and appends it, with the no-design routes excluded.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded in Revision 7: block 15's who-appends text follows `agents/contract-critic.md:150` and `JOURNAL.md` "Maintained by", and the `--fix` description follows `plugin_doctor.py` `REQUIREMENTS` and `apply_fixes`.
- **2026-10-15 — A script that reads a project-owned file must be told which project** — heeded in Revision 7 by block 14 I2 (`default_branch_or_none(cwd=<project>)`, no `master` fallback).
- **2026-11-01 — After merging a base that changes the row shape a feature reads, re-check every coverage claim and round-trip test against the merged writer** — heeded in Revision 8: block 17 re-runs the suites on the merged tree and rewrites every README count from what the merged tree and suites report, never by adding the two sides.
- **2026-10-17 — Judge "identical to master" by git's view, not raw bytes, on Windows** — heeded in Revision 8: block 18 checks the master side of each registry with `git show origin/master:<path>`, not a copy on disk.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — heeded in Revision 8. The user's answers to Open Questions 24-28 (2026-11-03) are written into blocks 17 and 18, which keep no conditional branch. Each Revision 8 critic finding carries its `→ Addressed by:` line.
- **2026-11-02 — Keep a review-fix block to the review's findings** — heeded in Revision 9: block 19 carries only B1, W1 and the J12 entry the t18 review proposed, plus the test edit that B1's own fix forces. The README tree-count pin (F2) goes to a follow-up stub (Open Question 30).
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded in Revision 9: block 19 names `test_parent_branch_rule_text.py`, whose step 5a test ends its section at the heading block 19 deletes, and fixes the end marker.
- **2026-11-02 — A revision that adds a path adds its failure modes** and **2026-11-02 — After amending a contract, update every summary of the block graph** — heeded in Revision 9: four Revision 9 Failure Modes entries and one Uncertain Assumptions line; the header Revision line, the Handoff intro, its graph, the block 11 pointer and Appendix C row P10 are updated.
- **2026-10-17 — Judge "identical to master" by git's view, not raw bytes, on Windows** — heeded in Revision 9: block 19 checks the kept steps 6-9 with `git diff 274bf1e -- <path>` (git's view, not raw bytes), and block 20 judges them with the same `git diff`.
- **2026-11-01 — After merging a base that changes the row shape a feature reads, re-check every coverage claim ...** — heeded in Revision 9: block 19 re-measures each tree count from the tree it edits; the numbers this contract quotes are a measurement, not the value to write.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — heeded in Revision 9: blocks 19 and 20 are already written to the recommendations of Open Questions 29-32 and keep no conditional branch.
- Orthogonal to north-stars: none active (`.claude/north-stars/` does not exist, matching the brief's intake grade).

---

## Implementation Handoff

This contract has nineteen mergeable blocks plus one scope note (twenty numbered blocks; Revision 8 added the remedy 17 and its review 18, graph 9,10→17→18; Revision 9 added the fix 19 and its re-review 20, graph 17→19→20; block 19 does not depend on block 18, because the loop withholds any dependent of a `blocked` review, and block 18 is the blocked review of block 17), so it is delivered through the parent branch `feature/memory-client-and-cloud-engineering` (Parent Branch Delivery Rule). No block touches a version file; the landing raises the version once. Block 1 holds the profile slots, blocks 2-5 the memory boundary, 6-8 the cloud capability and 9-10 the documentation; block 11 is the scope note. Revision 6 added the cloud fix 12 and its re-review 13; Revision 7 added the memory-boundary fixes 14, the Project history record block 15 and their re-review 16. The true graph, with no cycle:
- 1→2→3→4→5 (5 also waits for 2 and 3); 2,3,4→14→15; 2,3,4,14,15→16.
- 1→6→7→8 (8 also waits for 6); 7→12; 6,7,12→13.
- 13,14,15,16→9; 9,14,15,16→10.
- 9,10→17→18 (Revision 8).
- 17→19; 17,19→20 (Revision 9). Block 19 does not list block 18: it needs the merge it fixes (17), and the blocked review of 17 would withhold it.

Blocks 5 and 8 keep their recorded `blocked` reviews; 16 supersedes 5 and 13 supersedes 8, so 9 waits for the re-reviews, not the originals. Block 18 keeps its recorded `blocked` review too; 20 supersedes it (Revision 9). Revision 5 removed the old block 8 (deployment authorization) and the conditional block 13 of that older numbering, and renumbered the rest; today's block 13 is the Revision 6 re-review.

### 1. Profile slots (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/project-profile.md`

**Pre-written TASK block:**
```
TASK: Add nine slot rows to the Slots table of the profile template: memory.server, memory.retrieve-tool,
  memory.capture-tool, memory.shape, memory.project-key, cloud.providers, cloud.iac, cloud.roots,
  cloud.mcp-server. Each value is the template's italic placeholder prose saying what to write and that
  `none` turns it off. Add one short note under the table: memory and cloud are optional and are off
  while their slots are unset.
CONTEXT: concept contract at .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md (Data Shapes,
  value objects "Memory adapter configuration" and "Cloud profile").
FILES: .claude/project-profile.md
CONSTRAINTS:
  - Placeholder form "*( ... )*" so pr_merged.load_slot reads every new slot as unset.
  - Do not change existing rows. Do not touch any version file.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

### 2. Memory adapter and degradation tests (`python-ai-developer`)

**Depends on:** 1

**Files to touch:**
- `.claude/scripts/memory_boundary.py`
- `.claude/scripts/tests/test_memory_boundary.py`
- `.claude/scripts/tests/test_plugin_text_scans.py`
- `.claude/scripts/generate_registry_digest.py`
- `.claude/hooks/journal-post-approval-tracker.py`
- `.claude/scripts/tests/test_registry_entries.py`

**Pre-written TASK block:**
```
TASK: Write memory_boundary.py with the subcommands status, retrieve-request, normalise, capture-candidates,
  capture-request, record, check-contract and changed-items, exactly as the contract's Commands table
  defines them, plus shape profile v0, marked provisional. The default tool names memory_retrieve and
  memory_capture live ONLY here. Tests first.
CONTEXT: concept contract (Data Shapes incl. "Candidate reading", "Provenance mapping", "Duplicate
  protection"; Commands; Failure Modes).
FILES: the six listed.
CONSTRAINTS:
  - Extend the shared registry reader in generate_registry_digest.py: add entry_blocks(text, pattern,
    per_domain=False) and journal_entries(text, per_domain=False) exactly as "Candidate reading" defines
    them. Both take TEXT (full own text, indented sub-bullets with lines; tier from the text's own
    headings; an entry before any tier heading is Project; per_domain=True makes all Project;
    sig/trigger/source). Rewrite tier_split(path, pattern) as read() then entry_blocks, keeping its
    signature and (title, line) shape. Byte-identical test: keep the pre-change tier_split verbatim in
    the test; run main() with cwd set to a temporary copy of the registries, once patched to the old
    function and once with the new; compare the two outputs byte for byte, on the current registries and
    on fixtures with a pre-heading entry and Correction sub-bullets. No golden file.
  - journal-post-approval-tracker.py: parse_entries(text) keeps its signature and becomes a thin caller of
    journal_entries(text), returning the keys it returns today, imported
    normally from the scripts folder and bound with getattr after a fail-soft import (a missing reader
    makes the hook skip and log). No other behaviour change except the listed Source forms.
  - test_registry_entries.py: Correction sub-bullets attach to their parent; a bullet ends at the next
    top-level match or heading; journal tier from "## Universal" / "## Project:" and per-domain files;
    Source contract with spaces, N/A, none, empty, placeholder and an absolute Windows path; the
    hook's sig/trigger/source on the current JOURNAL.md equal the old regex output except those forms.
  - memory_boundary.py imports load_slot and select_linked_brief from pr_merged, entry_blocks and
    journal_entries from generate_registry_digest, and is_shipped from check_version_bump. All are
    fail-soft and bound with getattr; append to sys.path, never insert. It never loads the hook file and
    parses no registry text itself.
  - Candidates only from entries whose OWN line names the contract (journal Source line; bullet text
    without sub-bullets); a naming Correction is its own correction-entry and never makes its parent one.
  - capture-candidates takes --run-report (the live writing run's JSON). It refuses not-flipped and
    brief-not-carried before producing anything; source-code-fact rests on that report's flipped verdict.
  - Every subcommand takes --project explicitly; never search for a profile or the token list.
  - status always exits 0. Profile absent, slot unset and placeholder all read "disabled"; test each.
  - record with state "disabled" refuses "not-enabled" and writes nothing (test: brief bytes unchanged).
    record --receipts takes --run-report <the report> and refuses "brief-not-carried" unless the brief is
    in that report's written_files.
  - The id/version pattern excludes "@". normalise keeps at most the first 8 accepted items (server
    order) and counts the rest as over-limit; test with a server response of 20 items.
  - normalise applies the per-field rules of the "Retrieved memory item" row to EVERY field; a test probes
    each field with a line separator, "## ", "|" and a backtick. Key = id+version; first wins.
  - Provenance exactly as the table: manual/post-approval give ai-hypothesis; test-confirmed is never
    produced. capture-request refuses ai-hypothesis and any status other than proposed.
  - Scope safety reads <project>/.claude/.project-tokens.json only. A token hit lowers to project; a
    missing or empty list lowers every candidate. Test both, plus a hit, with decoys in other locations.
  - Name matching: the stem rule with "/" and "\" separators; test an absolute Windows Source contract.
  - Single-adapter scan in test_plugin_text_scans.py: walk the named shipped folders listed in Extension
    Points from Path(__file__).parents[3] (never cwd, never a walk from the repo root), exclude every path
    with a .claude/worktrees/ segment, then filter by is_shipped(). Only .claude/scripts/memory_boundary.py
    may contain memory_retrieve or memory_capture. Positive controls: a planted made-up shipped-path file
    is caught; a planted copy under .claude/worktrees/x/ is ignored.
  - Run the existing suites in .claude/scripts/tests and .claude/hooks/tests; all must pass.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

### 3. Retrieval at design time (`python-ai-developer`)

**Depends on:** 2

**Preconditions:** one session with a stub MCP server confirms the tool id form mcp__server__tool, and a stub that never answers confirms the host timeout returns an error

**Files to touch:**
- `skills/design-first/SKILL.md`
- `skills/design-first/references/central-memory.md`
- `agents/data-architect.md`
- `.claude/templates/concept-contract.md`
- `.claude/scripts/tests/test_skill_script_lookup.py`
- `.claude/scripts/tests/test_repo_consistency.py`
- `.claude/scripts/tests/test_parent_branch_rule_text.py`
- `.claude/scripts/tests/test_memory_off_parity.py`
- `skills/flow/SKILL.md`

**Pre-written TASK block:**
```
TASK: Add /design-first Step 1.5 exactly as Extension Points describes. On "disabled" or an empty lookup it
  prints nothing and writes nothing. On ANY non-zero exit, crash, timeout or unreadable output of any
  adapter subcommand it prints one line, writes nothing more, treats memory as off and goes to Step 2.
  On "unconfigured" it records and prints one line. On "enabled" it
  reads references/central-memory.md. Write that reference: check the tool list; make ONE call (no retry,
  host timeout bounds it; any error or timeout means record "unavailable", print one line, go to Step 2);
  normalise; changed-items; ONE applicability question call (at most 8 items, up to two multi-select
  questions of four options); pass only applies items as
  PRIOR_FINDINGS memory_items; at Step 3 run check-contract, show not-cited/uncleared-item and change
  notices; write a follow-up stub (Parent contract = this contract) only on the user's yes. Document the
  "## Memory used" section in this reference (NOT in /task). Add the data-architect "Memory items" rule
  and the "Memory item <id>@<version>" line format to the template's Lessons referenced section. In
  skills/flow/SKILL.md, add the Step 1.5 applicability question to "Always the operator's call".
CONTEXT: concept contract (Extension Points, route table, Applicability decision, I-M0).
FILES: the nine listed.
CONSTRAINTS:
  - skills/task/SKILL.md is NOT touched.
  - Keep every sentence test_parent_branch_rule_text.py pins in design-first and flow passing.
  - No skill text names a memory tool; the tool id comes from the script's output.
  - Items are quoted data below registries and the user; applies/does-not-apply come only from the user.
  - Extend test_skill_script_lookup.py with the new lookup block (journal 2026-10-15). Keep every
    sentence test_repo_consistency.py SENTENCE_PLACEMENT pins in design-first; update the table only
    if a pinned sentence must move.
  - test_memory_off_parity.py: with memory off (profile absent, placeholder slots, and slots "none"),
    run the commands Step 1.5 runs against copies of every brief in .claude/work-items/ and two fixture
    briefs. Assert each is byte-identical to its original and that no new file appeared in the temp tree.
    Assert skills/task/SKILL.md contains no "Memory used" and no "memory_boundary" text (a content
    check, not a hash pin, so unrelated /task edits do not break it).
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

### 4. Capture at delivery (`python-ai-developer`)

**Depends on:** 3

**Files to touch:**
- `skills/pr-merged/references/contract-completion.md`
- `skills/pr-merged/SKILL.md`
- `skills/flow/SKILL.md`
- `.claude/scripts/tests/test_skill_script_lookup.py`
- `.claude/scripts/tests/test_parent_branch_rule_text.py`

**Pre-written TASK block:**
```
TASK: Add step 5a "Capture" to references/contract-completion.md exactly as Extension Points describes. It
  runs only when capture is enabled and only AFTER a live writing run returned "flipped" for this contract,
  whatever the dry run said. Step 3's confirmation is unchanged. Run capture-candidates --run-report
  <the report> (the JSON of the writing run that flipped); on not-flipped or brief-not-carried print one
  line and go on, sending nothing. Otherwise ask the separate capture question (candidates, provenance,
  scope, lowerings), send confirmed candidates in order with the stop rule, then record --receipts
  --run-report <the report> into the linked brief before step 7's copy. In contract-completion.md, amend
  the sentence "the confirmation always comes before any writing run" and the /flow sentence (line 59)
  so they also say: "when memory capture is enabled and candidates exist, one separate capture question
  follows the writing run that flipped". In skills/flow/SKILL.md, amend the closing paragraph (line 591,
  "Step 8's confirmation as the one confirmation") and Step 8 with the same sentence: Step 8's
  confirmation stays BEFORE the writing run and is unchanged; the capture question comes after that run
  flips, and Step 8 commits the brief only after receipts are recorded. Add the capture question to
  "Always the operator's call". pr-merged reads ../design-first/references/central-memory.md.
CONTEXT: concept contract (Provenance mapping, Candidate reading, Duplicate protection, Capture receipt,
  route table).
FILES: the five listed.
CONSTRAINTS:
  - Capture is never built from a dry run and never folded into the records confirmation, on either route.
    Exactly one capture question, only when there are candidates. Never capture without the owner's
    answer in this run.
  - Stop rule: at the first send failure or timeout, stop sending, write the rest as "Not sent: (stopped
    after <reason>)", continue delivery. No outcome of capture blocks the records pull request.
  - Keep every sentence test_parent_branch_rule_text.py pins in flow, pr-merged and contract-completion.md;
    where an amended sentence is pinned, update the pin in the same block and say why.
  - skills/journal-add/SKILL.md is NOT touched.
  - flow is a repository-owned skill: keep any sync test over it passing.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

### 5. Review memory boundary (`fullstack-code-reviewer`)

**Depends on:** 2, 3, 4

**Files to touch:**
- `.claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t5-review-memory-boundary-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review blocks 2-4 and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
FILES: .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t5-review-memory-boundary-fullstack-code-reviewer.md
CONSTRAINTS:
  - Check: one adapter point (scan over is_shipped paths, control fails when planted); memory off leaves
    briefs byte-identical (test_memory_off_parity.py) and /task and /journal-add untouched; unavailable
    and hung server give one line and continue; every server field neutralised (probe tests); no item
    reaches the architect before the user's applicability answer; provenance never stronger than the
    table; registry text is read only through the extended shared reader in generate_registry_digest.py
    (digest byte-identical, hook a thin normal-import caller, no importlib); candidates only from entries
    whose own line names the contract; capture only in step 5a after a live flipped run, refusing
    brief-not-carried before any send; capture is its own question after the flip on both /pr-merged
    and /flow, and the records confirmation (step 3 / Step 8) is unchanged and still before the writing
    run; the stop rule holds; receipts carried by the records pull request; the Step 1.5 and capture
    stops are listed in /flow; the scan walks named folders and excludes .claude/worktrees/; no frontmatter key, hook, store or
    background process added; each part names its existing mechanism as in Reused Mechanisms.
  - Six fixed sections; the file does not exist yet and you create it. Name base..head.
  - Verdict line alone, exactly one of: "**Verdict:** pass", "**Verdict:** pass-with-findings",
    "**Verdict:** blocked". Write the Gate Output <artefact stem>.gate.json beside it.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

### 6. Cloud skill and provider references (`python-ai-developer`)

**Depends on:** 1

**Files to touch:**
- `skills/cloud-engineering/SKILL.md`
- `skills/cloud-engineering/references/cross-cutting.md`
- `skills/cloud-engineering/references/azure.md`
- `skills/cloud-engineering/references/aws.md`
- `skills/cloud-engineering/references/gcp.md`
- `skills/cloud-engineering/references/terraform.md`
- `skills/cloud-engineering/references/bicep.md`
- `skills/cloud-engineering/references/docker.md`
- `skills/cloud-engineering/references/kubernetes.md`
- `.claude/scripts/tests/test_cloud_text_scans.py`

**Pre-written TASK block:**
```
TASK: Write the cloud-engineering skill. It reads cloud.providers and cloud.iac and opens ONLY the
  matching references, halting with one line when cloud.providers is unset. cross-cutting.md covers
  networking, identity and access, secrets, messaging, storage, observability, cost, governance,
  deployment validation and troubleshooting, each as a provider-neutral rule plus a pointer to the
  provider file. Each provider and tool file maps those topics to concrete services and to
  NON-MUTATING validation commands, written as ready contractLanding.verification.steps entries.
CONTEXT: concept contract (Cloud profile, Reused Mechanisms rows for cloud).
FILES: the ten listed.
CONSTRAINTS:
  - Provider choice comes only from the profile, never from where an MCP server runs.
  - State the cloud scope rule near the top of SKILL.md: this skill does design, review, validation
    (non-mutating commands only) and troubleshooting. It never runs a deploy, apply, create, update or
    destroy command against a live environment; it writes the command out for the user to run, and the
    user's normal Claude Code permission prompts and the existing destructive-operation guards apply
    unchanged. No settings file is written and no permission check is run.
  - Mutating commands appear only inside a block labelled "for the user to run".
  - test_cloud_text_scans.py: over agents/cloud-engineer.md (when present) and skills/cloud-engineering/,
    every line carrying apply, create, update, destroy, delete, deploy, install, upgrade, uninstall or push
    as a command sits inside a "for the user to run" block; a planted line is the positive control.
  - Names no project; passes the project-name check.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

### 7. Cloud agent and review coverage (`python-ai-developer`)

**Depends on:** 6

**Files to touch:**
- `agents/cloud-engineer.md`
- `agents/security-auditor.md`
- `skills/debug/SKILL.md`
- `.claude/scripts/pr_merged.py`
- `.claude/scripts/tests/test_pr_merged.py`
- `.claude/scripts/tests/test_agent_skill_preloads.py`

**Pre-written TASK block:**
```
TASK: Add the cloud-engineer implementer agent (tools: Read, Edit, Write, Grep, Glob, Bash,
  mcp__codegraph__*; refuses without an approved contract and when cloud.providers is unset; writes
  only under cloud.roots; does design, review, validation with non-mutating commands only, and
  troubleshooting; never runs a deploy, apply, create, update or destroy command against a live
  environment, and writes it out for the user to run instead; the user's normal permission prompts and
  the existing destructive-operation guards apply unchanged).
  Add an infrastructure-as-code checklist section to security-auditor, active when cloud.providers is set.
  Route container and infrastructure bugs in /debug to cloud-engineer. Add cloud-engineer to
  DEFAULT_IMPLEMENTERS.
CONTEXT: concept contract (Extension Points, Failure Modes).
FILES: the six listed.
CONSTRAINTS:
  - Follow the subagent_type literal rule in test_plugin_text_scans.py.
  - Only the docker-master-goat line changes in /debug; the other unshipped names stay (follow-up stub).
  - The agent text must pass test_cloud_text_scans.py (block 6), which covers agents/cloud-engineer.md.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

### 8. Review cloud capability (`fullstack-code-reviewer`)

**Depends on:** 6, 7

**Files to touch:**
- `.claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t8-review-cloud-capability-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review blocks 6-7 and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
FILES: .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t8-review-cloud-capability-fullstack-code-reviewer.md
CONSTRAINTS:
  - Check: capability off while cloud.providers is unset; only selected references load; the cloud scope
    rule is stated in both the skill and the agent; no shipped cloud text instructs a mutating command
    (test_cloud_text_scans.py, control fails when planted); no settings file, permission row, hook or
    finish-install change was added (Decision note, Revision 5); database guards untouched;
    the Cloud coverage table in Appendix A.6 is now true.
  - Six fixed sections, base..head named, verdict line exactly "**Verdict:** pass",
    "**Verdict:** pass-with-findings" or "**Verdict:** blocked"; write the Gate Output beside it.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

### 9. Documentation (`python-ai-developer`)

**Depends on:** 13, 14, 15, 16

**Files to touch:**
- `README.md`
- `CONTRIBUTING.md`
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/VOCABULARY.md`
- `.claude/registries/JOURNAL.md`

**Pre-written TASK block:**
```
TASK: Document the architecture (one diagram of the delivery chain with the two memory call sites:
  /design-first Step 1.5, and the separate capture question after the flip in /pr-merged or /flow), the memory boundary, the
  configuration slots, MCP integration (main session only, tool names in slots, shapes in one script,
  one attempt bounded by the host MCP timeout), lifecycle separation, the cloud capability with its scope
  rule (it never runs live-changing commands, hands them to the user, and adds no permission mechanism),
  and Known limitations (shape v0 provisional; no capture retry; changed items found only when
  re-returned; an empty project-name token list keeps all capture project-scoped; Cursor and Codex MCP
  naming untested; the cloud scope rule is enforced in text only, by the user's own permission prompts
  and the existing guards; cloud-management MCP deferred; AND, from review I3 of the t5 review: the
  mcp__<server>__<tool> id form and the host MCP timeout returning an error are unverified, because the
  block 3 stub-server trials left no recorded evidence, so a project should not set memory.shape until
  that trial is run). Document the Project history record (Revision 7) exactly as the Business Concept
  term defines it: what it holds, that /design-first and the data-architect read it, which confirmed
  steps append to it, and that the Central Memory System only supplements it; do not claim that every
  flow reads or appends it. Update the README skill and agent counts, and the working-agreement count and
  list (README "6 working agreements" rows and the agreements paragraph) to seven, naming the block 15
  agreement. In CONTRIBUTING, add the rule: no shipped file (check_version_bump
  is_shipped) but memory_boundary.py names a memory tool. Append the Memory adapter entry to the Universal
  tier of MECHANISMS.md and the confirmed terms (Business Concept list, including Project history record)
  to VOCABULARY.md. Append to JOURNAL.md the entry the t5 review's Disposition item 6 drafts ("A skill
  written around an adapter refusal hides a contract divergence"), verbatim, plus the pre-approval critic
  entries the user confirmed for the Revision 7 critique, as the main session records them at approval.
CONTEXT: concept contract (whole); the t5 review at
  .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t5-review-memory-boundary-fullstack-code-reviewer.md
  (I3 and Disposition items 5 and 6) and the block 16 re-review.
FILES: the five listed.
CONSTRAINTS: plain language; no version files; counts must match skills/ and agents/. README and
  CONTRIBUTING are exempt from the single-adapter scan by is_shipped, so they may name the two tools.
  Registry appends are append-only and go in the Universal tier. The registries are shipped and are
  NOT exempt from the scan: the Memory adapter entry and every memory term say "the configured retrieve
  tool" and "the configured capture tool", never the literal names. Run test_plugin_text_scans.py after
  the appends.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

### 10. Review documentation (`fullstack-code-reviewer`)

**Depends on:** 9, 14, 15, 16

**Files to touch:**
- `.claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t10-review-documentation-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review block 9 against the merged code and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
FILES: .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t10-review-documentation-fullstack-code-reviewer.md
CONSTRAINTS:
  - Check every documented behaviour against the code (journal 2026-10-04 "check a documented guard
    behaviour"); counts; every Known limitation present, including the unverified MCP tool id form and
    host timeout (t5 review I3); the Project history record documented as the Business Concept term
    defines it (no claim that every flow reads or appends it), with the Central Memory System only
    supplementing it; the README working-agreement count matches .claude/agreements/; the registry appends from block 9 (MECHANISMS, VOCABULARY, JOURNAL)
    match the merged code. Do NOT append to any registry yourself: report a missing append as a finding.
  - Six fixed sections, base..head named, verdict line exactly "**Verdict:** pass",
    "**Verdict:** pass-with-findings" or "**Verdict:** blocked"; write the Gate Output beside it.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

### 11. Scope note on version, registries and deferred work

No block raises the version. The landing raises it once, and corrects the manifest description counts (Open Question 15). Registry appends (MECHANISMS, VOCABULARY) are shipped files. They ride with block 9, which merges before the landing raise. Journal entries confirmed at the approval step ride with the first block that merges. Every review gate names only its artefact (Open Question 20). The token-efficiency fixes and the other audit defects are in `.claude/concepts/followups/2026-11-01-token-efficiency-and-audit-defects.followup.md`, `**Issue:** pending` until Step 3.4 fills it. Revision 5 removed the deployment-authorization block and the conditional deploy-guard add-on block at the user's instruction. No block touches `auto_improve_finish_install.py`, its test, `plugin_doctor.py`, any settings file or the brief. The only finish-install change is block 15's text in `skills/auto-improve-finish-install/SKILL.md` (Revision 7); it adds no cloud permission row, so the cloud reviews' check "no finish-install change was added", which concerns those rows, still holds.

**Revision 6 (2026-11-02, user instruction).** The review of block 7 (`t8`, verdict `blocked`) found that `agents/cloud-engineer.md` tells the agent to load the `cloud-engineering` skill with the Skill tool while its tool line omits `Skill` (finding B1), and that `/debug` hands a cloud bug to the agent without a contract path, which the agent refuses (finding W3). The user decided to keep both the `cloud-engineer` agent and the `cloud-engineering` skill and to fix B1. Blocks 12 and 13 are appended so that block identities and records of blocks 1 to 10 stay as they are. Block 9 now depends on block 13 instead of block 8, because block 13's review supersedes block 8's. Findings W1 and W2 (scanner tightening) are not in scope; they stay recorded in the block 8 review. This revision adds no agent, skill, flow or mechanism, and no block raises the version. The contract was amended without a new critic round, because the change is two small blocks that fix a recorded review finding; `/critique-now` can still be run on it.

**Revision 7 (2026-11-02, user instruction).** Two inputs.
- **The block 5 review** (`t5`, verdict `blocked`, `.claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t5-review-memory-boundary-fullstack-code-reviewer.md`) found that `record` refuses the `unconfigured` state, which the Commands table, Extension Points Step 1.5 point 3 and I-M1 say it records (B1). Block 3's skill text documented around the refusal, and a test name claimed coverage it lacked. The review also found that receipt lines lose their source reference (W1), that `changed-items` is fed the raw response (W2), and that provenance is chosen by substring (W3). It added three information notes: a trailing note paragraph is absorbed into the bullet above it (I1), `--default-branch` is hard-coded to `master` (I2), and the block 3 stub-server trials left no evidence (I3). Block 14 fixes B1, W1 to W3, I1 and I2. Block 9's Known limitations now state I3. Data Shapes are amended in place and marked "Revision 7": the `record` and `changed-items` rows of Commands, Trigger matching under the provenance table, and the entry end under Candidate reading.
- **A new user requirement:** "the plugin must instruct to use the memory system it currently use/provide in the host repos". The user clarified this as the file-based record (registries, contracts and so on) that a host project uses to track its history. This is the new term **Project history record** (Business Concept; first drafted as "Project memory", renamed by the user after the Revision 7 critique). Block 15 states it in host onboarding (`/auto-improve-finish-install`), on every printed line of `/design-first` Step 1.5 and its reference, and in one new shipped agreement delivered at session start. It reuses the doctor (report, then ask before `--fix`), the finish-install skill, the Step 1.5 printed lines and Session-start context delivery, and adds no store, hook, seed or frontmatter key.

**Why two blocks.** The requirement is its own block (15), not part of the fix block. Block 14 is judged against a recorded review report and stays limited to it: it carries no Project history record text, and the suffix on the printed lines is added by block 15 in the skill text, not in `memory_boundary.py`. Block 15 adds a new acceptance criterion and touches a skill (`/auto-improve-finish-install`) and the shipped agreements that no fix touches. The two blocks share three files (`skills/design-first/SKILL.md`, `references/central-memory.md` and `test_memory_off_parity.py`), so block 15 depends on block 14 and they never run in parallel. Both blocks change only text the user sees, plus block 14's script fixes. They are reviewed together by block 16, which supersedes the block 5 review the way block 13 superseded block 8.

**What else changes.**
- Blocks 9 and 10 now depend on 14, 15 and 16, so block 9 is released only after the re-review passes. Block 16 replaces block 5 in block 9's Depends on.
- Block 9 also appends the journal entry the t5 review drafted, the user-confirmed Revision 7 critic entries, documents the Project history record and updates the README agreement count, so it gains `JOURNAL.md`.
- No block raises the version. The user answered Open Questions 22 and 23 and the critic findings on 2026-11-02, and the answers are written into the body; this is the re-approval of Revision 7. The Revision 7 critique was run (`## Critique (Revision 7)`, at the end), and each finding carries its disposition there.
- Budget: this contract is over the template's budget rule (critique Revision 7 NIT). The superseded critique rounds and the appendices stay inline; at the user's instruction this amendment only notes it and trims nothing. Moving them to `.claude/contract-history/` (Open Question 14) is still owed and has no block yet.

**Revision 8 (2026-11-03).** The landing halted at gate P7; the remedy and its review are blocks 17 and 18, and the Revision 8 note opens block 17.

**Revision 9 (2026-11-03).** The landing halted at gate P3 on block 18's `blocked` review; the fix and its re-review are blocks 19 and 20, and the Revision 9 note opens block 19. Correction to the first paragraph of this note: the landing does not correct the manifest description counts. Its only manifest write is `raise_manifests`, which rewrites the `"version"` fields alone. Who corrects them is Open Question 33.

### 12. Cloud agent skill-load fix (`python-ai-developer`)

**Depends on:** 7

**Files to touch:**
- `agents/cloud-engineer.md`
- `skills/debug/SKILL.md`
- `.claude/scripts/tests/test_agent_skill_preloads.py`

**Pre-written TASK block:**
```
TASK: Fix review findings B1 and W3 of the block 8 review.
  B1: add Skill to the tool line of agents/cloud-engineer.md, so the line reads
  "Read, Edit, Write, Grep, Glob, Bash, Skill, mcp__codegraph__*". Add the instruction that if the
  cloud-engineering skill cannot be loaded the agent stops and says so, as agents/senior-test-engineer.md
  does. Update the test in test_agent_skill_preloads.py that pins the old tool line, and add a test that
  every agent whose body says to invoke a skill with the Skill tool lists Skill on its tool line or
  preloads it with a skills: entry (cover all files under agents/).
  W3: in skills/debug/SKILL.md, make the hand-off to cloud-engineer carry a contract_path when one exists,
  and when none exists say that a contract is required first (run /design-first) instead of invoking the
  agent. Change nothing else in /debug.
CONTEXT: concept contract (Revision 6); the block 8 review at
  .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t8-review-cloud-capability-fullstack-code-reviewer.md
  (findings B1 and W3).
FILES: the three listed.
CONSTRAINTS:
  - No new agent, skill or flow. Do not bump the plugin version (Parent Branch Delivery Rule).
  - Follow the subagent_type literal rule in test_plugin_text_scans.py.
  - Keep agents/cloud-engineer.md passing test_cloud_text_scans.py.
  - Run test_agent_skill_preloads.py, test_cloud_text_scans.py and test_plugin_text_scans.py and quote the results.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

### 13. Re-review cloud capability (`fullstack-code-reviewer`)

**Depends on:** 6, 7, 12

**Files to touch:**
- `.claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t13-re-review-cloud-capability-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review blocks 6, 7 and 12 afresh and write the review artefact. This review supersedes the block 8 review.
CONTEXT: concept contract at .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md (Revision 6)
FILES: .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t13-re-review-cloud-capability-fullstack-code-reviewer.md
CONSTRAINTS:
  - Start from a cold context. Do not read the block 8 review before forming your own findings; read it
    afterwards only to confirm that B1 and W3 are cleared.
  - Check the same list as block 8: capability off while cloud.providers is unset; only selected references load,
    on both the skill path and the agent path; the cloud scope rule is stated in both the skill and the agent;
    no shipped cloud text instructs a mutating command (test_cloud_text_scans.py, control fails when planted);
    no settings file, permission row, hook or finish-install change was added; database guards untouched;
    the Cloud coverage table in Appendix A.6 is true.
  - Six fixed sections, base..head named, verdict line exactly "**Verdict:** pass",
    "**Verdict:** pass-with-findings" or "**Verdict:** blocked". Write the Gate Output beside it, and set its
    supersedes field to the block 8 review artefact.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

### 14. Memory boundary review fixes (`python-ai-developer`)

**Depends on:** 2, 3, 4

**Files to touch:**
- `.claude/scripts/memory_boundary.py`
- `.claude/scripts/tests/test_memory_boundary.py`
- `.claude/scripts/tests/test_memory_off_parity.py`
- `.claude/scripts/generate_registry_digest.py`
- `.claude/scripts/tests/test_registry_entries.py`
- `skills/design-first/SKILL.md`
- `skills/design-first/references/central-memory.md`

**Pre-written TASK block:**
```
TASK: Fix findings B1, W1, W2, W3, I1 and I2 of the block 5 review. Tests first.
  B1: in cmd_record, refuse "not-enabled" only when the profile state is "disabled" or the outcome's state
  is "disabled". Under profile state "unconfigured", write only the line
  "Memory: unconfigured (<reason>) | <date>", with the reason taken from the profile (read_config), never
  from the outcome, and ignore any retrieved or reported entries. --receipts still requires "enabled".
  Do not change the status "line" strings (block 15 adds the printed suffix in the skill text). Rewrite
  skills/design-first/SKILL.md Step 1.5 point 3 as: print its line (one line), then record it with
  record (outcome {"state": "unconfigured", "date": "<today>"}) into the brief whose branch: is the
  branch you are on (the same rule as point 4), then go to Step 2. With no such brief, print one line
  saying the memory record was skipped for want of a brief (point 4's wording) and go to Step 2; that is
  not a failure. Only a refusal or non-zero exit from record when a brief was found is a failure under
  point 2. Delete the sentence saying a not-enabled refusal "is expected". Split test_unavailable_and_unconfigured_states_are_recorded into an
  _unavailable_ test and an _unconfigured_ test. The second asserts the "Memory: unconfigured (shape-unknown)"
  line, frontmatter bytes unchanged, no Retrieved line even when the outcome carries items, and that
  --receipts is refused with not-enabled. Add an unconfigured variant to the positive control in
  test_memory_off_parity.py; the three disabled profiles stay byte-identical.
  W1: receipt_line accepts source_ref as the object capture-candidates emits ({file, line, title, date})
  and renders "<file>:<line>" (file through clean_text, line through safe_token). It keeps accepting a
  string. Use one helper for both receipt_line and cmd_capture_request's source_ref, not a copy. Add a
  test that runs capture-candidates on a fixture, puts a candidate's own source_ref object into a receipt,
  runs record --receipts and asserts "<file>:<line>" on the Captured: and Not sent: lines.
  W2: in central-memory.md section 3, write the normalise output to a second temporary file and pass that
  file to changed-items. In cmd_changed_items, pass each input item through the same per-item rules
  normalise applies (call the same function, do not copy it) and compare versions as the normalised
  strings. Tests: a raw item with scope NOT-A-SCOPE raises no notice; an integer version 1 against a
  recorded "1" raises no notice. Update the parity test's changed-items call to use a normalised file.
  W3: map a Trigger only by an exact match of its whole value (trimmed, case-folded, surrounding backticks
  removed): "pre-approval critic" gives user-decision; "post-impl divergence" gives source-code-fact;
  "manual" and "post-approval" are skipped as ai-hypothesis; anything else is skipped as unknown-trigger.
  Tests: "manual (follow-up to a pre-approval critic finding)" and "post-approval, found after post-impl
  review" are both skipped and never offered; each of the four canonical values maps as the table says;
  on the current JOURNAL.md every entry's mapping is unchanged.
  I1: in entry_blocks, an entry's own text also ends at a blank line followed by a non-indented line that
  is not a top-level match (Candidate reading, Revision 7). Test: a planted note paragraph naming
  .claude/concepts/<slug>.md after the last bullet of a section does not make that bullet a candidate.
  TierSplitIsByteIdentical stays green.
  I2: capture-candidates --default-branch defaults to None. When it is None, bind
  pr_merged.default_branch_or_none fail-soft (the existing _bind list at memory_boundary.py:58) and call
  it with cwd=str(<--project root>), so the project's own origin/HEAD is read, never the process's
  working directory. Pass the name it returns to select_linked_brief as default_branch_name. When it
  returns None (or the function is unbound), refuse "default-branch-unknown" before anything is offered,
  with one line saying to pass --default-branch <name>; never call pr_merged.default_branch(), which
  falls back to "master" (pr_merged.py:2380-2381), and never let select_linked_brief reach it with None
  (pr_merged.py:3016). Tests: a fixture project whose origin/HEAD is main, run from a different working
  directory, links the brief through main; a fixture with no origin/HEAD and no flag refuses
  default-branch-unknown and offers nothing; an explicit --default-branch still wins.
CONTEXT: concept contract (Revision 7: Commands, Provenance mapping and Trigger matching, Candidate
  reading, Extension Points Step 1.5); the block 5 review at
  .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t5-review-memory-boundary-fullstack-code-reviewer.md
  (B1, W1-W3, I1, I2).
FILES: the seven listed.
CONSTRAINTS:
  - No new subcommand, frontmatter key, hook, store or background process. Do not bump the plugin version
    (Parent Branch Delivery Rule).
  - I-M0 holds: with memory disabled, nothing is printed and no brief is touched.
  - Do NOT change the three tests that guard I-M0 (the disabled state): in test_memory_boundary.py,
    test_disabled_refuses_not_enabled_and_writes_nothing (:742-748, assertion at :747),
    test_an_outcome_that_says_disabled_writes_nothing (:750-755, assertion at :754) and
    test_receipts_with_memory_disabled_write_nothing (:860-866, assertion at :865). They must pass
    unchanged after B1. The only existing test to change is
    test_unavailable_and_unconfigured_states_are_recorded (:796), which B1 splits. If any other test
    asserts a refusal under unconfigured, change it and say why in your HANDOFF. Name each test after
    only what it asserts (journal entry drafted in the block 5 review).
  - Keep every pin passing: Step15TextTests in test_memory_off_parity.py (the regex
    "unconfigured.{0,300}one line" must still match), test_parent_branch_rule_text.py and
    test_repo_consistency.py SENTENCE_PLACEMENT for design-first, test_skill_script_lookup.py (the lookup
    block is unchanged), and test_plugin_text_scans.py (no skill text names a memory tool).
  - The adapter still never loads the hook file and parses no registry text itself.
  - Run test_memory_boundary.py, test_memory_off_parity.py, test_registry_entries.py,
    test_plugin_text_scans.py, test_skill_script_lookup.py, test_parent_branch_rule_text.py,
    test_repo_consistency.py and the .claude/hooks/tests suite, and quote the results.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

### 15. Project history record in host onboarding (`python-ai-developer`)

**Depends on:** 14

**Files to touch:**
- `skills/auto-improve-finish-install/SKILL.md`
- `skills/design-first/SKILL.md`
- `skills/design-first/references/central-memory.md`
- `.claude/scripts/tests/test_memory_off_parity.py`
- `.claude/agreements/use-the-project-history-record.md`
- `.claude/hooks/tests/test_working_agreements.py`

**Pre-written TASK block:**
```
TASK: State the Project history record requirement (Business Concept, Revision 7) in host onboarding,
  on every printed line of /design-first Step 1.5, and in one shipped session-start agreement.
  1. skills/auto-improve-finish-install/SKILL.md: add a section "The project history record" after Stage 2
     and before "Add-ons". It says that the project's record of its design history is its Project history
     record: .claude/registries/MECHANISMS.md, VOCABULARY.md and JOURNAL.md (seeded by the doctor),
     INTEGRATION.md where the project keeps one (no seed exists for it), the concept contracts and
     follow-up stubs under .claude/concepts/, and the Work Item Briefs under .claude/work-items/.
     Who uses it, exactly: /design-first and the data-architect read it on every design. /task writes the
     brief and the data-architect the contract. /design-first appends to JOURNAL.md only the critic
     findings the user confirmed (Steps 3 and 5); fullstack-code-reviewer appends on a justified contract
     divergence and, as janitor, to MECHANISMS.md and VOCABULARY.md; /journal-add appends a manual lesson.
     The contract-critic reads it and never appends. Do not say that anything appends "on every run".
     Commit these files, and never delete, gitignore or bypass them. The Central Memory System, when a
     project switches it on through the memory.* profile slots, only supplements them: it never replaces
     or hides them, and a local entry wins a conflict until the user decides.
     The check (Open Question 23, "Report, then ask before --fix"): run the doctor in report mode
     ($PY "<dir of FI>/plugin_doctor.py" --project .). If it prints "plugin:  NOT FOUND - pass --plugin",
     say in one line that the registries cannot be seeded and ask for the plugin path; offer --fix only
     with --plugin <path>. If it lists any "missing" entry, show the user that whole list as exactly what
     --fix would create: --fix creates every missing requirement in the doctor's REQUIREMENTS, not only the
     registries (for example .claude/north-stars, .claude/orchestrator/results, the contract template,
     .claude/area-mapping.json and .claude/work-item-conventions.json); it never overwrites and leaves
     .claude/settings.json alone. Run $PY "<dir of FI>/plugin_doctor.py" --fix only after the user says
     yes; never run it on its own. Add one Closing bullet (which history-record files exist and which the
     doctor created, if the user agreed) and one Anti-patterns bullet (treating the Central Memory System
     as the project's record, skipping the registries, or running --fix without asking).
  2. skills/design-first/SKILL.md Step 1.5: add one lead sentence. The project's design history is its
     Project history record (the registries, including INTEGRATION.md where present, the concept contracts
     and the briefs). Step 2 and the architect read it in every memory state, including disabled. The
     Central Memory System only supplements it: its items never replace, hide or skip a registry read. In
     point 1, add after the existing sentences that the Project history record is read as always. Nothing
     is printed or written on disabled. Every line Step 1.5 prints in any other state ends with the fixed
     suffix "; design continues from the project history record (registries and concept contracts)": the
     point 2 failure line, the point 3 status line and its skipped-for-want-of-a-brief line (block 14's
     text), and the point 4 skipped-for-want-of-a-brief line. The skill text appends the suffix when it
     prints; memory_boundary.py is not changed.
  3. references/central-memory.md, Ground rules: add the same rule. Each one-line "unavailable" print ends
     with the same suffix.
  4. test_memory_off_parity.py: add a ProjectHistoryRecordTextTests class. It pins that the finish-install
     section names the three seeded registries, INTEGRATION.md, .claude/concepts/ and .claude/work-items/,
     says the Central Memory System only supplements them, runs plugin_doctor.py in report mode, and asks
     before --fix (a "--fix" mention is preceded within the section by a confirmation sentence); that it
     does not contain "on every run" next to "append". It pins the Step 1.5 lead sentence, the suffix on
     points 2, 3 and 4, and the central-memory.md ground rule. It pins that Step 1.5 point 1 still prints
     nothing and writes nothing on disabled.
  5. .claude/agreements/use-the-project-history-record.md (new shipped agreement, user answer "Yes, add a
     session-start agreement"): first line "# Use the Project History Record", then three or four short
     sentences, under about 400 characters in all. It says: the registries (.claude/registries/) and the
     concept contracts (.claude/concepts/) are the project's memory and its design history; read them and
     use them; a central MCP memory system, when one is switched on, only supplements them and never
     replaces them. It names no project, person, machine path, incident date, MCP server or memory tool.
  6. .claude/hooks/tests/test_working_agreements.py: add the file to REQUIRED and add a SHIPPED_PHRASES
     row for it (for example "project's memory", "only supplements", "concept contracts"). Rename
     case_real_shipped_folder_is_exactly_the_six_required_files and
     case_s3_the_phrase_table_covers_exactly_the_six_required_files (and their add() labels and messages)
     to say seven, so each test is named after what it asserts.
CONTEXT: concept contract (Revision 7: Business Concept "Project history record", Extension Points
  (Step 1.5, /auto-improve-finish-install, Shipped agreements), Reused Mechanisms row "Telling a host
  project...", Alternatives Considered Options I-K, Failure Modes (Revision 7 entries), Open Questions 22
  and 23 as answered); MECHANISMS.md "Session-start context delivery".
FILES: the six listed.
CONSTRAINTS:
  - Text and tests only. Do not touch auto_improve_finish_install.py, plugin_doctor.py, the doctor's
    REQUIREMENTS, memory_boundary.py, working-agreements.py, working-agreements.rules.json, any settings
    file, any hook code, agents/data-architect.md (its rule 9 already ranks items below the registries)
    or any registry. Add no seed or template for INTEGRATION.md (Open Question 22). No new store, seed,
    hook or frontmatter key. Do not bump the plugin version.
  - The shipped agreement set must still fit the default limit with nothing dropped
    (case_real_shipped_set_fits_default_limit_with_nothing_dropped, 9000 characters), plain-language must
    stay first (INV-6), and the new file must pass every real-file case in test_working_agreements.py.
    test_plugin_text_scans.py scans .claude/agreements/, so the agreement names no memory tool.
  - test_plugin_manifests.py INV-14: every --flag the finish-install text names must exist in
    auto_improve_finish_install's parser unless the line names plugin_doctor, so keep each doctor command
    on a line that names plugin_doctor.py. INV-13: frontmatter name and user_invocable unchanged, and the
    description stays non-empty.
  - Keep passing, without editing them: test_plugin_manifests.py, test_skill_script_lookup.py (the lookup
    blocks in finish-install and design-first are unchanged), test_parent_branch_rule_text.py,
    test_repo_consistency.py, test_plugin_text_scans.py (no memory tool name in any text),
    test_auto_improve_finish_install.py and test_plugin_doctor.py. Also keep Step15TextTests passing
    (the disabled regex "disabled.{0,300}print(s)? nothing.{0,200}writ(e|es) nothing", so the new
    sentence goes after it). If one of these pins must change, stop and report it; do not edit the file.
  - Run the suites named above plus test_memory_off_parity.py and
    py -3 .claude/hooks/tests/test_working_agreements.py, and quote the results.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

### 16. Re-review memory boundary (`fullstack-code-reviewer`)

**Depends on:** 2, 3, 4, 14, 15

**Files to touch:**
- `.claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t16-re-review-memory-boundary-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review blocks 2, 3, 4, 14 and 15 afresh and write the review artefact. This review supersedes the block 5 review.
CONTEXT: concept contract at .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md (Revision 7)
FILES: .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t16-re-review-memory-boundary-fullstack-code-reviewer.md
CONSTRAINTS:
  - Start from a cold context. Do not read the block 5 review before forming your own findings. Read it
    afterwards only to confirm that B1, W1, W2 and W3 are cleared and that I1 and I2 are handled.
  - Check the same list as block 5. Then check Revision 7: record writes the unconfigured line and
    refuses only disabled (and --receipts unless enabled); the skill no longer documents a refusal as
    expected; receipts carry <file>:<line> from the real capture-candidates output; changed-items gets
    the normalised file and applies the normalise rules; Triggers map only by exact canonical value; a
    trailing note paragraph is no entry's text; --default-branch is not hard-coded and, when unset, is
    read with default_branch_or_none(cwd=<project>) or refused as default-branch-unknown; the unconfigured
    path records into the brief whose branch: is the current branch and treats a missing brief as a
    skipped line, not a failure; the three I-M0 disabled tests are unchanged.
  - Check block 15: finish-install, /design-first Step 1.5 and its reference, and the new shipped
    agreement state that the Project history record is the project's record and that the Central Memory
    System only supplements it; the finish-install text says exactly who appends (no "on every run"
    claim); finish-install runs the doctor in report mode, shows what --fix would create, and runs --fix
    only on the user's yes; every Step 1.5 printed line carries the suffix; the disabled path still prints
    and writes nothing (I-M0, test_memory_off_parity.py); no change to plugin_doctor.py or
    memory_boundary.py from block 15; test_working_agreements.py names the new file and the set fits the
    limit; no store, seed, hook or frontmatter key added.
  - Six fixed sections; the file does not exist yet and you create it. Name base..head.
  - Verdict line alone, exactly one of: "**Verdict:** pass", "**Verdict:** pass-with-findings",
    "**Verdict:** blocked". Write the Gate Output <artefact stem>.gate.json beside it, and set its
    supersedes field to the block 5 review artefact.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

### 17. Merge the default branch into the parent branch (`python-ai-developer`)

*Revision 8 (2026-11-03), a remedy sub-task.* The user answered Open Questions 24-28 and the Revision 8 critique on 2026-11-03, and the answers are written in below. The amendment awaits only the user's final approval at `/design-first` Step 3. `Status` stays `approved` in the header for the blocks already delivered. It adds no data shape, mechanism or term. Blocks 1-16 keep their identities and records, and 9 and 10 stay as delivered.

**Why.** Landing run `20261103T101941Z-58fe7b` (`.claude/state/landing/2026-11-01-memory-client-and-cloud-engineering/report.json`) halted at gate P7, `unresolvable-conflict`: "`.claude/registries/JOURNAL.md` conflicts and is neither a union path nor regenerated". Nothing reached `master`. `master` (8ea2dd4, version 0.14.x) gained the records-leftover-cleanup work (#178 and later) after the parent branch (0.12.4) was cut, while block 9 appended to the same registry tails. The t10 review (`pass-with-findings`) also left text fixes W1, W2, I1, I2, I3 and I5 owed before the landing's flip; entries appended after that flip are never offered for capture.

**Conflicting files (computed 2026-11-03, `master` at 8ea2dd4; Open Question 24).** The main session ran `git merge-tree --write-tree --name-only origin/feature/memory-client-and-cloud-engineering origin/master`. It reports conflicts in exactly five files:
- `.claude/registries/JOURNAL.md`, `.claude/registries/MECHANISMS.md` and `.claude/registries/VOCABULARY.md`. Both sides appended at the end of the Universal tier. In JOURNAL.md, master added "2026-11-02 — A sweep that deletes every proven file..." and this contract added the t5 entry, both after the 2026-11-01 "After merging a base..." entry.
- `README.md`.
- `skills/pr-merged/references/contract-completion.md`.

Four files that both sides changed are auto-merged by git with no conflict: `.claude/scripts/pr_merged.py`, `.claude/scripts/tests/test_pr_merged.py`, `skills/flow/SKILL.md` and `skills/pr-merged/SKILL.md`. No manifest conflicts. That conclusion rests on the `merge-tree` result alone. The P7 halt on JOURNAL.md proves nothing about the manifests, for two reasons. With `versionRaise: true`, a manifest conflict is a `version-fields` case, not `halt` (`land_contract.py:1038-1039`). And `plugin.json` and `.cursor-plugin/plugin.json` sort after JOURNAL.md. If `master` moves before block 17 runs, git's own conflict list governs. A conflict in a file not listed below stops the block with `git merge --abort`.

**Version (Open Question 28, accepted).** No conflict with the version rule. The parent side never changed a manifest, and `merge-tree` reports no manifest conflict. So git takes `master`'s 0.14.x into all five entries, and no version file is edited by hand. The sub-task pull request is checked in `parent` mode (`check_version_bump.py:166-174`). That mode allows the base's version (0.12.4) or the version at `merge-base(origin/master, HEAD)`. After the merge, that merge base is the merged `master` commit itself, so 0.14.x is allowed and the check exits 0. It still exits 0 if `master` moves on later. Block 18's pull request is cut from the merged parent, where base and head both hold 0.14.x. The landing then merges `master` again, which is clean or a no-op, and `--raise` writes minor + 1 with patch 0 of `origin/master` (`exact_version`, `:91-97`). That is **0.15.0** while `master` stays on 0.14, and `--exact` checks the same value. A `master` that reaches 0.15 first moves the landing to 0.16.0. The precedent is block 6 of `.claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md` (#183, pull request #187).

**Journal entries for t10 W2.** The user confirmed all eleven, J1-J11 (Open Questions 25 and 26). They take the `/design-first` Step 3 shape.

The t10 review placed these entries in the landing's version-raise commit. Block 17 moves them into its own sub-task commit, for two reasons. The landing halts at P7 before its raise commit exists. And entries appended after the landing's flip are never offered for capture. `raise_manifests` commits only the manifests, so nothing is lost by the move. Source contract for all: `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`. The Trigger is `pre-approval critic` for J1-J10 and `post-impl divergence` for J11. Each title starts `2026-11-02 — `.
- **J1** (WARN reach) "A rule every session needs goes in a shipped agreement, not a once-run step". Lesson: before putting a standing instruction in an onboarding skill or one design step, check Session-start context delivery and list the routes (direct edit, `/debug`, `/journal-add`, sessions that never design) that would never see it. Apply when: a contract adds a standing instruction to `/auto-improve-finish-install`, one skill step or any once-run path. Tags: agreements, session-start, standing-guidance, reach.
- **J2** (WARN term collision) "Search a proposed term against agent frontmatter and host docs before adding it". Lesson: if the words already name something else (`memory: project`, the host's "project memory"), rename the term instead of adding "it is not X" to its definition. Apply when: a contract proposes a VOCABULARY term that reuses a word the repository or host already uses. Tags: vocabulary, term-collision, naming, agent-memory.
- **J3** (WARN `--fix`) "Describe a fixer a skill runs by everything it writes, and keep the skill's confirm-first promise". Lesson: describe `plugin_doctor.py --fix` (or any list-driven fixer) from its own requirement list (`REQUIREMENTS`, `apply_fixes`), and run it only after the user confirms the listed set. Apply when: a contract triggers `--fix` or another fixer that creates every missing item. Tags: plugin-doctor, fix-scope, confirmation, side-effects.
- **J4** (WARN tests) "Name the tests a fix may change by the state they guard, after reading them". Lesson: before telling an implementer to change tests "around" given lines, read each one; a test that guards a neighbouring invariant (here `disabled`, I-M0) is named as unchangeable. Apply when: a fix block's CONSTRAINTS tell the implementer to change or relax tests by line number. Tags: tests, invariant, fix-scope, line-reference.
- **J5** (WARN brief on the unconfigured path) "A path that calls a command must say how it finds the command's input". Lesson: when a step calls a command that needs an input (`record --brief`), state on that same path how the input is found and what happens when it is absent; a rule that lives only on a sibling path turns a normal case into a reported failure. Apply when: one branch of a skill step (unconfigured, disabled, error) calls a command whose argument is resolved only on another branch. Tags: skill-steps, missing-input, brief-linkage, degradation.
- **J6** (WARN Failure Modes) "A revision that adds a path adds its failure modes". Lesson: for each new script call, fixer run or degraded path a revision adds, add a Failure Modes entry whose mitigation cites a mechanism. Apply when: a contract revision adds blocks or Extension Points and leaves `## Failure Modes & Mitigations` unchanged. Tags: failure-modes, amendment, revision, completeness.
- **J7** (NIT stale lines) "After amending a contract, update every summary of the block graph". Lesson: re-check the header Revision line, the Handoff intro's block count and graph, and the prioritised plan's Depends on against the new blocks. Apply when: a revision adds, removes or re-links handoff blocks. Tags: amendment, summary-drift, handoff-graph.
- **J8** (NIT scope note) "Edit a reversed sentence where it stands". Lesson: when an amendment reverses an earlier claim, edit that sentence; do not keep it and add a later bullet that contradicts it. Apply when: a revision changes a claim made earlier in the same section. Tags: amendment, self-contradiction, scope-note.
- **J9** (NIT block 14 scope) "Keep a review-fix block to the review's findings". Lesson: put text for a new requirement in the block that owns the requirement, so each block's review judges one thing. Apply when: one revision adds both review fixes and a new user requirement. Tags: block-scope, review-fix, separation.
- **J10** (NIT suffix) "A rule titled 'every' must list every line it covers". Lesson: a rule for "every state" or "every printed line" names each line, including failure and skipped lines, and a test pins each. Apply when: a contract adds text to every output line or state of a step. Tags: every-claim, printed-lines, coverage.
- **J11** (t10 Disposition 7, verbatim from the review artefact) "A 'fails the build' claim must name the workflow that runs the check".
- No new entry (Open Question 25) for five findings, which re-apply existing lessons or are deferred:
  - the BLOCKER (re-applies 2026-10-22);
  - the WARN on the term definition (2026-10-28);
  - the WARN on "append on every run" (2026-10-04);
  - the WARN on the I2 reader (2026-10-15);
  - the budget NIT (deferred, Open Question 14).
- Critique rounds 1-3 were not journaled. No entries are added for them.

**Deferred review leftovers (Open Question 27).** The t16 review's W1 and I1-I5, and the t10 review's I4 and I6, go into one follow-up stub: `.claude/concepts/followups/2026-11-03-memory-boundary-review-leftovers.followup.md`, `**Issue:** pending`. No block of this contract fixes them.

**Main-session actions, outside any block:**
- Append the t10 reviewer-verdict line (Disposition 8) to `~/.claude/logs/reviewer-verdicts.jsonl`.
- In the parent brief, record "no new entry" for the five findings above, and that critique rounds 1-3 were not journaled.
- Create the follow-up stub named above and open its issue (`/design-first` Step 3.4).

**Depends on:** 9, 10

**Files to touch:**
- `.claude/registries/JOURNAL.md`
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/VOCABULARY.md`
- `README.md`
- `skills/pr-merged/references/contract-completion.md`
- `CONTRIBUTING.md`
- `skills/auto-improve-finish-install/SKILL.md`

The first five files are the computed conflicts; the last two take text fixes. No test pins the replaced sentences, so the text fixes change no test file. The four auto-merged files are not listed: they keep git's automatic merge and are not edited by hand.

**Pre-written TASK block:**
```
TASK: On the sub-task branch (cut from origin/feature/memory-client-and-cloud-engineering), run
  git fetch origin, then git merge origin/master, and resolve every conflict by hand. Commit the merge on
  its own. Then, in a second commit, apply the t10 text fixes and the confirmed journal entries.
  Merge:
  - Before resolving, list the conflicts (git diff --name-only --diff-filter=U) and quote them. If any
    conflicting file is not in Files to touch, stop, abort the merge (git merge --abort) and report the
    list: the contract must be amended first.
  - JOURNAL.md, MECHANISMS.md, VOCABULARY.md: both sides append at the end of the Universal tier. Keep
    every entry of both sides, verbatim, once each; never edit, reorder or drop an existing entry. Master's
    entries go first, then this contract's (precedent: block 6 of
    .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md). Keep each file's closing lines once.
  - skills/pr-merged/references/contract-completion.md: keep both sides' changes, so that both behaviours
    stay (master's records-leftover steps and this contract's step 5a capture).
  - Do not edit the four auto-merged files (pr_merged.py, test_pr_merged.py, skills/flow/SKILL.md,
    skills/pr-merged/SKILL.md). Check only that no function, class or test name is defined twice in
    them and every import is present; if one is, stop and report it (the contract must be amended).
  - README.md: keep both sides' sections. Every count (skills, agents, agreements, hooks, test cases of
    any suite either side changed) is rewritten from the merged tree and from what each suite reports
    when run; never add the two sides' numbers.
  Text fixes (second commit). Line numbers are from the parent tip before the merge and will shift in
  README.md; locate each sentence by its text.
  - W1, CONTRIBUTING.md:162-163: "A scan in .claude/scripts/tests/test_plugin_text_scans.py enforces it:
    run it before committing a change to a shipped file. It is not yet run in CI."
  - I1 and I2: one append-only sub-bullet under the Memory adapter entry of MECHANISMS.md:
    "**Correction (2026-11-03):** a new bullet registry as a capture source is one pair in the tuple in
    select_candidates; any other source kind is a new branch there with its own key and provenance rule
    (there is no source-kind table). The call is bounded by the host's MCP timeout, and by a deadline
    argument where the shape supports one (v0 sends deadline_seconds: 20)."
  - I3, in both README.md (~903, "The contract-critic reads it and never appends.") and
    skills/auto-improve-finish-install/SKILL.md (~292, "The `contract-critic` reads it and never
    appends."): replace with "The contract-critic appends only its Critique section to the contract
    under review, and never writes a registry."
  - I5, README.md:885-886: "With both off, every brief, every Step 1.5 run and every capture step is what
    it was before they existed. The Project history record rule below applies whatever the switches say."
  - W2: append to JOURNAL.md, after the merged tail, all eleven entries J1-J11 of block 17, in that
    order, each in the /design-first Step 3 shape (title "### 2026-11-02 — <title>", then
    Trigger, Source contract, Lesson, Apply when, Tags lines), J11 verbatim from the t10 artefact's
    Disposition item 7.
CONTEXT: concept contract, block 17 (Revision 8 note, conflict list, Version, journal entries); landing
  report .claude/state/landing/2026-11-01-memory-client-and-cloud-engineering/report.json; the t10 review
  .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t10-review-documentation-fullstack-code-reviewer.md
  (W1, W2, I1, I2, I3, I5, Disposition 7).
FILES: as listed.
CONSTRAINTS:
  - A change to any file not listed comes only from master through the merge; resolve nothing else by
    choosing a side.
  - Never edit plugin.json, .claude-plugin/plugin.json, .cursor-plugin/plugin.json or
    .claude-plugin/marketplace.json by hand. The merge brings master's version; the landing raises once.
  - Registry text names no memory tool literally ("the configured retrieve tool", "the configured
    capture tool").
  - No conflict marker may remain in any file (search for "<<<<<<<", "=======" at line start, ">>>>>>>").
  - Run, and report the exit code and case count of: test_pr_merged.py (on its own; it is large),
    every .claude/hooks/tests/test_*.py except test_gate_cost.py, test_plugin_text_scans.py,
    test_registry_entries.py, test_repo_consistency.py, test_memory_boundary.py, test_memory_off_parity.py,
    test_plugin_manifests.py, test_auto_improve_finish_install.py, test_check_version_bump.py,
    test_parent_branch_rule_text.py, test_skill_script_lookup.py and test_cleanup_delivered.py (the
    last three read the merged skills/pr-merged/references/contract-completion.md, skills/flow/SKILL.md
    and skills/pr-merged/SKILL.md, and pin sentences in them), and
    py -3 .claude/scripts/check_version_bump.py --base origin/feature/memory-client-and-cloud-engineering
    --default-branch master --head-ref <this branch>. A failure that also fails on origin/master is
    reported as such, with the origin/master run quoted, and is not fixed here.
  - Every command in a form that runs in PowerShell.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

### 18. Review merge and text fixes (`fullstack-code-reviewer`)

**Depends on:** 17

**Files to touch:**
- `.claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t18-review-merge-and-text-fixes-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review block 17 and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md (Revision 8, block 17)
FILES: .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t18-review-merge-and-text-fixes-fullstack-code-reviewer.md
CONSTRAINTS:
  - Start from a cold context. Name base..head (the parent tip before the merge, and block 17's head).
  - Merge: for JOURNAL.md, MECHANISMS.md and VOCABULARY.md, every entry heading of git show
    origin/master:<path> and of the pre-merge parent tip is present exactly once, unedited, master's
    first; no conflict marker in any file. Files in block 17's Files to touch are judged on content.
    Every OTHER file the merge commit changed against the parent tip carries no hand edit, judged by git
    blob ids, not bytes on disk:
    - a file only master changed (the manifests included) is identical to its version in the master
      commit that was merged;
    - a file both sides changed and git auto-merged (pr_merged.py, test_pr_merged.py,
      skills/flow/SKILL.md, skills/pr-merged/SKILL.md) is identical to the same path in the tree that
      git merge-tree --write-tree <pre-merge parent tip> <merged master commit> prints. It cannot equal
      origin/master, because it holds both sides.
    No name is defined twice in pr_merged.py or test_pr_merged.py.
  - Text fixes: W1, I1/I2 (one Correction sub-bullet, append-only), I3 (in both README.md and
    skills/auto-improve-finish-install/SKILL.md), and I5 read as block 17 states. The JOURNAL.md
    entries are exactly J1-J11, in that order and in the Step 3 shape. Every README count is true
    against the merged tree and the suites' own output.
  - Re-run the suites block 17 lists (including test_parent_branch_rule_text.py,
    test_skill_script_lookup.py and test_cleanup_delivered.py) and the parent-mode version check; quote exit codes; a failure
    that also fails on origin/master is reported as pre-existing.
  - Six fixed sections; the file does not exist yet and you create it. Verdict line alone, exactly one
    of: "**Verdict:** pass", "**Verdict:** pass-with-findings", "**Verdict:** blocked". Write the Gate
    Output <artefact stem>.gate.json beside it. Do NOT append to any registry yourself: report a missing
    append as a finding.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

### 19. Fix merged records steps and tree counts (`python-ai-developer`)

*Revision 9 (2026-11-03), a fix sub-task.* Revision 9 is approved by the user on 2026-11-03, including Question 33. The user accepted the recommendations of Open Questions 29-32 and asked for the eight `## Critique (Revision 9)` warnings to be folded in; blocks 19 and 20 carry both. Question 33 (the manifest descriptions) changes neither block. `Status` stays `approved` in the header for the blocks already delivered. It adds no data shape, mechanism or term. Blocks 1-18 keep their identities and records, and block 18's `blocked` artefact stays as recorded.

**Why.** Block 17 merged (#223), and its review, block 18 (#224, `.claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t18-review-merge-and-text-fixes-fullstack-code-reviewer.md`), returned `**Verdict:** blocked`. The landing (`land_contract.py`) then halted at gate P3. The review found the merge otherwise exact, with one blocker and one warning:
- **B1 (blocker).** In `skills/pr-merged/references/contract-completion.md`, the hand resolution kept both sides of the conflict hunk whole. The parent side was step 5a followed by the base's unchanged steps 6-9; the `master` side was master's rewritten steps 6-9. So the merged file holds the base's old steps 6-9 (first line "6. **Cut the branch in a flat worktree.**", last line "9. **Remove the records worktree.** Then name the copies left in the starting tree ...") right after step 5a, then master's steps 6-9 (first line "6. **Put the stable branch in a flat worktree.**"). The old step 6 cuts the records branch from `origin/<default>`, which master's step 6 and `skills/pr-merged/SKILL.md` ("One stable branch, added to and never re-cut") forbid. Confirmed on 2026-11-03 in the landing worktree, at lines 89-92 then 93-96; the line numbers are not the locator.
- **W1 (warning).** Four folder-tree counts in `README.md` are false against the merged tree. The merge did not cause them; both sides and the merge base had them already. Measured on 2026-11-03 in the landing worktree:

  | Tree line | README says | Tree has |
  |---|---|---|
  | `hooks/tests/` | 9 hook test suites | 23 `test_*.py` files |
  | `scripts/` | 15 workflow scripts, 3 shared helper modules | 23 workflow scripts and 3 helper modules (`_claude_paths.py`, `_contract_files.py`, `_contract_index.py`) |
  | `scripts/tests/` | 11 suites | 36 `test_*.py` files |
  | `references/` | 2 reference documents | 3 files |

- **Found while drafting this revision.** `test_parent_branch_rule_text.py` (class `CaptureAtDeliveryTextTests`, the step 5a test) ends step 5a's section at the heading `6. **Cut the branch`, which is the line B1 deletes. The test's `section` helper runs to the end of the file when the end heading is absent, so the test would still pass but would no longer pin step 5a alone. The end marker has to move.

**Decided, not fixed here (Critique Revision 9).**
- **The other tree counts.** Block 19 changes only the four counts W1 names, and block 20 judges only those four (critic WARN 5). The tree's other counts are reported by block 20 as information, never as a finding against block 19. Why not widen block 19 instead: the next suspect, "6 generic data files" in `.claude/hooks/`, depends on whether `hooks.json` counts as a data file. The folder holds six `.json` files, but `hooks.json` has its own tree line, which leaves five. That is a counting rule to decide, not a fact to correct, so it goes to the follow-up stub with the tree-count pin.
- **t18 I1, the manifest descriptions** ("28 skills", 14 agents; the tree has 33 and 15). Neither block can fix them, because a sub-task never lists a version file. The landing does not fix them either, despite what block 11 says (see the Revision 9 correction there). Who fixes them is Open Question 33; the stub records it.
- **Pull request #223's description**, which t18 did not check. Dropped by decision: no gate reads it, it does not ship, and the record of what block 17 did is its commits and the t18 artefact. Block 20 lists it under What was NOT checked.

**What the t18 review recorded beyond its artefact (Open Question 29).** The t18 artefact was committed with the placeholder row `SUITES_PENDING` in Evidence and the bullet "The hook suites under `.claude/hooks/tests/`: see Evidence for what finished" under What was NOT checked. The reviewer's hand-back gave the missing rows: `test_skill_script_lookup.py` 29 OK; `test_cleanup_delivered.py` 126 OK (1 skipped); `test_pr_merged.py` 761 OK; `test_auto_improve_finish_install.py` 344 run with 5 failures (`TestLauncherFallbackNote` 1, `TestLauncherSurfaceMissingRefusal` 4), which also fail on `origin/master` and so are pre-existing; and 22 hook suites exited 0. They are recorded here. The t18 artefact is not edited: block 20's artefact supersedes it and carries the full table.

**A second hand merge is not planned.** After block 17, the parent branch's manifests equal 274bf1e's, so master's version change in 0061212 is a one-sided change and merges without a conflict. The t18 review (I2) found that master's commits after 274bf1e touch no registry, no `README.md` and no file block 17 resolved by hand. The same must hold for the two files block 17 text-fixed after the merge, `CONTRIBUTING.md` and `skills/auto-improve-finish-install/SKILL.md`. That fact is unverified by this contract (no shell), so block 19 checks it before editing, and block 20 runs `git merge-tree` against `origin/master`. If either finds an overlap, the contract is amended first, with the Revision 8 remedy pattern. The landing then merges `master` again and raises the version to **0.15.0** while `master` is on 0.14.

**Deferred (Open Question 30).** Pinning the README folder-tree counts in `test_repo_consistency.py` (F2) goes to `.claude/concepts/followups/2026-11-03-readme-tree-counts-and-step-pins.followup.md`, `**Issue:** pending`.

**Main-session actions, outside any block:**
- Fast-forward the parent worktree to `origin/feature/memory-client-and-cloud-engineering` before committing this amendment. The local branch was at fdd7640 when Revision 9 was drafted and did not yet hold #223 or #224. The amendment touches only the contract and the new stub, and neither of those merges changed them.
- Append the t18 reviewer-verdict line (t18 Disposition item 5) to `~/.claude/logs/reviewer-verdicts.jsonl`.
- Open the tracking issue for the new stub (`/design-first` Step 3.4), and the two sub-issues and briefs for blocks 19 and 20, as commit fdd7640 did for Revision 8.
- `contract-critic` ran on Revision 9 (`## Critique (Revision 9)`, warnings only). The user had its eight warnings folded in on 2026-11-03.

**Depends on:** 17

**Files to touch:**
- `skills/pr-merged/references/contract-completion.md`
- `README.md`
- `.claude/registries/JOURNAL.md`
- `.claude/scripts/tests/test_parent_branch_rule_text.py`

No version file is listed: the landing raises once (Parent Branch Delivery Rule). `JOURNAL.md` is a shipped registry, and its append rides here for the same reasons as J1-J11 in block 17.

**Pre-written TASK block:**
```
TASK: On the sub-task branch (cut from origin/feature/memory-client-and-cloud-engineering, which holds
  #223 and #224), fix the t18 review's B1 and W1, fix the step 5a test's end marker, pin the step order,
  and append the journal entry J12. One commit.
  Pre-check (before any edit):
  - git fetch origin, then git diff --name-only 274bf1e origin/master, and quote the output (274bf1e is
    the master commit block 17 merged). Stop list: any file in Files to touch; JOURNAL.md, MECHANISMS.md,
    VOCABULARY.md; CONTRIBUTING.md and skills/auto-improve-finish-install/SKILL.md (block 17 text-fixed
    them after the merge). If the output lists a file on the stop list, stop and report it, editing
    nothing: the contract must be amended first (a second hand merge may be needed).
  B1, skills/pr-merged/references/contract-completion.md, section "The records pull request":
  - Delete the four lines of the first steps 6-9 that follow step 5a. Locate them by text, not by line
    number: they start with "6. **Cut the branch in a flat worktree.**", "7. **Copy exactly that union
    of `written_files` there**", "8. **Open a draft pull request**" (the FIRST such line, the one
    without "when no open pull request has") and "9. **Remove the records worktree.** Then name the
    copies left in the starting tree". Delete nothing else.
  - Afterwards: the section's top-level steps read 1, 2, 3, 4, 5, 5a, 6, 7, 8, 9, each exactly once and
    in that order. Steps 6-9 equal master's, judged by git's view, never by raw bytes on disk (journal
    2026-10-17; this worktree is Windows and line ends differ):
    git diff 274bf1e -- skills/pr-merged/references/contract-completion.md shows no added or removed
    line that starts with "6. **", "7. **", "8. **" or "9. **". Every line that diff does show belongs
    to this contract's side (step 5a, its sub-steps and code block, and the capture-question sentences
    in the records-step paragraph and the "Under /flow" paragraph). The commit's own diff
    (git diff HEAD~1 -- <same path>) removes exactly the four lines above and adds none. The phrase
    "Cut the branch in a flat worktree" appears nowhere in the file.
  W1, README.md, the folder tree (the block that lists skills/, agents/ and .claude/):
  - Rewrite the four counts by measuring the tree you are editing, not by copying the contract:
    "hooks/tests/" = number of test_*.py files in .claude/hooks/tests/; "scripts/" = number of .py files
    directly in .claude/scripts/ not starting with "_" (workflow scripts) and number starting with "_"
    (shared helper modules); "scripts/tests/" = number of test_*.py files in .claude/scripts/tests/
    (keep ", including the path-resolution suite"); "references/" = number of files in
    .claude/references/. On 2026-11-03 these measured 23; 23 and 3; 36; 3. If your measurement
    differs, write yours and say so in the hand-back. Change no other README line, including the
    tree's other counts (such as "6 generic data files"): they go to the follow-up stub.
  Test, .claude/scripts/tests/test_parent_branch_rule_text.py, class CaptureAtDeliveryTextTests:
  - In the step 5a test, change the section end heading from "6. **Cut the branch" to
    "6. **Put the stable branch". Change none of its assertions.
  - Add one module-level pure function, records_step_labels(text), which takes the file's text (a
    string, not a path) and returns the labels of the top-level steps in the section that starts at the
    line "### The records pull request" and ends at the next line starting "### ", in file order. It
    works on the raw text, line by line, and NEVER through squash, flat or section: those squash all
    whitespace, newlines included, and would merge step 5a's own sub-steps into the list. A top-level
    step is a line matching ^(\d+a?)\. \*\* in column 0 (no leading space). Step 5a's six sub-steps
    ("   1. **Read the candidates" to "   6. **No outcome of this step", after the code block) are
    indented by three spaces, so they are excluded; so is anything inside the ``` code block. Normalise
    "\r\n" to "\n" before splitting.
  - Add the step-order test in CaptureAtDeliveryTextTests: records_step_labels(self.read(self.CC))
    equals ["1", "2", "3", "4", "5", "5a", "6", "7", "8", "9"].
  - Add a control test that calls the same function on a short fixture string held in the test: a
    copy of the section's shape with a planted second "6. **" line is reported (the list is not equal),
    and the same fixture with an indented "   1. **" sub-step is NOT counted. A comment says the
    function takes text so that a reviewer can run it on a git show copy of an older file.
  - Run the function on the pre-fix file and quote the result. In PowerShell, from the worktree root:
    git show HEAD~1:skills/pr-merged/references/contract-completion.md | py -3 -I -c "import sys; sys.path.insert(0, '.claude/scripts/tests'); import test_parent_branch_rule_text as t; print(t.records_step_labels(sys.stdin.read()))"
    The pre-fix result lists 6, 7, 8 and 9 twice; the same command with HEAD lists each once.
  J12, .claude/registries/JOURNAL.md:
  - Append after the last entry (J11, "A \"fails the build\" claim must name the workflow that runs the
    check") and before the closing "---" and comment, verbatim from the t18 artefact's Disposition
    item 4:
    ### 2026-11-03 — When resolving a conflict hunk by keeping both sides, drop the base lines the other side rewrote
    - **Trigger:** post-impl divergence
    - **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
    - **Lesson:** Before keeping both sides of a conflict hunk, diff each side against the merge base; lines one side left unchanged and the other side rewrote belong to the rewrite only, or the merge restores deleted text beside its replacement.
    - **Apply when:** a merge resolves a prose or procedure conflict "keeping both behaviours", especially numbered steps
    - **Tags:** merge, conflict-resolution, base-text, duplicate-steps
CONTEXT: concept contract, block 19 (Revision 9 note); the t18 review
  .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t18-review-merge-and-text-fixes-fullstack-code-reviewer.md
  (B1, W1, Disposition items 1, 2 and 4).
FILES: as listed.
CONSTRAINTS:
  - Edit only the four files listed. Do not edit the t18 review artefact or its .gate.json (Open
    Question 29). Do not edit MECHANISMS.md or VOCABULARY.md (the t18 review owes no append there).
  - Never edit plugin.json, .claude-plugin/plugin.json, .cursor-plugin/plugin.json or
    .claude-plugin/marketplace.json. The branch keeps 0.14.2; the landing raises once.
  - Registry text names no memory tool literally.
  - Run, and report the exit code and case count of: test_parent_branch_rule_text.py,
    test_skill_script_lookup.py, test_cleanup_delivered.py, test_pr_merged.py (on its own),
    test_registry_entries.py, test_repo_consistency.py, test_plugin_text_scans.py,
    test_plugin_manifests.py (one failure, "the version obeys the merge-base rule", is by design on a
    parent branch, as the t10 and t18 reviews recorded), and
    py -3 .claude/scripts/check_version_bump.py --base origin/feature/memory-client-and-cloud-engineering
    --default-branch master --head-ref <this branch>. Report the pre-fix and head output of the
    records_step_labels command above. A failure
    that also fails on origin/master is reported as such, with the origin/master run quoted, and is not
    fixed here.
  - Every command in a form that runs in PowerShell.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

### 20. Re-review merge fix (`fullstack-code-reviewer`)

**Depends on:** 17, 19

**Files to touch:**
- `.claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t20-re-review-merge-fix-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review blocks 17 and 19 together and write the review artefact. This review supersedes the block
  18 review (t18-review-merge-and-text-fixes-fullstack-code-reviewer.md).
CONTEXT: concept contract at .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  (Revision 9, block 19; Revision 8, block 17)
FILES: .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t20-re-review-merge-fix-fullstack-code-reviewer.md
CONSTRAINTS:
  - Start from a cold context. Do not read the t18 review before forming your own findings. Read it
    afterwards only to confirm B1 and W1 are cleared. Name base..head: the parent tip before block 17's
    merge (fdd7640) and block 19's head; name block 19's own range separately.
  - Block 17 again, on the current tree, judged by git blob ids, not bytes on disk: the checks of block
    18's CONSTRAINTS (registries, conflict markers, files outside block 17's Files to touch, no name
    defined twice). Block 19 adds to these checks exactly: one file outside block 17's Files to touch,
    .claude/scripts/tests/test_parent_branch_rule_text.py; and, inside block 17's Files to touch, the
    four-line deletion in contract-completion.md, the four README count lines and one appended JOURNAL.md
    entry. MECHANISMS.md and VOCABULARY.md are unchanged by block 19.
  - B1: in skills/pr-merged/references/contract-completion.md, section "The records pull request", the
    top-level steps (column 0; step 5a's indented sub-steps 1-6 are not top-level) read 1, 2, 3, 4, 5,
    5a, 6, 7, 8, 9, once each and in order. Steps 6-9 equal master's by git's view, never by raw bytes
    on disk (journal 2026-10-17): git diff 274bf1e <block 19 head> -- <path> shows no added or removed
    line that starts with "6. **", "7. **", "8. **" or "9. **", and every line it does show belongs to
    this contract's side. Step 5a is unchanged (git diff <block 19 base> <block 19 head> -- <path>
    removes exactly the four old step lines and adds none). "Cut the branch in a flat worktree"
    appears nowhere. Then read skills/flow/SKILL.md and skills/pr-merged/SKILL.md end to end for any
    other base text restored beside its rewrite (the t18 review did not), and report what you find.
  - W1: the four counts block 19 may change ("hooks/tests/", "scripts/" workflow scripts and helper
    modules, "scripts/tests/", "references/") are true against the tree, measured by you with block 19's
    counting rules. No other README line changed. Any other tree count you find false (such as "6
    generic data files", which depends on whether hooks.json counts) is reported as information and
    pointed at the follow-up stub, never as a finding against block 19.
  - Test: the step 5a test's section ends at "6. **Put the stable branch"; its assertions are
    unchanged. records_step_labels(text) is a module-level function that takes text, reads raw lines
    (not squash, flat or section) and counts only column-0 steps. The step-order test and the control
    exist and pass on head. Show the test fails on the pre-fix file by running, in PowerShell from the
    worktree root, with <block 19 base> = the parent tip block 19 was cut from:
    git show <block 19 base>:skills/pr-merged/references/contract-completion.md | py -3 -I -c "import sys; sys.path.insert(0, '.claude/scripts/tests'); import test_parent_branch_rule_text as t; print(t.records_step_labels(sys.stdin.read()))"
    Quote both outputs: the base lists 6, 7, 8 and 9 twice, so the step-order test's equality fails
    there; the same command with <block 19 head> lists each once.
  - J12: one entry appended after J11, before the closing lines, verbatim as block 19 states. No other
    registry line changed.
  - Scope: block 19's commits touch only its four files, plus the usual Work Item Brief bookkeeping
    commit (the t19 brief's front matter: pr:, issue_link:, status:), which is not a shipped file and is
    reported as a note, as t18 did for 4707150. Any other path is a finding. The t18 artefact and its
    .gate.json are unchanged since #224 (git diff on them is empty).
  - Not checked, by decision: the description of pull request #223 (no gate reads it and it does not
    ship). List it under What was NOT checked.
  - Second merge: run git fetch origin, then git merge-tree --write-tree --name-only <block 19 head>
    origin/master, and quote it. Report whether the landing's merge conflicts, and on which files.
  - Re-run, each as its own row with exit code and case count: test_pr_merged.py (alone); every
    .claude/hooks/tests/test_*.py except test_gate_cost.py, one row per suite; test_plugin_text_scans.py,
    test_registry_entries.py, test_repo_consistency.py, test_memory_boundary.py,
    test_memory_off_parity.py, test_plugin_manifests.py, test_auto_improve_finish_install.py,
    test_check_version_bump.py, test_parent_branch_rule_text.py, test_skill_script_lookup.py,
    test_cleanup_delivered.py; and the parent-mode version check. A failure that also fails on
    origin/master is reported as pre-existing, with the origin/master run quoted. No placeholder row:
    a suite that could not finish gets a row saying so, and that is a finding.
  - Six fixed sections; the file does not exist yet and you create it. The Scope section says
    "Supersedes: t18-review-merge-and-text-fixes-fullstack-code-reviewer.md". Verdict line alone,
    exactly one of: "**Verdict:** pass", "**Verdict:** pass-with-findings", "**Verdict:** blocked".
    Write the Gate Output <artefact stem>.gate.json beside it, and set its supersedes field to
    ["t18-review-merge-and-text-fixes-fullstack-code-reviewer.md"]. Do NOT edit the t18 artefact and do
    NOT append to any registry yourself: report a missing append as a finding.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
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

---

## Appendix A — Read-only audit (2026-11-01, worktree at `master` 6d1ca0c)

### A.1 Architecture in one paragraph
The plugin is a **contract-driven delivery chain**. Skills run in the main session: `/task` writes the brief, `/design-first` gets a contract and is the human gate, `/tdd-first`, the reviewers, `/verify-before-done`, `/git-commit` and `/ship` follow, and `/flow` runs the whole chain. Multi-block contracts loop through `/advance` and `/pr-merged`. 14 **agents** do the design, implementation and review work, each with a fixed `tools:` line. 13 **hook rows** (`.claude/hooks/hooks.json`) enforce the rules. **Scripts** in `.claude/scripts/` hold every deterministic rule, and the skills find them through a pinned lookup block. **Registries** (`MECHANISMS`, `VOCABULARY`, `JOURNAL`) carry design knowledge in two tiers. The **project profile** carries every project fact. Add-ons (`.claude/addons/`) ship opt-in hooks and documents.

### A.2 Components: responsibility, state, keep or change

| Component | Responsibility | Works | Missing / defect | Verdict |
|---|---|---|---|---|
| Delivery skills (`task`, `design-first`, `flow`, `advance`, `pr-merged`, `ship`, `verify-before-done`, `git-commit`, `tdd-first`) | the chain | yes; heavily tested by the scripts behind them | `/task` Step 1.5 duplicated; obsolete Step 5c; `/flow` Step 2.7 always loaded (Appendix B) | keep; two call sites added here (`/design-first` Step 1.5; the `/pr-merged` / `/flow` Step 8 confirmation); `/task` untouched; cleanup by stub |
| Design support (`contract-critic`, `critique-now`, `contract-accuracy`, `cross-impact`, `list-contracts`, `validate-registries`, `plan-questions`) | critique, accuracy streaks, inventory | yes | the area map is empty, so the accuracy skip and the cross-area scan never signal | keep |
| Knowledge skills (`journal-add`, `north-star`, `north-star-review`, `promote-ui-rule`) | write registry and north-star knowledge | yes | no external exchange | unchanged (no capture from `/journal-add` in v1) |
| Domain skills (`sql-server-patterns`, `unit-testing`, `angular-ui-rules`, `website-design`, `application-design`, `debug`) | patterns | yes | `debug` routes to three unshipped agents | keep; one route fixed |
| Install skills (`auto-improve-*`) | finish install, add-ons | yes | none found | unchanged |
| Agents (14) | design, implement, review | yes | none for cloud; `ingestion-data-architect` is cited in the template and by data-architect but not shipped | add `cloud-engineer` |
| Hooks | gates (concept, main checkout, merge direction, architecture, two database guards), trackers, advisor, pager, session-start agreements | yes; fail directions documented | `memory-pager.py` runs every Stop with no shipped `memory-blocks.json` | unchanged |
| Scripts | every rule (`pr_merged`, `land_contract`, `cleanup_delivered`, `flat_worktree`, `merge_direction`, `check_version_bump`, `plugin_doctor`, finish install) | yes; 30+ test files | none blocking | `memory_boundary.py` added |
| Registries | design knowledge, two tiers | yes | the digest, the per-domain files and `INTEGRATION.md` the agents cite do not exist here | unchanged |
| Project profile | project facts | yes; one reader (`load_slot`) | no memory or cloud slots | nine slots |
| `work-item-conventions.json` | tracker conventions, landing verification steps | yes | none | reused for cloud validation |
| Agent memory (`memory:` frontmatter, `.claude/agent-memory/`) | per-agent private notes | yes | uncontrolled provenance; `memory: user` crosses projects | **unchanged; never a capture source** |
| Memory pager (`memory-pager.py`, `_memory_common.py`) | always-on file budget proposals | fail-open | config usually absent; `memory-health.py` cited but not shipped | unchanged; name disambiguated |
| North-stars | long-horizon direction | yes | none active here | unchanged |
| MCP integrations | CodeGraph (add-on), tracker MCPs found by pattern in `/task` 1c | yes | no memory or cloud client | adapter added |
| Validation, recovery, reporting | land runner, doctor `--drift`, Gate Output, delivery cleanup, error log | yes | none for this scope | reused |

### A.3 Existing memory-like mechanisms, and whether each is touched
1. **Registries plus journal**: the knowledge base. They supply capture candidates and set precedence. Their content is not changed.
2. **Work Item Brief**: the per-task record. It gains `## Memory used`.
3. **Contract `## Lessons referenced` and `## Uncertain Assumptions`**: what shaped a design (a new line format), and the source of `ai-hypothesis` provenance (not captured).
4. **Agent memory**: untouched.
5. **Memory pager**: untouched.
6. **Working agreements (session start)**: gain one shipped agreement in Revision 7 (block 15), a fixed rule to use the Project history record; still never a channel for Central Memory System items.
7. **North-stars and follow-up stubs**: follow-up stubs are the only "proposed work item" channel.
8. **Accuracy ledger** (`accuracy_update.py`): untouched.

### A.4 Context loading today
At session start the host loads every skill and agent description. `working-agreements.py` adds up to 9,500 characters. The global and project `CLAUDE.md` files load. A skill body loads on invocation, and `references/` files only when a step says so. Subagents get a cold context plus PRIOR_FINDINGS. Memory retrieval follows the "on invocation, only when it applies" path.

### A.5 What could conflict
- The word **memory** has three existing meanings. The vocabulary fixes this (Business Concept).
- **Plugin sync vs global capture.** The Universal tier already travels to other projects through the plugin. Capturing the same entry as `global` creates a second channel, so the memory system must dedupe by source ref. That is out of our control and documented.
- **Project-name leakage** into global memory is handled by the project-name check.
- **Subagent tool lines** cannot name project-chosen servers, which is why calls stay in the main session.
- **Cursor and Codex** have no hooks and may name MCP tools differently. The boundary uses no hook, but the tool id form is Claude Code's; documented as a limitation.
- **Database guards vs cloud database deletes.** The guards match SQL and EF forms, not `az sql db delete` or `aws rds delete-db-instance`. The permissions rows close that gap without touching the guards.

### A.6 Cloud engineering coverage today

| Area | Today | After this contract |
|---|---|---|
| Azure, AWS, GCP | none | provider references, selected per profile |
| Terraform, Bicep | none | references, validation steps (`terraform validate` / `plan`, `bicep build` / `what-if`) |
| Docker | one line in `python-ai-developer`; `debug` routes to an unshipped agent | reference; routed to `cloud-engineer` |
| Kubernetes | none | reference; server-side dry-run and schema validation |
| Networking, IAM, secrets, messaging, storage, observability, cost, governance | secrets only, in `security-auditor` (config files) | cross-cutting reference plus auditor checklist |
| Deployment validation | none for infrastructure | land runner steps, non-mutating |
| Troubleshooting | generic `/debug` | cross-cutting procedure |
| Deploy and destructive operations | database guards only | unchanged guards and the user's normal permission prompts; the skill and agent hand live-changing commands to the user (no new mechanism) |
| Cloud-management MCP | none | slot only (deferred) |

---

## Appendix B — Context and token efficiency (estimated at four characters per token)

1. **`/task` Step 1.5 is written twice** (`skills/task/SKILL.md:104-118` and `120-134`). That is about 700 wasted tokens per intake.
2. **`/task` Step 5c** (`:446-521`, about 1,800 tokens) describes creation steps the skill says are no longer run.
3. **`/flow` Step 2.7** (`:114-334`, about 5,000 tokens) loads for every run, including single-block contracts. It could move to `references/`.
4. **The script lookup block** (about 450 tokens) is copied 10+ times across skills (three in `advance`, three in `flow`). Its copies are pinned by `test_skill_script_lookup.py`. It is correct but heavy; leave it unless one shared reference can be tested the same way.
5. **Always-loaded descriptions.** 32 skill and 14 agent descriptions load every session. The longest (`task`, about 1,000 characters; `data-architect` and the reviewers carry examples) could be shortened without losing their trigger phrases.
6. **The concept template** is about 8,000 tokens and loads on every design. Its Chat Tool Impact section belongs to one consuming project.
7. **Hook processes.** Per edit: three sync processes plus one async. Per shell command: three sync. Per prompt: one. Per Stop: one sync plus one async (the pager, which usually only logs a failure). The gates must stay as command hooks because they fail closed. Only the pager is a cheap win.
8. **Flow vs task duplication** is small: `/flow` repeats the design handoff block that `/task` Step 6 already writes, and it states that the stage skill wins.
9. **This contract adds**: zero always-loaded tokens for Central Memory System items (no new skill; the procedure lives in a reference read only when enabled). Revision 7's shipped agreement adds about 100 always-loaded tokens (about 400 characters) at session start, inside the agreements' 9,000-character limit. The cloud skill adds one description, about 60 tokens. The cloud agent adds one description. The disabled memory path costs one silent script call per design and writes nothing.

---

## Appendix C — Prioritised plan

| Priority | Change | Blocks | Depends on | Risk | Validation criterion |
|---|---|---|---|---|---|
| P1 | Slots plus the adapter, with degradation and single-adapter tests | 1, 2 | none | wrong tool-id assumption | `test_memory_boundary.py` passes; scan control fails when planted; all existing suites pass |
| P2 | Retrieval at design time, applicability asked before the draft, recorded in the brief | 3 | P1 | prompt injection via items; a hung server | the stub-server trials (tool id, a server that never answers); `test_memory_off_parity.py` shows memory-off briefs byte-identical and `/task`'s template hash unchanged |
| P3 | Capture as its own question after the writing run flips | 4 | P2 | over-capture, leakage, lost receipts, a hung server | only contract-named entries offered; an empty token list lowers everything; receipts reach the records pull request; exactly one capture question, asked after the flip, under `/pr-merged` and `/flow`; the records confirmation is unchanged; the stop rule caps a hung server at one timeout |
| P4 | Memory review gate | 5 | P1-P3 | none | verdict pass (block 5 recorded `blocked`; superseded by P4b) |
| P4b | Memory-boundary review fixes, the Project history record in onboarding, Step 1.5 and a shipped agreement, and their re-review (Revision 7) | 14, 15, 16 | P1-P3 | weakening I-M0 while fixing B1; `--fix` writing more than the user expected | the three I-M0 disabled tests unchanged and passing; finish-install asks before `--fix`; `test_working_agreements.py` passes with seven files; block 16 verdict pass |
| P5 | Cloud skill and references | 6 | 1 | stale provider facts; a live-changing command run by mistake | references load only for the selected providers; the scope rule is stated; `test_cloud_text_scans.py` control fails when planted |
| P6 | Cloud agent, auditor checklist, debug route | 7 | P5 | agent overreach | agent refuses when the slot is unset; the scope rule is stated and passes the text scan; preload test passes |
| P7 | Cloud review gate | 8 | P5-P6 | none | verdict pass (block 8 recorded `blocked`; superseded by P7b) |
| P7b | Cloud agent skill-load fix and its re-review (Revision 6) | 12, 13 | P6 | none | block 13 verdict pass |
| P8 | Documentation, registry appends and their review | 9, 10 | P4b, P7b (blocks 13, 14, 15, 16) | documentation that disagrees with the code | reviewer checks each claim against the code |
| P9 | Merge `master` into the parent branch by hand, the t10 text fixes and the W2 journal entries, and their review (Revision 8) | 17, 18 | P8 | dropping an entry of either side while resolving a registry | every entry of both sides present once; block 18 verdict pass (recorded `blocked`; superseded by P10); the landing reruns clean |
| P10 | Delete the restored base steps 6-9, correct four README tree counts, pin the step order, append J12, and the re-review (Revision 9) | 19, 20 | P9 | widening the step 5a test by deleting its end marker; a later `master` commit touching the same files | steps 1-9 and 5a once each, steps 6-9 identical to 274bf1e; block 20 verdict pass and its Gate Output supersedes t18; the landing passes P3 |
| Later | Token-efficiency fixes; cloud-management MCP adapter | follow-up stub; a new contract | none | none | separate contracts |

---

## Critique (Revision 7)

**Critic:** contract-critic
**Date:** 2026-11-02
**Verdict:** blockers-found
**Scope:** Revision 7 only (the Revision 7 note under Handoff 11, blocks 14-16, the Depends on lines of blocks 9 and 10, the `record` and `changed-items` Commands rows, Trigger matching, the Candidate reading entry end, the two Extension Points bullets, the term "Project memory" and the Reused Mechanisms row). Checked against the t5 review and the user's Project memory requirement.

### Findings

- **[BLOCKER] Status stays `approved` while Open Questions 22 and 23 are open, and block 15 leaves the implementer to apply whatever the user answers.**
  - **What is wrong:** questions 22 and 23 are unticked, but the body, the Reused Mechanisms row and block 15's TASK already assume the recommended answers. Block 15's constraint "If they differ from the recommendations, the user's answer wins" hands any change to the implementer, and `concept-gate.py` reads only `Status: approved`, so block 15 can be dispatched before the questions are answered.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-22, "An accepted critic WARN or answered Open Question must amend the contract body before approval".
  - **Where in this contract:** `## Open Questions for User`, "Revision 7 adds two questions. Answering them is the user's re-approval of Revision 7."; `### 15`, "Apply the answers the user gave to Open Questions 22 and 23. If they differ from the recommendations, the user's answer wins."
  - → Addressed by: Open Questions 22 and 23 ticked with the user's answers (2026-11-02) and `→ Addressed by:` lines; the answers written into Business Concept, Extension Points, Failure Modes and block 15's TASK; the "user's answer wins" constraint removed from block 15.

- **[WARN] The Project memory instruction reaches only two places, onboarding and non-trivial design, and the plugin's existing channel for standing guidance is not used or considered.**
  - **What is wrong:** the user asked that the plugin tell host repositories to use their file-based memory. Block 15 puts the instruction in `/auto-improve-finish-install` (run once, and never by a plugin install that skips it) and in `/design-first` Step 1.5 (non-trivial tasks only). The XS/S direct edit, `/debug`, `/journal-add` and every session that never designs get no instruction. The shipped agreements folder already delivers standing guidance to every session in every plugin-installed host. `## Alternatives Considered` has no Revision 7 entry that weighs it.
  - **Prior artifact ignored:** `MECHANISMS.md:65` **Session-start context delivery** ("the way the plugin hands standing guidance to the model once per session start"; "Extend by: adding a markdown file to the plugin's folder"); `.claude/agreements/` holds six shipped agreements today.
  - **Where in this contract:** `## Reused Mechanisms`, "Telling a host project that its registries and contracts are its memory (Revision 7) | ... the `/auto-improve-finish-install` skill and the Step 1.5 printed line, extended by text only".
  - → Addressed by: user answer "Yes, add a session-start agreement". Block 15 adds `.claude/agreements/use-the-project-history-record.md` and updates `.claude/hooks/tests/test_working_agreements.py` (`REQUIRED`, `SHIPPED_PHRASES`); Reused Mechanisms row now names Session-start context delivery; Alternatives Considered Options I, J and K; Extension Points bullet "Shipped agreements"; block 9 updates the README agreement count.

- **[WARN] Block 15's shipped text says the contract-critic and the other roles "append to them on every run". That is false.**
  - **What is wrong:** the contract-critic never appends to a registry. `/design-first` Step 5 appends confirmed findings, and the reviewer appends only on a divergence. The data-architect appends only after approval. The finish-install text would describe behaviour the agents do not have.
  - **Prior artifact ignored:** `agents/contract-critic.md:150` ("Append entries to `JOURNAL.md` ... Never by you"); `JOURNAL.md:5-8` ("Maintained by"); `JOURNAL.md` 2026-10-04, "Check a documented guard behaviour against the guard's code".
  - **Where in this contract:** `### 15`, TASK point 1, "/design-first, the data-architect, the contract-critic and the reviewer read them and append to them on every run."
  - → Addressed by: block 15 TASK point 1 now names who appends and when (`/design-first` Steps 3 and 5 for confirmed critic findings, `fullstack-code-reviewer` on a justified divergence and as janitor, `/journal-add` manually; the contract-critic reads and never appends) and forbids "on every run"; block 15 point 4 pins it; block 16 checks it.

- **[WARN] The definition of "Project memory" makes a universal claim that some existing flows contradict.**
  - **What is wrong:** "the memory every plugin flow reads and appends to, in every memory state" is false for the routes the contract's own route table lists as having no design step (XS/S direct edit, `/debug`), and for `/git-commit` and `/ship`. This text goes into `VOCABULARY.md` through block 9.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-28, "A new term's definition must be true against every existing member"; this contract's `## Extension Points` route table, row "XS/S direct edit or `/debug` | none (no design step ...)".
  - **Where in this contract:** `## Business Concept`, "**Project memory** *(Revision 7)* — ... It is the memory every plugin flow reads and appends to, in every memory state."
  - → Addressed by: the Business Concept term (now **Project history record**) says `/design-first` and the data-architect read it, names the confirmed steps that append, and states that XS/S direct edits, `/debug`, `/git-commit` and `/ship` neither read nor append it; block 9 and block 10 require the documentation to match.

- **[WARN] The term "Project memory" is already used for something else in this repository.**
  - **What is wrong:** eight plugin agents declare `memory: project`, which selects the project-scope agent-memory folder under `.claude/agent-memory/`. The definition has to add "It is not agent memory" because the same words already name that folder. The host's own documentation also uses "project memory" for the project's CLAUDE.md file. So `VOCABULARY.md` would gain a term that means a third thing.
  - **Prior artifact ignored:** this contract's `## Uncertain Assumptions`, "`VERIFIED via agents/*.md frontmatter`: ... eight declare `memory: project`"; the *Central Memory System* term in this contract, which was defined against "the three existing 'memory' things" (`## Lessons referenced`, 2026-10-28).
  - **Where in this contract:** `## Business Concept`, "New terms proposed", **Project memory**.
  - → Addressed by: the user renamed the term to **Project history record** (2026-11-02) everywhere in Revision 7 outside the critique sections; the definition keeps one line distinguishing it from `memory: project` agent memory. The shipped agreement still calls the registries and contracts "the project's memory" in plain words, at the user's instruction.

- **[WARN] The contract understates what `plugin_doctor.py --fix` does, and block 15 runs it without the confirmation the finish-install skill promises.**
  - **What is wrong:** `--fix` creates every missing requirement, not only the memory seeds. That includes `.claude/north-stars`, `.claude/orchestrator/results`, the contract template, and the scaffolds `area-mapping.json` and `work-item-conventions.json`. Block 15 triggers it whenever one memory file is missing, in a project that already has a profile. That is a wider case than Stage 1a's "no profile yet", and no question is asked first.
  - **Prior artifact ignored:** `.claude/scripts/plugin_doctor.py:58-87` (`REQUIREMENTS`) and `:200-244` (`apply_fixes` writes every missing entry); `skills/auto-improve-finish-install/SKILL.md:12` ("It proposes, you confirm, and only then does it write").
  - **Where in this contract:** `## Extension Points`, "runs `plugin_doctor.py --fix`, which copies the plugin's seeds and never overwrites"; `### 15`, TASK point 1, "run ... --fix, which copies the plugin's seed files and never overwrites (as Stage 1a)".
  - → Addressed by: user answer to Open Question 23, "Report, then ask before --fix". Extension Points bullet `/auto-improve-finish-install` and block 15 TASK point 1 describe `--fix` from `REQUIREMENTS` and `apply_fixes` (every missing requirement, including north-stars, orchestrator results, the contract template and both scaffolds) and run it only after the user confirms the listed set; Failure Modes entry "`--fix` creates more than the user expected".

- **[WARN] Block 14 tells the implementer to change three tests that check the disabled state, not the unconfigured state.**
  - **What is wrong:** `test_memory_boundary.py:747` and `:865` use an empty profile or none at all, and `:754` uses an outcome that says `disabled`. All three guard I-M0 and must stay unchanged after B1. The only test that misstates unconfigured coverage is `:796`, which the TASK already splits. The constraint invites the implementer to weaken the I-M0 refusals.
  - **Prior artifact ignored:** `.claude/scripts/tests/test_memory_boundary.py:742-755` (`test_disabled_refuses_not_enabled_and_writes_nothing`, `test_an_outcome_that_says_disabled_writes_nothing`) and `:861-865`; the t5 review B1 fix, item 1 ("refuse `not-enabled` only when ... `disabled`").
  - **Where in this contract:** `### 14`, CONSTRAINTS, "Where an existing test asserts that record refuses under unconfigured (for example around test_memory_boundary.py:747, :754, :865), change it to the new behaviour".
  - → Addressed by: block 14 CONSTRAINTS now forbid changing the three I-M0 tests, named with their verified lines (:742-748, :750-755, :860-866), and name `:796` as the only test to change (the split).

- **[WARN] On the unconfigured path, nothing says which brief `record` writes to, so a design run with no brief turns into a reported failure.**
  - **What is wrong:** the rewritten point 3 calls `record`, which needs `--brief`, but the rule for finding the brief ("the one whose `branch:` is the branch you are on") sits only in point 4, the enabled path. On the route "/design-first run directly", `record` refuses `brief-not-found`. The new text says "a refusal or non-zero exit from record here is a failure under point 2", so a normal case prints a failure line.
  - **Prior artifact ignored:** `skills/design-first/SKILL.md:79` (brief resolution, enabled only); this contract's route table row "`/design-first` run directly | Step 1.5".
  - **Where in this contract:** `### 14`, B1, "record it with record (outcome {"state": "unconfigured", ...}), then go to Step 2; a refusal or non-zero exit from record here is a failure under point 2."
  - → Addressed by: block 14 B1 and Extension Points Step 1.5 point 3 now pick the brief by point 4's rule (the brief whose `branch:` is the current branch); a missing brief prints one skipped-for-want-of-a-brief line and design continues, which is not a failure; only a refusal when a brief was found falls to point 2. Failure Modes entry on `record` under `unconfigured`.

- **[WARN] The I2 fix relies on a reader that ignores `--project` and still falls back to `master`.**
  - **What is wrong:** with `default_branch_name=None`, `select_linked_brief` calls `default_branch()`. That reads `origin/HEAD` in the process's working directory, not in the `--project` root, and answers `master` when the value cannot be read. A `main` project whose `origin/HEAD` is unset still gets the hard-coded name. The TASK's "reuse its function" does not say to pass `cwd=<project>` through `default_branch_or_none`.
  - **Prior artifact ignored:** `.claude/scripts/pr_merged.py:2364-2381` and `:3016`; `JOURNAL.md` 2026-10-15, "A script that reads a project-owned file must be told which project, not search for one".
  - **Where in this contract:** `### 14`, I2, "When it is None, resolve the default branch the way pr_merged does (reuse its function; do not hard-code a name)."
  - → Addressed by: block 14 I2 now binds `pr_merged.default_branch_or_none` and calls it with `cwd=<--project root>` (verified `pr_merged.py:2364-2377`), never `default_branch()` (`:2380-2381`, the `master` fallback), and never passes None into `select_linked_brief` (`:3016`). When it cannot read `origin/HEAD`, `capture-candidates` refuses the new `default-branch-unknown` before offering anything (Commands row amended). Tests cover a `main` project run from another directory, the unreadable case and an explicit flag.

- **[WARN] Failure Modes has no entry for anything Revision 7 adds.**
  - **What is wrong:** three new failure paths have no mitigation. The doctor can fail to find the plugin root ("NOT FOUND - pass --plugin"), which leaves the copy requirements `unresolved` while finish-install goes on. `record` can refuse under `unconfigured`. And `--fix` can create files nobody expected (finding above).
  - **Prior artifact ignored:** `.claude/scripts/plugin_doctor.py:993` and `:226-230`; the checklist rule that every mitigation cites a mechanism.
  - **Where in this contract:** `## Failure Modes & Mitigations`, which is unchanged since Revision 5.
  - → Addressed by: three Revision 7 entries in Failure Modes (doctor `NOT FOUND - pass --plugin`; `record` refusing or no brief under `unconfigured`; `--fix` creating more than expected), each citing the plugin doctor, the brief linkage rule or the tracker-cascade degradation rule.

- **[NIT] Several summary lines are stale.** The Handoff intro still says "ten mergeable blocks" with the graph "5,8→9→10". Appendix C row P8 says "Depends on P4, P7". The header still says "**Revision:** 5". All three contradict blocks 9 and 10's new Depends on lines (13, 14, 15, 16).
  - → Addressed by: header now "Revision: 7"; Handoff intro gives fifteen mergeable blocks plus the scope note and the true dependency graph; Appendix C gains rows P4b and P7b, and P8 depends on them.
- **[NIT] The scope note contradicts itself.** Its first paragraph still says "No block touches ... `skills/auto-improve-finish-install/SKILL.md`", and a later Revision 7 bullet amends that instead of the sentence being edited where it stands.
  - → Addressed by: the scope note's first paragraph edited in place; the later amending bullet removed.
- **[NIT] Block 14 implements part of the new requirement.** It carries the Project memory suffix on the `status` line, although "Why two blocks" says block 14 stays limited to the review report.
  - → Addressed by: the suffix moved to block 15 as skill text appended when the line is printed, so `memory_boundary.py`'s status strings do not change and block 14 carries no Project history record text; "Why two blocks" says so.
- **[NIT] The suffix "every state" bullet is only partly delivered.** The point 2 failure line and the point 4 "skipped for want of a brief" line get no "design continues from the project memory" suffix, although the Extension Points bullet is titled "in every state".
  - → Addressed by: Extension Points bullet and block 15 TASK point 2 put the suffix on every printed line of Step 1.5 (points 2, 3 and 4) and the reference's `unavailable` lines; block 15 point 4 pins it.
- **[NIT] The contract is over its budget rule.** Three superseded critique rounds and the appendices are still inline, against the template's budget rule (`.claude/templates/concept-contract.md:22`) and the answer to Open Question 14.
  - → Deferred: at the user's instruction this amendment notes it only and trims nothing (scope note, "Budget"). Moving the old rounds and appendices to `.claude/contract-history/` is still owed.

### What Revision 7 gets right (checked, no finding)

- **The t5 findings are covered.** B1 (record writes the unconfigured line with the reason from the profile, refuses only `disabled`, `--receipts` still needs `enabled`, the "is expected" sentence is deleted, the test is split, a parity variant is added), W1 (one shared source_ref helper, plus a test on the real `capture-candidates` output), W2 (a normalised file, the same function, string versions) and W3 (an exact canonical match, with both compound strings tested) match the review's fixes. I1 and I2 ride with block 14, and I2 has the caveat above. I3 is carried into block 9's Known limitations and checked by block 10. Disposition items 5 and 6 land in block 9.
- **Pins hold.** INV-14 skips any line that names `plugin_doctor` (`test_plugin_manifests.py:503`), and block 15 keeps the doctor commands on such lines. INV-13 checks only frontmatter. The Step15TextTests searches (`unconfigured.{0,300}one line`, `disabled.{0,300}print(s)? nothing...`) still match the rewritten point 3 and an appended sentence. `test_skill_script_lookup.py` cuts only fenced blocks that hold the plugin-cache search line, and the doctor commands carry none. `SENTENCE_PLACEMENT` for design-first pins a Step 3 sentence that blocks 14 and 15 do not touch.
- **Ordering and file scope hold.** Blocks 9 and 10 now wait for 16, 16 waits for 14 and 15, and 15 waits for 14. No cycle. The three files 14 and 15 share are sequenced. Every shipped file the blocks change is listed. No version file appears. The registry appends ride in block 9, before the landing raise.

### Applicable journal entries

- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — violated (see the BLOCKER).
- **2026-10-28 — A new term's definition must be true against every existing member** — violated by "Project memory" (see the WARNs).
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — violated in spirit by block 15's "append to them on every run" claim (see the WARN).
- **2026-10-15 — A script that reads a project-owned file must be told which project** — not addressed by I2 (see the WARN).
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded: blocks 14 and 15 both run `test_skill_script_lookup.py`.
- **2026-10-30 — One shared reader must own the filtering** — heeded by W2 ("call the same function, do not copy it") and W1 (one source_ref helper).
- **2026-11-01 — A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for** — heeded by W3's exact-match rule and I1's entry end.
- **2026-10-05 — Neutralise every field echoed from untrusted input** — heeded: W1 sends `file` through `clean_text` and `line` through `safe_token`.

### What the critic did not check

- `pr_merged.py --contract <slug> --status --json` was not run (no shell in this session), so `layout_defects` are not cited. The check above was by reading.
- No test suite was run. Pin compatibility was judged from the test source.
- CodeGraph tools were not available in this session, so symbols were checked with Grep and Read.
- North-star alignment was not checked: `.claude/north-stars/` does not exist.

---

## Critique (Revision 8)

**Critic:** contract-critic
**Date:** 2026-11-03
**Verdict:** blockers-found
**Scope:** Revision 8 only: blocks 17 and 18, Open Questions 24-28, the Revision 8 note under Handoff 11, the header Revision line, the Handoff intro and graph, the three Revision 8 lines of `## Lessons referenced` and Appendix C row P9. Checked against `check_version_bump.py`, `land_contract.py`, `pr_merged.derive_subtask_id`, the t10 review artefact and `## Critique (Revision 7)`.

### Findings

- **[BLOCKER] Block 18's merge check fails on a file that auto-merges, and Open Question 24's recommendation would add three more failures.**
  - **What is wrong:** block 18 requires "every file the merge commit changed against the parent tip is either in block 17's Files to touch or identical to origin/master". A file that both sides changed and git auto-merges is neither. `skills/flow/SKILL.md` is one: the parent changed it in blocks 3 and 4 (this contract `:878`, `:922`), the caller's `git merge-tree` run reports it as auto-merged, and block 17 does not list it. Block 18 therefore cannot return `pass`. Open Question 24 then recommends replacing the conflict part of Files to touch with "exactly the names it prints". `--name-only` prints only the conflicted paths, so that would also drop `pr_merged.py`, `test_pr_merged.py` and `skills/pr-merged/SKILL.md`, which auto-merge, and they would fail the same check. The set block 18 needs is the conflicted files plus every file both sides changed, not the conflicted files alone.
  - **Prior artifact ignored:** this contract's blocks 3 and 4 Files to touch (`skills/flow/SKILL.md`); `JOURNAL.md` 2026-11-01, "After merging a base that changes the row shape a feature reads, re-check every coverage claim ... against the merged writer" (the merged file holds both sides' changes, so it matches neither side).
  - **Where in this contract:** `### 18`, CONSTRAINTS, "every file the merge commit changed against the parent tip is either in block 17's Files to touch or identical to origin/master"; `## Open Questions for User` 24, "replaces block 17's 'Files to touch' conflict part with exactly the names it prints".
  - → Addressed by:
    - Block 17's Files to touch now lists the five computed conflicts plus `CONTRIBUTING.md` and the finish-install skill. The text fixes change no test.
    - Block 18 judges listed files on content. Every other changed file must carry no hand edit: a master-only file (the manifests included) equals the merged master commit; an auto-merged both-sided file equals git's own `merge-tree --write-tree` result.
    - The literal "identical to origin/master" rule for auto-merged files was not used, because it fails by construction.
    - Open Question 24's recommendation was replaced by the computed answer.

- **[BLOCKER] The contract says `approved` while Open Questions 24-28 are open, and block 17's TASK leaves the answers to the implementer.**
  - **What is wrong:** this is the same defect as the Revision 7 BLOCKER. Questions 24-28 are unticked. Block 17's TASK still carries the branches the user has not chosen: "skills/auto-improve-finish-install/SKILL.md:292 (the latter only if Open Question 27 says yes)", "the entries J1-J11 the contract's block 17 still lists as confirmed", and "strike the rest here before approval". The dispatch path reads only `Status`, and that already says `approved`, so block 17 could be dispatched with the conditions still in it. `## Lessons referenced` says the 2026-10-22 lesson is "heeded in Revision 8". The TASK text says otherwise.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-22, "An accepted critic WARN or answered Open Question must amend the contract body before approval"; `## Critique (Revision 7)`, first BLOCKER (the same pattern, "the user's answer wins").
  - **Where in this contract:** `### 17`, TASK, I3 and W2 bullets; header "**Status:** approved" with "**Revision:** 8 (... needs the user's re-approval ...)".
  - → Addressed by: Open Questions 24-28 are ticked with the user's answers (2026-11-03). Block 17's TASK and notes state the final answers: I3 is fixed in both files, all of J1-J11 are appended, and "only if", "still lists as confirmed" and "strike the rest" are removed. The block 17 Revision 8 note now says the amendment awaits only the final approval.

- **[WARN] Block 17's list of suites leaves out the suites that pin the text of the files being merged.**
  - **What is wrong:** `test_parent_branch_rule_text.py` pins paragraphs in `skills/pr-merged/references/contract-completion.md` (a conflict resolved by hand) and in `skills/flow/SKILL.md` and `skills/pr-merged/SKILL.md` (auto-merged), at `:201`, `:308-315`, `:336-394`. `test_skill_script_lookup.py` and `test_cleanup_delivered.py` also read these skill files, and master's records-leftover-cleanup work (#178) changed the cleanup path. None of the three is in block 17's run list or block 18's re-run. A hand resolution that breaks a pinned sentence would pass both gates and first surface at the landing's verification.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-15, "A skill that edits a block pinned by a lookup-block test must name that test"; revision-2 critique NIT at this contract `:644`, which names `test_parent_branch_rule_text.py` as pinning these same files.
  - **Where in this contract:** `### 17`, CONSTRAINTS, "Run, and report the exit code and case count of: test_pr_merged.py ... test_check_version_bump.py".
  - → Addressed by: `test_parent_branch_rule_text.py`, `test_skill_script_lookup.py` and `test_cleanup_delivered.py` are added to block 17's required suites, noting that they read the three merged skill files. Block 18 re-runs them by name.

- **[WARN] The reasoning that clears the manifests misstates the landing code.**
  - **What is wrong:** block 17 says no `unionPaths` or `regenerators` are configured, "so every conflict is `halt`", and that paths sorting before JOURNAL.md "therefore do not conflict". Both steps are false. `versionRaise` is `true` (`.claude/work-item-conventions.json:89`), so a conflicting manifest is classed `version-fields`, not `halt` (`land_contract.py:1038-1039`). And `plugin.json` and `.cursor-plugin/plugin.json` sort after `.claude/registries/JOURNAL.md`, so the halt on JOURNAL.md does not clear them. The conclusion (no manifest conflicts) agrees with the caller's `merge-tree` run, but only by chance, and Open Question 28 relies on the same premise ("the parent side never changed a manifest").
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04, "Check a documented guard behaviour against the guard's code"; `land_contract.py:1028-1040`.
  - **Where in this contract:** `### 17`, "Conflicting files", "Cleared: every path that sorts before it. ... so every conflict is `halt` ... The manifests ... therefore do not conflict."
  - → Addressed by: the "Cleared" reasoning is removed. Block 17 now says that `versionRaise: true` makes a manifest conflict `version-fields`, and that `plugin.json` and `.cursor-plugin/plugin.json` sort after JOURNAL.md, so the P7 halt proves nothing about them. "No manifest conflict" rests only on the computed `merge-tree` result, and the Version paragraph cites that result.

- **[WARN] Revision 8 adds a hand-merge path but no failure modes and no uncertain assumption.**
  - **What is wrong:** `## Failure Modes & Mitigations` is unchanged since Revision 7. It has nothing on these failures:
    - a registry entry dropped or duplicated while resolving by hand;
    - an auto-merged script that defines a name twice or drops an import;
    - the landing halting again at P7 because `master` appended to a registry tail after block 17;
    - README counts that are wrong after the merge.
    These appear only as TASK constraints and as Appendix C's Risk cell. `## Uncertain Assumptions` also has no entry for the conflict list, which the contract itself calls derived rather than computed, or for "master (8ea2dd4, version 0.14.x)". The architect's own proposed J6 is exactly this lesson.
  - **Prior artifact ignored:** `## Critique (Revision 7)`, WARN "Failure Modes has no entry for anything Revision 7 adds" (this contract `:1800`); block 17 J6.
  - **Where in this contract:** `## Failure Modes & Mitigations` (no Revision 8 entry); `### 17`, "Conflicting files (derived ...)".
  - → Addressed by: four Revision 8 Failure Modes entries (a dropped or duplicated registry entry; a name defined twice or a dropped import in an auto-merged script; a second P7 halt when `master` moves; wrong README counts), each with a mitigation citing a mechanism; an `ASSUMED` (Revision 8) entry in Uncertain Assumptions for `master` at 8ea2dd4 with version 0.14.x; and the conflict list is now marked computed.

- **[NIT] The dependency graph list leaves out blocks 17 and 18.** The intro sentence says "graph 9,10→17→18", but the "true graph" bullets (`:760-762`) end at "9,14,15,16→10". This is the stale-summary class of proposed J7.
  - → Addressed by: the graph bullets gain "9,10→17→18 (Revision 8)".
- **[NIT] The text-fix line numbers are from before the merge.** README `:885-886` and `:903` are correct on the parent tip, but the second commit runs after merging a README that conflicts, so they will shift. The quoted replacement sentences still locate the text.
  - → Addressed by: block 17's TASK says the line numbers are from before the merge and will shift in README.md, so each sentence is located by its text. The I3 bullet quotes both old sentences.
- **[NIT] Block 17 moves the W2 append without saying so.** t10 Disposition 2 and W2's Fix put the entries "in the same commit as the landing's version raise". Block 17 appends them in a sub-task commit instead. That works, because `raise_manifests` commits only the manifests, with `--no-verify`. The contract does not state the move or the reason for it.
  - → Addressed by: block 17's "Journal entries" now states the move and the reasons. The landing halts at P7 before its raise commit exists. Entries appended after the flip are never offered for capture. `raise_manifests` commits only the manifests.

### Checked, no finding

- **Version (Open Question 28).** Parent mode (`check_version_bump.py:166-174`) allows the head's version when it matches the version at `--base` or at `merge-base(origin/master, HEAD)`. After the merge, that merge base is the merged `origin/master` tip, so 0.14.x passes for block 17 (base 0.12.4) and for block 18 (base 0.14.x). `--raise` writes `max(default) minor + 1, patch 0` (`:91-97`, `:150-157`), which is 0.15.0 while `master` is on 0.14.x, and `--exact` checks the same value. The answer is right. The worktree's `plugin.json` reads 0.12.4. No block lists a version file, and the `**Work Item Brief:**` header is present.
- **The conflicted files are covered.** All five paths the caller's `merge-tree` run reports as conflicted are in block 17's Files to touch, so the "abort if a conflict is unlisted" stop will not trip. The conflict-hand edits are all `.md`, and `concept-gate.py` allows `.md`. `merge_direction.py` judges pull requests only, not a local `git merge`.
- **Block 18's artefact name maps through `derive_subtask_id`.** `pr_merged.py:265-273` turns "Review merge and text fixes (`fullstack-code-reviewer`)" into `t18-review-merge-and-text-fixes`. The stem `t18-review-merge-and-text-fixes-fullstack-code-reviewer` follows the t10 pattern.
- **J1-J10 match the Revision 7 dispositions.** Revision 7 had 1 BLOCKER, 9 WARNs and 5 NITs. J1 (reach), J2 (term collision), J3 (`--fix`), J4 (tests), J5 (brief on unconfigured) and J6 (Failure Modes) cover the six WARNs no journal entry held. The other three WARNs re-applied 2026-10-28, 2026-10-04 and 2026-10-15, and the BLOCKER re-applied 2026-10-22, all of which exist in `JOURNAL.md`. J7-J10 cover four NITs, and the budget NIT is deferred under Open Question 14. That accounts for all 15 findings, and each lesson matches its finding's text. J11 is verbatim from t10 Disposition 7 (title, Trigger `post-impl divergence`). The J1-J10 Trigger `pre-approval critic` matches the `JOURNAL.md:5-8` "Maintained by" header.
- **The text fixes match their sources.** W1, I1/I2, I3 and I5 match the t10 Fix lines. `CONTRIBUTING.md:162`, `README.md:885`, `README.md:903` and `skills/auto-improve-finish-install/SKILL.md:292` hold the quoted false sentences on the parent tip. No test pins those sentences. `**Correction (` sub-bullets are an existing form in `MECHANISMS.md` (8 uses).

### Applicable journal entries

- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — violated, see the second BLOCKER.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — not addressed. The Apply-when matches only partly, because a hand merge need not move a lookup block, so this is a WARN.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — violated by the conflict-clearing reasoning (WARN).
- **2026-11-01 — After merging a base that changes the row shape a feature reads ...** — heeded for README counts and suites. Not heeded by block 18's file-scope rule (first BLOCKER).
- **2026-10-17 — Judge "identical to master" by git's view, not raw bytes** — heeded by block 18 (`git show origin/master:<path>`).

### What the critic did not check

- No shell in this session. I did not run `git merge-tree`, `pr_merged.py --contract <slug> --status --json` or any suite, so the conflict and auto-merge sets are the caller's, cross-checked only against this contract's block 3 and 4 file lists. The 0.14.x on `master` and the landing report under `.claude/state/landing/` (not present in this worktree) are unverified.
- CodeGraph was not available. I checked symbols with Grep and Read.
- North-star alignment: `.claude/north-stars/` does not exist.

---

## Critique (Revision 9)

**Critic:** contract-critic
**Date:** 2026-11-03
**Verdict:** warnings-only
**Scope:** Revision 9 only: blocks 19 and 20, the Revision 9 notes (block 19 preamble, block 11 pointer, Handoff intro and graph, Appendix C row P10, the Revision 9 Failure Modes and Uncertain Assumptions lines, the Revision 9 lines of `## Lessons referenced`), Open Questions 29-32 and `.claude/concepts/followups/2026-11-03-readme-tree-counts-and-step-pins.followup.md`. Checked against `pr_merged.py` `read_review_set` / `parse_gate_output`, `land_contract.py` P3, `check_version_bump.py`, the t18 artefact and its `.gate.json`, `contract-completion.md`, `test_parent_branch_rule_text.py`, `test_repo_consistency.py`, the README folder tree and the files on disk in this worktree.

### Findings

- **[WARN] The step-order test as specified collides with step 5a's own nested sub-steps 1-6.**
  - **What is wrong:** inside "The records pull request", step 5a carries six indented sub-steps (`contract-completion.md:82-87`, "   1. **Read the candidates" ... "   6. **No outcome of this step"). Block 19 asks that "1. **" to "9. **" "at the start of a line each appear exactly once". That holds only if "start of a line" means column 0. The file's idiom is the opposite: `TextCase.section` and `flat` squash all whitespace, newlines included (`test_parent_branch_rule_text.py:46-47`, `:60-66`). An implementer who reuses `section` counts "1. **" to "6. **" twice and gets a test that fails on the fixed file. Neither block 19 nor block 20 mentions that the nested list exists.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02, "Name the tests a fix may change by the state they guard, after reading them" (J4): read the target text before giving test instructions. `JOURNAL.md` 2026-11-02, "A rule titled 'every' must list every line it covers" (J10).
  - **Where in this contract:** `### 19`, TASK, Test bullet, "the step headings "1. **" to "9. **" and "5a. **" at the start of a line each appear exactly once".
  - → Addressed by: block 19's Test bullets define `records_step_labels(text)`. It reads raw lines bounded by "### The records pull request" and the next "### " line, never through `squash`, `flat` or `section`, and counts only column-0 steps. Step 5a's indented sub-steps 1-6 and the code block are excluded by name, and the control checks that an indented sub-step is not counted. Block 20's B1 bullet says the same.

- **[WARN] Block 19 asks for a control "in the file's existing control style", and the file has no such style.**
  - **What is wrong:** `test_parent_branch_rule_text.py` has no fixture-text controls. Its only controls are `positive_control` tests that "pass today by design: they pin text that must stay" on the real files (`:29-30`, `:191`). Every helper reads a file under `PLUGIN_ROOT` (`:52-66`). A check run "on a fixture text with a planted second "6. **" step" therefore needs a new pure function, and the TASK neither names nor allows one. The same gap affects "run the new step-order test against the file as it was before your edit (git show HEAD~1 or the base)". The test cannot read a `git show` blob without a temporary revert of a listed file or a text-taking entry point. Block 20 then requires that the test "fail on the pre-fix file", with no stated method.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02, "Name the tests a fix may change by the state they guard, after reading them"; `test_parent_branch_rule_text.py:26-30` (the file's own "How the checks read").
  - **Where in this contract:** `### 19`, TASK, "Add a control in the file's existing control style"; CONSTRAINTS, "Also run the new step-order test against the file as it was before your edit"; `### 20`, "pass on head and fail on the pre-fix file".
  - → Addressed by: the text-taking module-level function `records_step_labels(text)` is named in block 19. The control calls it on a fixture string held in the test. The pre-fix run pipes `git show <rev>:<path>` into `py -3 -I -c` that imports the test module and prints the labels; that command is in block 19, and block 20 runs it against block 19's base and head and quotes both outputs.

- **[WARN] "Byte-identical" contradicts the lesson the contract says it heeds.**
  - **What is wrong:** block 19 requires steps 6-9 to be "byte-identical to the same four lines of git show 274bf1e:...". On this Windows worktree, a raw-byte comparison of the checked-out file against a `git show` blob fails on CRLF line ends even when the content is equal. `## Lessons referenced` says block 19 heeds 2026-10-17 by checking "against `git show 274bf1e:<path>`". The lesson says to compare by git's view, not by bytes. Block 20 says "identical", which is safer, so the two blocks state different tests.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-17, "Judge 'identical to master' by git's view, not raw bytes, on Windows" (`JOURNAL.md:215-220`).
  - **Where in this contract:** `### 19`, TASK, "steps 6-9 are byte-identical to the same four lines of"; `## Lessons referenced`, the 2026-10-17 line marked "heeded in Revision 9".
  - → Addressed by: "byte-identical" is removed. Blocks 19 and 20 both judge steps 6-9 with `git diff 274bf1e -- <path>`: no added or removed line starting "6. **" to "9. **". The commit's own diff removes exactly the four old lines. The 2026-10-17 line in `## Lessons referenced` now names `git diff`.

- **[WARN] Block 19's pre-check stop list leaves out two files the parent branch changed after 274bf1e.**
  - **What is wrong:** the pre-check stops only on the four Files to touch plus the three registries. After the 274bf1e merge, block 17's second commit also hand-edited `CONTRIBUTING.md` and `skills/auto-improve-finish-install/SKILL.md`. A `master` commit touching either one makes the landing's second merge conflict, and the pre-check would let it pass. The `ASSUMED` (Revision 9) line repeats the gap: it lists "a registry, `README.md` or a file block 17 resolved by hand", and those two files were text fixes, not conflict resolutions. Block 20's `merge-tree` and P7 are later backstops. The pre-check is meant to be the stop that edits nothing.
  - **Prior artifact ignored:** this contract's block 17 Files to touch (`CONTRIBUTING.md`, `skills/auto-improve-finish-install/SKILL.md`); `JOURNAL.md` 2026-11-02, "A revision that adds a path adds its failure modes" (J6). The Revision 9 Failure Mode for a second-merge conflict names only "a file block 19 edits".
  - **Where in this contract:** `### 19`, TASK, Pre-check, "If it lists any file in Files to touch, or JOURNAL.md, MECHANISMS.md or VOCABULARY.md, stop"; `## Uncertain Assumptions`, the Revision 9 `ASSUMED` line.
  - → Addressed by: block 19's pre-check stop list now names `CONTRIBUTING.md` and `skills/auto-improve-finish-install/SKILL.md`. So do the Revision 9 `ASSUMED` line, the block 19 "second hand merge" note and the Revision 9 second-merge Failure Mode.

- **[WARN] Block 20 checks every folder-tree count, but block 19 may change only four of them.**
  - **What is wrong:** block 20 W1 says "every count in README.md's folder tree is true against the tree, measured by you". Block 19 says "Change no other README line". The tree holds more counts than the four. At least one looks false on disk: `README.md:764` says "6 generic data files" in `.claude/hooks/`. The folder has five data files (`architecture-guard.exceptions.json`, `architecture-guard.rules.json`, `db-destructive-guard.rules.json`, `integration-check.rules.json`, `working-agreements.rules.json`), and `hooks.json` has its own tree line at `:765`. If the reviewer counts it the same way, block 20 reports a finding block 19 was forbidden to fix. That is the setup for another revision loop.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02, "A rule titled 'every' must list every line it covers" (J10); the t18 artefact W1 ("The review's TASK says every README count must be true"), which is how block 18 produced this same finding.
  - **Where in this contract:** `### 19`, TASK, "Change no other README line."; `### 20`, "W1: every count in README.md's folder tree is true against the tree".
  - → Addressed by: block 20 is aligned to the four counts block 19 may change. Any other false tree count is information that points at the stub, never a finding against block 19. Block 19 was not widened, because "6 generic data files" depends on an undecided counting rule (six `.json` files, or five once `hooks.json`, which has its own tree line, is left out). The stub takes that rule. The decision is recorded in block 19's "Decided, not fixed here".

- **[WARN] Block 20's scope rules are false by construction.**
  - **What is wrong:** block 20 requires "block 19's commits touch only its four files". The precedent t17 head (`4707150`) was a Work Item Brief front-matter commit (`pr:`, `issue_link:`, `status:`), which t18 recorded as "Met, with one note". Block 19's head will carry the same bookkeeping commit, so the literal rule fails. Block 20 also says "Block 19 changes none of those files except JOURNAL.md". "Those files" covers files outside block 17's Files to touch, and block 19 edits `test_parent_branch_rule_text.py`, which is outside that list.
  - **Prior artifact ignored:** t18 artefact, Scope ("`4707150` touches the t17 Work Item Brief's front matter ... not a shipped file"); `## Critique (Revision 8)`, first BLOCKER (a review rule that cannot return `pass` by construction).
  - **Where in this contract:** `### 20`, CONSTRAINTS, "Scope: block 19's commits touch only its four files" and "Block 19 changes none of those files except JOURNAL.md, by one appended entry."
  - → Addressed by: block 20's Scope rule allows the t19 Work Item Brief's front-matter bookkeeping commit and reports it as a note. Its block 17 bullet now states exactly what block 19 adds: one file outside block 17's Files to touch (`test_parent_branch_rule_text.py`); inside them, the four-line deletion, four README count lines and one JOURNAL.md entry; MECHANISMS.md and VOCABULARY.md unchanged.

- **[WARN] t18's I1 (manifest descriptions say "28 skills" and "14 agents") is dropped with no recorded decision, and the mechanism it relies on does not exist.**
  - **What is wrong:** Revision 9 records B1, W1, I2, I3, `SUITES_PENDING` and the verdict line, but not I1. t18 says "The landing corrects them (Open Question 15)", and block 11 says the landing "corrects the manifest description counts". The landing's only manifest write is `check_version_bump.py` `raise_manifests` (`:111-126`), which rewrites `"version"` fields only. Its caller is `land_contract.py:2687-2689`. The tree has 33 skills and 15 agents, while `plugin.json:5`, `.claude-plugin/plugin.json:6`, `.cursor-plugin/plugin.json:4` and `.claude-plugin/marketplace.json:14` still say 28 (and 14 agents). Under the automatic landing, nothing corrects them, and block 19 forbids manifest edits.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04, "Check a documented guard behaviour against the guard's code"; Open Question 15; t18 artefact I1 and Disposition 3.
  - **Where in this contract:** `### 19`, "Why" (B1 and W1 only) and the Revision 9 note (no I1 line); `### 11`, "The landing raises it once, and corrects the manifest description counts".
  - → Addressed by: new Open Question 33. It recommends one post-landing pull request to `master` that corrects the four description strings and takes a patch raise, recorded in the stub. Block 19's "Decided, not fixed here" records I1. The Revision 9 pointer under block 11 corrects the "corrects the manifest description counts" claim; the original sentence is left as written, with the correction beside it.

- **[WARN] The header says `approved` while Open Questions 29-32 are open, so blocks 19 and 20 can be dispatched before the user answers.**
  - **What is wrong:** this is the first half of the Revision 8 BLOCKER, still present. The dispatch path and `concept-gate.py` read only `Status`, which says `approved`. Questions 29-32 are unticked, and the header Revision line calls Revision 9 a "draft". The TASK blocks have no conditional branch this time, which removes the Revision 8 BLOCKER's second half. Nothing in the tooling enforces "awaits the user's answers".
  - **Prior artifact ignored:** `## Critique (Revision 8)`, second BLOCKER ("The dispatch path reads only `Status`, and that already says `approved`"); `JOURNAL.md` 2026-10-22, "An accepted critic WARN or answered Open Question must amend the contract body before approval".
  - **Where in this contract:** header, "**Status:** approved" with "**Revision:** 9 (2026-11-03, draft; needs the user's re-approval"; `## Open Questions for User` 29-32 `[ ]`.
  - → Addressed by: the user answered Questions 29-32 on 2026-11-03, and they are ticked with the answers. The header Revision line and block 19's opening note say Revision 9 is approved by the user on 2026-11-03, except where Question 33 is open; Question 33 changes neither block. The header `Status` line is left to the main session.

- **[NIT] Block 19's preamble will be stale on approval.** "It awaits the user's answers to Open Questions 29-32 and the final approval" has to be edited where it stands when the questions are ticked (`JOURNAL.md` 2026-11-02, "Edit a reversed sentence where it stands").
  - → Addressed by: block 19's opening note is rewritten where it stands.
- **[NIT] The stub's second paragraph is conditional on Open Question 31.** "If the user answers that question no, the step-order pin moves here" stays in a tracked stub after a "yes", and the slug `...-and-step-pins` then names work the stub does not hold.
  - → Addressed by: the stub's second paragraph now states the answer: block 19 delivers the step pin. Its file name is kept, because the contract and the coordinator's records already cite it.
- **[NIT] The t18 artefact's "What was NOT checked" item "Pull request #223's description" is not carried into block 20 or recorded as dropped.** Low impact.
  - → Addressed by: dropped by decision. No gate reads the description and it does not ship. The decision is recorded in block 19's "Decided, not fixed here", and block 20 lists it under What was NOT checked.

### Checked, no finding

- **The supersedes mechanism really clears P3.** `land_contract.py:2274-2280` builds `review_files_by_task` from each sub-task's `.claude/reviews/` Files to touch. For t18 that is exactly the `.md` artefact, not its `.gate.json`. It then calls `pr_merged.read_review_set` on `parent_ref`. `read_review_set` (`pr_merged.py:3753-3790`) sets `effective: False` on every report that a readable Gate Output's `supersedes` names by basename, unless that Gate Output is in a loop. t18's own `.gate.json` has `"supersedes": []`, so there is no loop. `blocked_review_verdicts` (`land_contract.py:1287-1295`) skips a task whose report names are all superseded. Block 20's `.gate.json` uses only the keys `parse_gate_output` accepts (`:3693`). The precedent pairs t16→t5 and t13→t8 are on disk (`t16-...gate.json` names t5). The claim holds, provided block 20's verdict is a pass.
- **Parent Branch Delivery Rule.** Neither block lists a version file. Block 19 forbids manifest edits. All five declarations read 0.14.2 (`.claude-plugin/marketplace.json:8,15`), which equals both the parent base and the 274bf1e merge base, so parent mode passes. The `**Work Item Brief:**` header is present, and both sub-tasks target the parent branch.
- **Dependency graph.** The intro reads "17,18→19; 17,19→20". Block 19 depends on 17 and 18, and block 20 on 17 and 19. The intro says "nineteen mergeable blocks plus one scope note (twenty numbered blocks)". Appendix C P10 and the block 11 pointer agree.
- **Files to touch.** Block 19's four files cover every edit its TASK makes. The JOURNAL.md tail ends at J11 (`JOURNAL.md:404`), then `---` and the comment (`:411-413`), as the J12 bullet assumes. J12 matches t18 Disposition 4 verbatim. Rewriting "9 hook test suites" cannot trip `test_repo_consistency.py`, whose hooks regex excludes it (`:72`, `:424`).
- **W1 numbers.** Measured on disk: 23 `test_*.py` in `.claude/hooks/tests/`, 23 workflow scripts and 3 `_` helper modules in `.claude/scripts/`, 36 `test_*.py` in `.claude/scripts/tests/`, 3 files in `.claude/references/`.
- **The B1 locators.** "Cut the branch in a flat worktree" and "name the copies left" appear only in `contract-completion.md:89,92`, the t18 artefact and `test_parent_branch_rule_text.py:382`. The step 5a end-marker fix is real: `section` runs to the end of the file when the end heading is absent (`:65-66`).
- **Other t18 items.** B1 and W1 go to block 19, and the W1 pin (F2) goes to the stub. Disposition 1's suggested step pin is Open Question 31. I2 is in the Revision 9 note, the `ASSUMED` line and block 20's `merge-tree`. I3 is split into J12 and the main-session JSONL action. `SUITES_PENDING`, the stale bullet and the hand-back rows are Open Question 29. The stub exists on disk with `**Issue:** pending`.
- **Hidden Open Questions.** None of the tell words appears in the Revision 9 text.

### Applicable journal entries

- **2026-11-02 — Keep a review-fix block to the review's findings** — heeded by block 19: B1, W1 and J12, plus the step pin that t18 Disposition 1 itself suggested. The README pin is deferred to the stub.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded by block 19's end-marker fix.
- **2026-10-17 — Judge "identical to master" by git's view, not raw bytes, on Windows** — violated in wording by block 19's "byte-identical" (WARN above).
- **2026-11-02 — A revision that adds a path adds its failure modes** — heeded by four Revision 9 Failure Modes entries. The second-merge entry is narrower than the parent's post-274bf1e changes (WARN above).
- **2026-11-02 — After amending a contract, update every summary of the block graph** — heeded (intro, graph, block 11, Appendix C P10).
- **2026-11-02 — Name the tests a fix may change by the state they guard, after reading them** — not heeded for the new step-order test and its control (two WARNs above).
- **2026-11-02 — A rule titled 'every' must list every line it covers** — not heeded by block 20's "every count" against block 19's four counts (WARN above).
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — not heeded for the manifest-description correction attributed to the landing (WARN above).
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — heeded for the TASK text, which has no conditionals. The `Status` exposure remains (WARN above).

### What the critic did not check

- No shell in this session. I did not run `git diff --name-only 274bf1e origin/master`, `git merge-tree`, `git show 274bf1e:skills/pr-merged/references/contract-completion.md` or `pr_merged.py --contract <slug> --status --json`. So "steps 6-9 equal 274bf1e's" and t18's I2 file list (which "two test files"; whether one is `test_parent_branch_rule_text.py`, in which case block 19's pre-check stops) are unverified.
- CodeGraph was not available. I checked symbols with Grep and Read.
- `INTEGRATION.md`, the registry digest and `.claude/north-stars/` do not exist here, so items 7, 12 and 13 produce no findings. The End-User View and Adjacent Areas are unchanged by Revision 9.

