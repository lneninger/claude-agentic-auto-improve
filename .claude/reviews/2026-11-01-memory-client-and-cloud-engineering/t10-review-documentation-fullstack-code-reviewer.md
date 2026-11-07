# t10 review documentation — fullstack-code-reviewer

**Verdict:** pass-with-findings

## Scope and range

- **Gate agent:** fullstack-code-reviewer
- **Sub-task:** t10-review-documentation (issue #175, parent #161)
- **Contract:** `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md` (Revision 7, approved)
- **Supersedes:** none
- **Reviewed on:** 2026-11-02
- **Commit range reviewed:** `3a53480..cd0f76b` on the parent branch `feature/memory-client-and-cloud-engineering`.
  - `3a53480` is the merge of t16 (#215), the last commit before block 9.
  - `cd0f76b` is the merge of t9 (#216) and is the head of this worktree.
  - The range holds two commits: `6cb830e` (the block 9 change: `README.md`, `CONTRIBUTING.md`, `MECHANISMS.md`, `VOCABULARY.md`, `JOURNAL.md`) and `3039902` (the t9 brief's pull request line only).
- **Block covered:** block 9, `6cb830e`, merged in `cd0f76b` (#216).
- **Method:** cold context.
  - I read every added line of `6cb830e` and checked each documented behaviour against the merged code, skill and agent text (journal 2026-10-04, "Check a documented guard behaviour against the guard's code").
  - I checked the counts against `skills/`, `agents/` and `.claude/agreements/`, the Known limitations against block 9's TASK list, the Project history record against the Business Concept term, and the three registry appends against the contract and the code.
  - I read the pull request #216 description last, only to see whether a missing item was disclosed.

## What was checked

**Counts.** Met.

- `skills/` holds 33 folders and `agents/` 15 files. The README now says 33 and 15 in both the provider table and the directory tree, and "fifteen agents" in Quick start step 4. The Agents list names 15 (adds `cloud-engineer`) and the Skills list names 33 (adds `cloud-engineering`).
- `.claude/agreements/` holds 7 files. The README says 7 in the provider table and the tree, and the agreements paragraph says "seven" and names the seventh, `use-the-project-history-record.md`, by its rule.
- The README's `test_auto_improve_finish_install.py` count moved from 308 to 313, matching the suite (see Evidence). `test_plugin_manifests.py` now fails only the merge-base version rule, which fails by design on a parent branch.
- The manifest descriptions still say "28 skills, 14 agents". They are version files, which block 9 must not touch; the landing corrects them (Open Question 15). Not a block 9 finding.

**Known limitations.** Met. All eight from block 9's TASK are present: shape `v0` provisional; no capture retry; changed items found only when re-returned; an empty project-name token list keeps all capture project-scoped; Cursor and Codex MCP naming untested; the `mcp__<server>__<tool>` id form and the host MCP timeout returning an error unverified, because the block 3 stub-server trials left no evidence (t5 review I3), with "A project should not set `memory.shape` until that trial is run"; the cloud scope rule enforced in text only; cloud-management MCP deferred.

- Each is true against the code. `tool_id` (`memory_boundary.py:178-180`) carries the `ASSUMED` comment. `SHAPES["v0"]["provisional"]` is `True` (`:66-75`). `apply_scope_safety` (`:571-582`) lowers every global candidate when the token list is empty. `.claude/.project-tokens.json` ships `"tokens": []`. `test_cloud_text_scans.py` exists and passes. `cloud.mcp-server` is read by nothing in `scripts/`.

**The Project history record.** Met.

- The README subsection lists what it holds, word for word with the Business Concept term (registries including `INTEGRATION.md` where kept, contracts and follow-up stubs, briefs), and separates it from `memory: project` agent memory.
- Readers: `/design-first` and the data-architect only. Appenders: the five confirmed steps the term names. Non-readers: the XS/S direct edit, `/debug`, `/git-commit` and `/ship`, plus an explicit "Not every flow touches it". No sentence claims that every flow reads or appends it.
- "The Central Memory System only supplements it", with "a local entry wins a conflict until you decide", matches the term and Open Question 9.
- The "Where you meet it" bullet matches block 15: the seventh agreement, the finish-install section that reports, lists and runs `--fix` only on a yes, and the Step 1.5 suffix. The suffix text is copied exactly from `central-memory.md:11`.
- One wording point on the contract-critic is I3 below.

**Architecture and the memory boundary.** Met.

- The diagram puts the two call sites where the code puts them: `/design-first` Step 1.5 (`skills/design-first/SKILL.md:50`) and the capture question after a `flipped` writing run, on its own (`cmd_capture_candidates` refuses `not-flipped`, `memory_boundary.py:590-591`). The text says capture is never folded into the records confirmation and never built from the dry run, which matches the contract and the t16 check of `/flow` `:523` and `:593`.
- "One file knows the tool names and shapes": `memory_boundary.py` holds `SHAPES` and the default tool names. `test_plugin_text_scans.py` passes with the three registry appends in place, so the appends use the configured-tool wording and no literal name.
- "Every field the server returns is untrusted" matches `check_item`, `build_item` and `clean_text`, which t16 checked.

**Configuration slots and states.** Met.

- The nine slot names, and the values given for `cloud.providers` and `cloud.iac`, match `.claude/project-profile.md:37-45`.
- The three states match `read_config` (`memory_boundary.py:189-223`). No server, or a placeholder or `none` (`pr_merged.load_slot:97-100`), is `disabled`. A server with an unknown shape or no retrieve tool is `unconfigured` with one line. Otherwise it is `enabled`, and capture is on only with a capture tool.
- The README is right where the profile's own row text is not (I6 below, out of this range).

**MCP integration and lifecycle.** Met.

- Main session only, ids from the script's output, one call with no retry, and `unavailable` with one line on an error, timeout or absent tool all match `central-memory.md` sections 1 and 2.
- Sending stops at the first failed send, which matches the contract's stop rule (t16 checked step 5a.4).
- Lifecycle: only `proposed` is claimed (`_candidate`, `:512`). Only `user-decision` and `source-code-fact` are capturable (`CAPTURABLE`, `:85`). `manual` and `post-approval` map to `ai-hypothesis` and are skipped (`:518-532`). The starting scope follows the tier (`:513`), and the token check only lowers it.
- The brief records `Retrieved:` lines with `id@version` and `Captured:` lines with `id@version` (`:662`, `:693`).

**Cloud capability.** Met.

- `skills/cloud-engineering/` opens only the references matching `cloud.providers` and `cloud.iac` (its description and `:21-28`). `agents/cloud-engineer.md` exists. `agents/security-auditor.md:99-110` holds the infrastructure-as-code checklist, skipped when `cloud.providers` is unset.
- Validation runs through `contractLanding.verification.steps` (`SKILL.md:54`). The "for the user to run" label is at `SKILL.md:13` and `:61`, and the "no permission mechanism" rule at `:15`.

**CONTRIBUTING rule.** Partly met.

- The rule is stated, and its claims about `is_shipped` are true. I ran `is_shipped` on each named class: the README, CONTRIBUTING, contracts, briefs and `.claude/scripts/tests/` are not shipped. The registries, agreements, add-ons, templates, hooks, scripts, skills, agents and references are shipped.
- The sentence that the scan "fails the build" is false: W1.

**Registry appends.**

- **MECHANISMS.md:** Memory adapter, appended at the end of `## Universal Patterns (cross-project)`, append-only. Its eight subcommands match `build_parser` (`:871-879`). Two inaccuracies follow from the contract text it copies: I1 and I2.
- **VOCABULARY.md:** all sixteen Business Concept terms are appended at the end of `## Universal Vocabulary`, append-only. Each matches its contract definition, and several add facts that are true against the code: "`test-confirmed` is never claimed, `ai-hypothesis` is never offered", and the limit of 8. One restates a Data Shapes row that the code does not meet: I4.
- **JOURNAL.md:** the t5 Disposition item 6 entry is appended verbatim, byte for byte against `t5-review-…md:175-180`, under `## Universal lessons`. The Revision 7 pre-approval critic entries are absent: W2.

**Scope.** Met. `git show --stat 6cb830e` lists exactly the five files in block 9's Files to touch. No version file changed. `check_version_bump.py` in parent mode keeps 0.12.4. There is no UI surface, so the End-User View audit does not apply, and Adjacent Areas does not apply.

## Findings

### W1 (warning) — CONTRIBUTING says the memory-tool scan "fails the build", but no build runs it. `CONTRIBUTING.md:162-163`

The new text says: "A scan in `.claude/scripts/tests/test_plugin_text_scans.py` enforces it, and fails the build on a shipped file that names a memory tool." The repository's only workflow is `.github/workflows/version-bump.yml`. It runs `test_check_version_bump.py` and `test_repo_consistency.py`, not `test_plugin_text_scans.py`. No script, workflow or hook in the tree calls the scan suite (a search for its name finds only the file itself). The scan fails when someone runs it, which block 9's own constraint did, but a contributor who reads "fails the build" will expect CI to catch a literal tool name, and CI will not. This is the class journal 2026-10-04 names: a documented guard behaviour that the code does not have. The README's sentence ("A scan in `test_plugin_text_scans.py` fails when any other shipped file names a memory tool") is accurate and needs no change.

Fix (text only, `CONTRIBUTING.md`): "A scan in `.claude/scripts/tests/test_plugin_text_scans.py` enforces it: run it before committing a change to a shipped file. It is not yet run in CI." Adding the suite to `version-bump.yml` (or a new workflow) is a separate change outside block 9's Files to touch, so file it as a follow-up if wanted.

### W2 (warning) — The confirmed critic entries for this contract were never appended to JOURNAL.md, and the landing is the last point at which they still count. `.claude/registries/JOURNAL.md`; `skills/design-first/SKILL.md:205`; contract block 9 TASK, block 11 scope note

Block 9's TASK asks for "the pre-approval critic entries the user confirmed for the Revision 7 critique, as the main session records them at approval". JOURNAL.md has exactly one entry naming this contract, the t5 entry. The Revision 7 critique (1 BLOCKER, 9 WARNs, 5 NITs) ends every finding with `→ Addressed by:`, and `/design-first` Step 3 (`SKILL.md:205`) says that for each finding the user agrees with and addresses, the main session appends a journal entry. No such entry exists for Revision 7, nor for the critique rounds 1 to 3, and no wording was recorded anywhere for the implementer to copy. The brief and the contract hold none. Pull request #216 discloses the gap in an unticked acceptance line, so this was not done silently.

Why it matters, and why it is a warning and not a block:
- The entries are the contract's own `pre-approval critic` lessons. `capture-candidates` offers only entries that exist at the live flip, with provenance `user-decision`. Entries appended after the landing's `/pr-merged` flip are never offered for this contract.
- JOURNAL.md is a shipped registry. An append after the landing needs its own version raise. The block 11 scope note says registry appends ride before the landing raise.
- Several Revision 7 findings only re-apply existing lessons (2026-10-22, 2026-10-28, 2026-10-04, 2026-10-15 under "Applicable journal entries"). It is a fair outcome for the user to confirm that no new entry is owed for some or all of them. That is the user's decision, not this gate's or the implementer's.
- Nothing about the documentation is wrong because of it.

Fix: before the landing, the main session asks the user which Revision 7 findings (and, if wanted, which earlier-round findings) to record. It appends the confirmed ones with `Trigger: pre-approval critic` and `Source contract:` set to this contract, under `## Universal lessons`, in the same commit as the landing's version raise. If the user confirms none, record that answer in the parent brief, so the gap is closed on the record.

### I1 (info) — The Memory adapter's Extend-by names a "source-kind table" that does not exist. `.claude/registries/MECHANISMS.md:97`; `memory_boundary.py:535-568`

"A new capture source is one entry in its source-kind table." `select_candidates` has no table of source kinds. A tuple, `(("MECHANISMS", "mechanism-entry"), ("VOCABULARY", "vocabulary-entry"))`, covers only a new bullet registry. Journal entries and Corrections are separate code paths. A new kind (for example a contract invariant) needs a new reader branch, a key rule and a provenance choice. The wording comes from the contract's New Mechanisms extension seam, so this is a contract-versus-code gap that block 9 copied, not one it introduced. Fix, append-only: add a `**Correction (date):**` sub-bullet saying that a new bullet registry is one pair in the tuple in `select_candidates`, and that any other source kind is a new branch there with its key and provenance rule.

### I2 (info) — "Bound only by the host's MCP timeout" drops the deadline argument. `.claude/registries/MECHANISMS.md:97`

The v0 request carries `deadline_seconds: 20` (`memory_boundary.py:72`, `:310-311`). The contract says the call is "bounded by the host's MCP timeout, with a deadline argument when the shape supports one" (Failure Modes, and the Retrieval request row). "Only" is too strong. The README says "bounded by the host's MCP timeout" without "only" and is acceptable. Fix: include it in the same Correction as I1, as "bounded by the host's MCP timeout, and by a deadline argument where the shape supports one".

### I3 (info) — "The contract-critic reads it and never appends" overlooks the Critique section it writes. `README.md:903`

The Project history record includes the concept contracts. `agents/contract-critic.md:24` says the critic's only write is appending one `## Critique` section to the contract file. So it does append to a member of the record, though never to a registry. The Business Concept term makes no claim about the critic. The README sentence comes from block 15's finish-install text, which t16 accepted. Fix (README, and finish-install with the t16 W1 fix): "The contract-critic appends only its Critique section to the contract under review, and never writes a registry."

### I4 (info, carried question) — The VOCABULARY entry "Memory exchange outcome" restates a row the code does not meet. `.claude/registries/VOCABULARY.md:104`

"`disabled` is never written and never printed. Any other state is the first line of the brief's `## Memory used` section." In the code, an enabled run with an empty retrieval prints nothing and writes nothing (`central-memory.md:43`), and an `unconfigured` run with no brief prints a skipped line and writes nothing (`design-first/SKILL.md:80`). This is t16's I4, still open as a question to the user. Block 9 copied the contract row faithfully, so this is not a block 9 defect. When the user answers I4, append a Correction here, or record a code change, to match.

### I5 (info) — "With both off, every brief, every flow and every printed line is what it was" is broader than true. `README.md:885-886`

The Project history record additions do not depend on either switch. The seventh agreement is delivered at every session start, and `/auto-improve-finish-install` gained a section and a doctor check. The memory-off parity tests cover Step 1.5 only. The subsection that follows mentions the agreement, so a careful reader can work this out, but the sentence as written is false for the finish-install flow. Fix: "With both off, every brief, every Step 1.5 run and every capture step is what it was before they existed. The Project history record rule below applies whatever the switches say."

### I6 (info, outside this range) — The profile's own row text says `none` turns memory off for two slots where the code reports `unconfigured`. `.claude/project-profile.md:38`, `:40`

The `memory.retrieve-tool` row says "`none` to turn retrieval off", and the `memory.shape` row says "`none` to turn memory off". `load_slot` reads `none` as unset (`pr_merged.py:97`), and `read_config` then answers `unconfigured` with a printed line and a brief line (`memory_boundary.py:210-218`). Only `memory.server` set to `none` gives `disabled`. The README describes the code correctly. The profile text came from block 1 and is not in block 9's files, so this is a follow-up: reword the two rows as "a server with this slot unset reports `unconfigured` on every design; set `memory.server` to `none` to turn memory off".

## What was NOT checked

- A live session with a real or stub MCP server. The id form and the host timeout stay unverified, which is the Known limitation the README now states.
- A real finish-install run, a real `/pr-merged` flip with memory enabled, or a real `/flow` Step 8. Those behaviours were checked against text and code, and against the t16 re-review's checks of the same text.
- README counts outside block 9's TASK (hooks, helper modules, data files, other suites' case counts), except the 308 to 313 correction block 9 made.
- Whether the user confirmed any Revision 7 critic finding for the journal. No record of it exists to check (W2).
- The reviewer-verdict JSONL log, the JOURNAL.md append for W1's class and the registry Corrections in I1 and I2. This gate writes only its two artefact files, so they are proposed under Disposition.

## Evidence

Every command ran from this worktree's root on 2026-11-02, at `cd0f76b`.

| Command | Exit | Result |
|---|---|---|
| `git log --oneline 6cb830e~1..cd0f76b` | 0 | `6cb830e`, `3039902`, `cd0f76b` |
| `git show --stat 6cb830e` | 0 | 5 files: JOURNAL.md +7, MECHANISMS.md +2, VOCABULARY.md +17, CONTRIBUTING.md +17, README.md +189 −13; all in block 9's Files to touch |
| `ls -d skills/*/ \| wc -l`; `ls agents/*.md \| wc -l`; `ls .claude/agreements \| wc -l` | 0 | 33, 15, 7 |
| `py -3 -I -c "<is_shipped over the CONTRIBUTING classes>"` | 0 | README, CONTRIBUTING, contract, brief, `scripts/tests/` False; registries, agreement, add-on, template, hook, script, skill, agent, reference, profile, token file True |
| `grep -rn test_plugin_text_scans` over `*.py *.yml *.json *.ps1 *.sh`; `ls .github/workflows` | 0 | only the suite itself; one workflow, `version-bump.yml`, running two other suites (W1) |
| `grep -c memory-client-and-cloud .claude/registries/JOURNAL.md` | 0 | 1 (the t5 entry only; W2) |
| `gh pr view 216 --json body` | 0 | unticked line: "The pre-approval critic entries for the Revision 7 critique are NOT in JOURNAL.md" |
| `py -3 .claude/scripts/tests/test_plugin_text_scans.py` | 0 | Ran 13, OK |
| `py -3 .claude/scripts/tests/test_registry_entries.py` | 0 | Ran 26, OK |
| `py -3 .claude/scripts/tests/test_repo_consistency.py` | 0 | Ran 22, OK |
| `py -3 .claude/scripts/tests/test_cloud_text_scans.py` | 0 | Ran 11, OK |
| `py -3 .claude/scripts/tests/test_memory_boundary.py` | 0 | Ran 111, OK |
| `py -3 .claude/scripts/tests/test_memory_off_parity.py` | 0 | Ran 28, OK |
| `py -3 .claude/scripts/tests/test_plugin_manifests.py` | 1 | 173 passed, 1 failed: the merge-base version rule, which fails by design on a parent branch (the landing raises). The README count check that failed at t16 (308 against 313) now passes |
| `py -3 .claude/hooks/tests/test_working_agreements.py` | 0 | 133 cases, 133 passed |
| `py -3 .claude/scripts/tests/test_auto_improve_finish_install.py` | 1 | Ran 313, matching the README's new count. The 19 failures t16 recorded are in the settings-writer and launcher classes, outside this range |
| `py -3 .claude/scripts/check_version_bump.py --base feature/memory-client-and-cloud-engineering --default-branch master --head-ref task/…/t10-review-documentation` | 0 | sub-task keeps 0.12.4; the landing raises it |

Files read: the whole `6cb830e` diff; `memory_boundary.py:60-90`, `:178-232`, `:486-600`, `:655-795`, `:835-880`; `pr_merged.py:74-104`; `.claude/project-profile.md:37-45`; `central-memory.md` sections 1 to 6 and 8; `design-first/SKILL.md` headings and `:205`; `agents/contract-critic.md:24`; `agents/security-auditor.md:96-110`; `skills/cloud-engineering/SKILL.md:1-63`; `.claude/.project-tokens.json`; JOURNAL.md `:68-74` and `:264-330`; the t5 Disposition item 6 and the t16 re-review in full; and, from the contract, Business Concept, Data Shapes rows 77 and 80, Extension Points, Failure Modes `:373`, block 9 to 11, the Critique (Revision 7) and the Review checklist.

## Disposition

No finding blocks. Block 9's documentation is accurate against the code, apart from W1 and the info notes.

1. **W1:** a one-sentence change in `CONTRIBUTING.md`. It can ride with the landing commit, or with the t16 W1 finish-install fix if that is amended into the contract. Adding the scan suite to CI is a separate follow-up.
2. **W2:** must be settled before the landing's `/pr-merged` flip. The main session asks the user which critic findings to record, and appends the confirmed entries in the landing's version-raise commit, or records "none owed" in the parent brief.
3. **I1 and I2:** one append-only Correction sub-bullet under the Memory adapter entry in `MECHANISMS.md`, batched with the landing raise.
4. **I3 and I5:** README wording, batched with W1.
5. **I4:** waits on the user's answer to t16 I4.
6. **I6:** a follow-up stub for the two profile rows (block 1's text).
7. **Proposed journal entry** (for the main session to confirm; this gate does not append):

   ```markdown
   ### 2026-11-02 — A "fails the build" claim must name the workflow that runs the check
   - **Trigger:** post-impl divergence
   - **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
   - **Lesson:** Before documenting that a test "fails the build" or "is enforced", find the CI workflow or hook that runs it; if none does, say "run it before committing" instead.
   - **Apply when:** documentation or a contract states that a scan or test suite enforces a rule
   - **Tags:** ci, enforcement-claim, readme-drift, text-scan
   ```

8. **Reviewer-verdict line** for `~/.claude/logs/reviewer-verdicts.jsonl`, outside this gate's write scope:

   ```json
   {"ts":"2026-11-02T00:00:00Z","contract_path":"D:/Dev/HIPALANET/claude-agentic-auto-improve/.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md","divergence":false,"drift_summary":"none in block 9; CONTRIBUTING claims CI runs the memory-tool scan (W1); Revision 7 critic journal entries never appended (W2)","critical_count":0,"warn_count":2}
   ```
