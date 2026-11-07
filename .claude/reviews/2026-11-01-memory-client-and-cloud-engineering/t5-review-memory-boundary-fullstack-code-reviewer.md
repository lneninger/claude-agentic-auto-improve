# t5 review memory boundary — fullstack-code-reviewer

**Verdict:** blocked

## Scope and range

- **Gate agent:** fullstack-code-reviewer
- **Sub-task:** t5-review-memory-boundary (issue #170, parent #161)
- **Contract:** `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md` (approved)
- **Reviewed on:** 2026-11-02
- **Commit range reviewed:** `1ffc25b..c77dd1b` on the parent branch `feature/memory-client-and-cloud-engineering`. `1ffc25b` is the merge of t1 (#176), the last commit before block 2. `c77dd1b` is the merge of t4 (#201) and is the head of this worktree. The range also holds blocks 6, 7 and 12 and the t8 and t13 review artefacts, which had their own gate and are not reviewed here.
- **Blocks covered:**
  - block 2: `469f51f`, merged in `19c89c5` (#179)
  - block 3: `aa56162`, merged in `5ac8862` (#198)
  - block 4: `ca1be7c`, merged in `c77dd1b` (#201)
- **Method:** cold context. I read the code and skill text of each block against the contract's Data Shapes, Commands, Extension Points, route table and handoff blocks 2 to 4. I ran every suite cited below and probed the adapter with my own inputs from a scratch folder outside the repository. I did not rely on the implementers' commit messages or briefs.

## What was checked

- **One adapter point.** Met. `test_plugin_text_scans.py` (`TestOnlyTheMemoryAdapterNamesTheMemoryTools`) builds its file set by walking the ten named shipped folders plus the four root manifests from `Path(__file__).parents[3]`. It drops every path with a `.claude/worktrees/` segment and then filters with `check_version_bump.is_shipped`. Only `.claude/scripts/memory_boundary.py` holds the two default tool names, at lines 68 and 69 inside shape profile `v0`. The positive controls pass:
  - planted files at `skills/zz-made-up/SKILL.md` and `.claude/registries/ZZ.md` are caught;
  - copies under `.claude/worktrees/x/` are ignored;
  - files under `.claude/scripts/tests/`, `__pycache__` and `README.md` are not scanned;
  - the walk does not depend on the current directory.

  The registries and `.claude/hooks/tests/` are not exempt.
- **Memory off changes nothing.** Met. `test_memory_off_parity.py` runs `status`, `retrieve-request`, `record`, `check-contract`, `normalise` and `changed-items` against copies of every brief in `.claude/work-items/` and two fixture briefs (one LF, one CRLF). It does this under three profiles: absent, placeholder slots, and `memory.server` set to `none`. It compares a SHA-256 snapshot of the whole temporary tree before and after, and a positive control proves `record` does write when memory is enabled. `git diff --name-only 1ffc25b..c77dd1b` shows no change under `skills/task/` or `skills/journal-add/`, and two content tests pin both skills. Step 5a ends silently on an empty lookup, `disabled`, or capture off (`contract-completion.md:78`).
- **Unavailable and hung server.** Met in the text.
  - Retrieval: `central-memory.md` sections 1 and 2 cover an absent tool, a call error and a timeout. Each one records `unavailable (<reason>)`, prints one line and goes to Step 2. The call is made once, with no retry, and the host's MCP timeout bounds it.
  - Any failing subcommand prints one line and memory is treated as off for the rest of the run (`design-first/SKILL.md:77`).
  - Capture: the stop rule is at `contract-completion.md:83`.
  - Run-time behaviour against a real hung server was not observed (see I3).
- **Every server field neutralised.** Met.
  - `normalise` (`memory_boundary.py:329-391`) applies a rule to each field. `id`, `version`, `superseded_by` and each `conflicts_with` entry must match a safe pattern that excludes `@`. `scope` and `status` must be in closed sets. `provenance` is mapped, else it reads `unknown`. `title` and `summary` lose line separators and control characters, have leading markers stripped, have `|` and backticks replaced, and are capped at 120 and 600 characters.
  - The adapter keeps the first 8 accepted items in server order. A duplicate key keeps the first item.
  - `test_every_field_is_probed_with_every_payload` and `test_a_probed_item_cannot_forge_a_brief_line` pass. My own probe sent `x\u2028## H|`y\r\n> z` through every field. It got 4 rejections and 3 dropped references, title and summary came back as `x ## H/'y > z`, and provenance came back as `unknown`.
  - `record` cleans the fields of the receipt, Reported and Retrieved lines again before writing them (`test_receipt_fields_cannot_forge_lines`).
- **No item reaches the architect before the user's answer.** Met. `central-memory.md` section 4 asks the applicability question before section 5 passes anything. A dismissed question means no item applies (`:52`). `design-first/SKILL.md:80` and the PRIOR_FINDINGS line `memory_items` pass `applies` items only. The `data-architect` rule 9 limits the architect to `memory_items` and ranks items below the registries and the user.
- **Provenance never stronger than the table.** Met for the four Trigger values the journal and `/journal-add` define. It is not met for any other Trigger text (W3). The adapter never produces `test-confirmed` (`CAPTURABLE`, `memory_boundary.py:84`). `capture-request` refuses `ai-hypothesis`, any provenance it does not recognise, and any status other than `proposed`.
- **One shared reader.** Met.
  - `generate_registry_digest.py` gains `entry_blocks` and `journal_entries`. Both take text, not a path.
  - `tier_split` keeps its signature and calls `read()` and then `entry_blocks`. Joining the lines with `\n` and splitting them again gives the same lines, so line numbers do not move.
  - `TierSplitIsByteIdentical` runs `main()` twice, once with the copied pre-change function and once with the new one. It does this on the current registries and on fixtures with an entry before any tier heading and with Correction sub-bullets. The digest is byte for byte the same.
  - The hook's `parse_entries(text)` delegates to `journal_entries`. It imports normally from the scripts folder, binds with `getattr` after an import that cannot fail, and skips and logs when the reader is missing.
  - On the current JOURNAL.md, `HookCallerTests` gets the same `sig`, `trigger` and `source` as the old regex. The only differences are the source forms listed in the contract.
  - The adapter imports its readers through `__import__` with `getattr` binding and appends to `sys.path`. It never loads the hook. The repository does use `importlib.util`, but only in `test_registry_entries.py:85`, to load a hook whose file name has hyphens. That is a test-only use, and the constraint covers shipped code.
- **Candidates only from an entry whose own line names the contract.** Met.
  - Journal entries are matched by the stem rule on their own `Source contract` value (`stem_names`).
  - Bullets are matched on their own text, without sub-bullets (`text_names` on `block["text"]`).
  - A naming Correction is its own `correction-entry` and never makes its parent a candidate.
  - Tests cover a longer slug, a plain sub-bullet, an absolute Windows path, and per-domain and pre-heading tiers. One boundary case is noted in I1.
- **Capture only in step 5a after a live flipped run, refusing brief-not-carried before any send.** Met.
  - `cmd_capture_candidates` checks `capture-not-enabled`, then `not-flipped`, then `brief-not-carried`, before it reads a registry (`memory_boundary.py:550-557`).
  - A dry run cannot pass. `pr_merged.py:3817` gives a dry run the verdict `would-flip`, never `flipped`, and a dry run's `written_files` is empty.
  - The report keys `contract`, `completion.verdict` and `written_files` match `pr_merged.py:4094`, `:4803` and `:4804`.
  - `record --receipts` checks `written_files` again before it writes.
- **Capture is its own question after the flip, on both routes, and the records confirmation is unchanged and still comes first.** Met.
  - Step 3 of `contract-completion.md` is unchanged.
  - Step 5a follows step 5 and is "never folded into step 3's records confirmation" (`:54`).
  - `/flow:593` says "Step 8's confirmation stays BEFORE the writing run and is unchanged". `/flow:523` puts the capture question after that run and before Step 8 commits the brief.
  - `CaptureAtDeliveryTextTests` pins all of these sentences.
- **Stop rule, receipts and records pull request.** Met in the text. The stop rule is at `:83`. Receipts are recorded before step 7's copy, into a brief that is already in `written_files` (`:84`). No outcome of the step blocks the records pull request (`:85`). The receipt line loses its source reference in practice (W1).
- **Stops listed in /flow.** Met. `skills/flow/SKILL.md:547` lists the Step 1.5 applicability question and `:548` lists the step 5a capture question.
- **Nothing added that the contract rules out.**
  - No frontmatter key: met. `record` refuses `would-add-frontmatter` and checks that the frontmatter block is byte-identical before it writes.
  - No hook, store or background process: met. The only hook change is the contract's own thin-caller edit to `journal-post-approval-tracker.py`. No settings file, state store or scheduled job appears in the range.
- **Each part names its existing mechanism.** Met. Every row of Reused Mechanisms is reflected:
  - `load_slot`, `select_linked_brief`, `parse_brief_frontmatter` and `is_shipped` are imported, not re-implemented;
  - the brief is the only record;
  - the shared reader is extended in its own file;
  - Completion Verdict and `written_files` are consumed as they are;
  - the lookup block is pinned by `TestDesignFirstMemoryLookup` and `TestPrMergedMemoryLookup`;
  - the sibling reference is read by `pr-merged`.
- **Files to touch.** Met. Block 2 changed its six listed files. Block 3 changed 7 of its 9 (it left `test_repo_consistency.py` and `test_parent_branch_rule_text.py` untouched, which the contract allows). Block 4 changed its five listed files. No version file changed, and `check_version_bump.py` in parent mode keeps 0.12.4. No UI surface is involved, so the End-User View audit does not apply. `Adjacent Areas` is not applicable, and no file outside the blocks' lists was touched.
- **Data Shapes alignment.** Not met. B1 departs from the Commands table and from Extension Points Step 1.5 point 3. W1 and W2 are smaller departures. No HANDOFF or brief justifies any of them.

## Findings

### B1 (blocking) — `record` refuses the `unconfigured` state, so Step 1.5 never records it. `.claude/scripts/memory_boundary.py:662`, `skills/design-first/SKILL.md:78`, `.claude/scripts/tests/test_memory_boundary.py:796`

The contract says three things about this state:
- **Extension Points, Step 1.5 point 3:** "On `unconfigured`, record and print the one line."
- **Invariant I-M1:** the `## Memory used` section exists when the state was `enabled` or `unconfigured`.
- **Commands table:** `record` refuses `not-enabled` only for "state `disabled`: **writes nothing**".

`cmd_record` calls `require_enabled(cfg)`, which refuses every state other than `enabled`. I probed it with a profile whose only memory slot is `memory.server`. `status` answered `unconfigured (shape-unknown)`, and `record` exited 1 with `{"refused": "not-enabled", "detail": "memory state is unconfigured"}`. The brief was left unchanged.

Block 3 then wrote the skill text around the defect rather than reporting it. Line 78 reads "record the outcome with `record` where the adapter allows it. A `not-enabled` refusal from `record` here is expected". The test `test_unavailable_and_unconfigured_states_are_recorded` checks only `unavailable`, so its name claims coverage it does not have. No brief or HANDOFF declares the divergence. Under the Data-First audit, an unjustified departure from Data Shapes blocks the gate.

Fix, in one small block:
1. In `cmd_record`, refuse `not-enabled` only when `cfg["state"] == "disabled"`, or when the outcome says `disabled`. Keep `require_enabled` for `--receipts`, since capture needs `enabled`. For `unconfigured`, write only the `Memory: unconfigured (<reason>) | <date>` line, because no item can exist.
2. Rewrite `design-first/SKILL.md:78` as: "print its `line` and record it with `record` (outcome `{"state": "unconfigured", "date": "<today>"}`), then go to Step 2".
3. Split the test into `..._unavailable_...` and `..._unconfigured_...`, and assert the `Memory: unconfigured (shape-unknown)` line in the second.
4. Add an `unconfigured` variant to the positive control in `test_memory_off_parity.py`.

### W1 (warning) — Receipt lines lose their source reference in the real pipeline. `memory_boundary.py:633`, `skills/pr-merged/references/contract-completion.md:84`

`capture-candidates` emits `source_ref` as an object (`{"file", "line", "title", "date"}`, `memory_boundary.py:485`). Step 5a.5 tells the session to build each receipt with `source_ref`, so the natural input is that object. `receipt_line` passes it to `clean_text`, which returns `""` for anything that is not a string. My probe, fed the object, wrote `Captured: aaaa… |  | m1@1 | 2026-11-02`, with the source field empty, and `Not sent:` lines lost it in the same way. The contract's Capture receipt names "source ref" as a field. Every receipt test hands in a string (`"f.md:1"`, `test_memory_boundary.py:805`, `:824`, `:836`), so the tests hide the mismatch.

Fix: in `receipt_line`, accept the object and render `"<file>:<line>"`, with `file` through `clean_text` and `line` through `safe_token`. Keep accepting a string. Add a test that feeds a candidate's own `source_ref` object from `capture-candidates` output into `record --receipts`.

### W2 (warning) — `changed-items` is fed the raw response, not the normalised items. `skills/design-first/references/central-memory.md:37`

The Commands table defines `changed-items --input <normalised file>`, and Data Shapes says its input is "the normalised items". The reference passes `<the response file>`, the raw server output. The fields the command prints are still made safe. Two consequences follow:
- A notice can come from an item that `normalise` rejected or dropped over the cap of 8. My probe returned an item with scope `NOT-A-SCOPE`. `normalise` rejected it (`invalid-scope: 1`), but `changed-items` still raised a notice for it.
- An integer `version` from the server, such as `1`, never equals the recorded string `"1"` (`memory_boundary.py:775`). That gives a false "changed" notice.

Fix: write the `normalise` output to a second temporary file and pass that file to `changed-items`. Update the reference's code block and the parity test's call to match.

### W3 (warning) — Provenance is chosen by substring, strongest first. `memory_boundary.py:519-527`

`"pre-approval" in trigger` is tested before `manual` and `post-approval`. A Trigger written as `manual (follow-up to a pre-approval critic finding)` therefore gets `user-decision`, but the table gives a manual entry `ai-hypothesis`, which is not offered. Likewise, `post-approval, found after post-impl review` gets `source-code-fact`. Every Trigger in the current JOURNAL.md has one of the four canonical values, and `/journal-add` offers only those four. So today's data is safe, but the rule "never stronger than the table" depends on how people write the line, not on the code.

Fix: compare the whole trimmed Trigger against the canonical values (`pre-approval critic`, `post-impl divergence`). Skip anything else as `unknown-trigger`, or check the weaker markers (`manual`, `post-approval`) first. Add a test with each of the two compound strings above.

### I1 (info) — A note paragraph after the last bullet of a section becomes part of that bullet's own text. `.claude/scripts/generate_registry_digest.py:111-112`

`entry_blocks` ends an entry only at the next top-level match or a heading, which is what the contract says. A non-indented paragraph after a blank line is therefore appended to the bullet above it. Suppose that paragraph names a contract, for example "see `.claude/concepts/<slug>.md`". The bullet above would then become a capture candidate for that contract, even though the bullet's own line never names it. The current MECHANISMS.md (43 entries) and VOCABULARY.md (73 entries) have no such paragraph, so this is latent. Fix: end the entry's own text at a blank line followed by a non-indented, non-bullet line. The digest still sees only `(title, line)`, so the byte-identical test is unaffected.

### I2 (info) — `capture-candidates` defaults `--default-branch` to `master`. `memory_boundary.py:803`

Step 5a does not pass the flag. The value matters only when the contract has no `**Work Item Brief:**` header and several briefs name it. In that case, `select_linked_brief` uses the topology, which a project whose default branch is `main` would misread. If that happens, capture refuses `brief-not-carried`, which is safe but silent. Fix: default to `None`, so the selector reads the real default branch, as `pr_merged` does.

### I3 (info) — The block 3 precondition has no recorded evidence. Contract, Handoff 3 Preconditions

Two trials were set as preconditions: one with a stub MCP server, to confirm the `mcp__<server>__<tool>` id form, and one with a server that never answers, to confirm the host's timeout returns an error. Neither result appears in the t3 brief or in the commit. The adapter's comment (`memory_boundary.py:178`) and Uncertain Assumptions still mark both as `ASSUMED`. The hung-server path is therefore correct in the text but unproven at run time. Block 9's Known limitations should say so, or the trial should be run before any project sets `memory.shape`.

## What was NOT checked

- A live session with a real or stub MCP server. No tool call, host timeout or `AskUserQuestion` rendering was observed (I3).
- A real `/pr-merged` writing run that flips a contract with memory enabled. The report keys were checked against `pr_merged.py`, and the refusals were checked against hand-built reports.
- The cloud blocks (6, 7, 12) and the t8 and t13 artefacts in the same range. They have their own gate.
- The full `test_pr_merged.py` suite. Blocks 2 to 4 do not change `pr_merged.py`.
- The reviewer-verdict JSONL log, the JOURNAL.md append and the MECHANISMS.md and VOCABULARY.md promotions. This gate writes only its two artefact files, so they are proposed under Disposition.

## Evidence

Every command ran from this worktree's root on 2026-11-02, at `c77dd1b`.

| Command | Exit | Result |
|---|---|---|
| `git log --oneline --merges -20` | 0 | blocks 2, 3 and 4 merged in `19c89c5`, `5ac8862` and `c77dd1b` |
| `git show --stat 469f51f` / `aa56162` / `ca1be7c` | 0 | 6, 7 and 5 files, all inside each block's `Files to touch` |
| `git diff --name-only 1ffc25b c77dd1b` filtered for `settings`, `hooks`, `skills/task/`, `skills/journal-add/`, `templates/work-item` | 0 | only `.claude/hooks/journal-post-approval-tracker.py` |
| `py -3 .claude/scripts/tests/test_memory_boundary.py` | 0 | Ran 91, OK |
| `py -3 .claude/scripts/tests/test_registry_entries.py` | 0 | Ran 24, OK |
| `py -3 .claude/scripts/tests/test_plugin_text_scans.py` | 0 | Ran 13, OK |
| `py -3 .claude/scripts/tests/test_memory_off_parity.py` | 0 | Ran 17, OK |
| `py -3 .claude/scripts/tests/test_skill_script_lookup.py` | 0 | Ran 29, OK |
| `py -3 .claude/scripts/tests/test_parent_branch_rule_text.py` | 0 | Ran 39, OK |
| `py -3 .claude/scripts/tests/test_repo_consistency.py` | 0 | Ran 22, OK |
| `py -3 -m unittest discover -s .claude/hooks/tests -p "test_*.py"` | 0 | Ran 485 tests, "FAILED (errors=2)". Both errors come from `test_hook_data_files_project_first.py:351` and `test_post_edit_dispatcher.py:470`, which are script-style modules that call `sys.exit(0)` at import, so discovery reports them as errors. `SystemExit: 0` means their own checks all passed. Neither file changed in the range (the last change to `.claude/hooks/tests/` is `bdbfe6a`, an ancestor of `1ffc25b`) |
| `py -3 .claude/scripts/check_version_bump.py --base feature/memory-client-and-cloud-engineering --default-branch master --head-ref task/…/t5-review-memory-boundary` | 0 | "sub-task pull request keeps version 0.12.4; the landing raises it" |
| `py -3 -I <scratch>/probe.py <worktree>` (record under `unconfigured`) | 0 | `status` → `unconfigured (shape-unknown)`; `record` → exit 1 `not-enabled`, brief unchanged (B1) |
| same probe (receipts with the candidate's `source_ref` object) | 0 | `Captured: aaaa… \|  \| m1@1 \| 2026-11-02`: the source field is empty (W1) |
| same probe (every field set to `x\u2028## H\|`y\r\n> z`) | 0 | 4 rejected, 3 references dropped, title and summary `x ## H/'y > z`, provenance `unknown` |
| same probe (raw item with scope `NOT-A-SCOPE`) | 0 | `normalise` rejects it, but `changed-items` on the raw file still raises a notice (W2) |
| `py -3 -I <scratch>/blocks.py <worktree>` | 0 | 0 of 43 MECHANISMS and 0 of 73 VOCABULARY entries carry a trailing paragraph; a planted note paragraph is absorbed into the bullet above it (I1) |
| `grep '**Trigger:**'` over the journals | 0 | 25 `pre-approval critic` and 15 `post-impl divergence`; the one compound line is the template example, which does not match `JOURNAL_HEADER` |

Files read in full: `memory_boundary.py`, `central-memory.md`, `test_memory_off_parity.py`, and the hook's import block and `main`. Range diffs read: `generate_registry_digest.py`, `journal-post-approval-tracker.py`, `test_plugin_text_scans.py`, `design-first/SKILL.md`, `data-architect.md`, `concept-contract.md`, `flow/SKILL.md`, `pr-merged/SKILL.md`, `contract-completion.md` and `test_parent_branch_rule_text.py`. Also read: `test_registry_entries.py:240-357`, `test_memory_boundary.py:180-191` and `:730-805`, and `pr_merged.py:2992-3020`, `:3600-3625`, `:4085-4105` and `:4780-4810`. From the contract: Business Concept, Data Shapes, Reused Mechanisms, New Mechanisms, Extension Points, Failure Modes, Open Questions, Lessons referenced and Handoffs 1 to 5.

## Disposition

The gate blocks on B1. Its dependents (block 9) wait for a fix block and a re-review of that block only.

1. **Fix block (one sub-task, owner `python-ai-developer`):** B1, W1 and W2 together. The files are `memory_boundary.py`, `test_memory_boundary.py`, `test_memory_off_parity.py`, `skills/design-first/SKILL.md` and `skills/design-first/references/central-memory.md`. Fold W3 in, because it is four lines in the same file. Amend the contract's Implementation Handoff with the block before dispatch, as Revision 6 did for block 12.
2. **Re-review:** confirm B1, W1, W2 and W3 against this report. It supersedes this report.
3. **I1, I2:** optional. They can ride with the fix block.
4. **I3:** block 9's Known limitations must state that the MCP tool id form and the host timeout are unverified until the stub trial runs.
5. **Registries (block 9, batched before the landing raise):** promote the Memory adapter to `MECHANISMS.md` as the New Mechanisms section says. Use the wording "the configured retrieve tool" and "the configured capture tool", because the scan treats the registries as shipped. Append the contract's Universal terms to `VOCABULARY.md`.
6. **Journal entry for B1**, to be appended with block 9:

   ```markdown
   ### 2026-11-02 — A skill written around an adapter refusal hides a contract divergence
   - **Trigger:** post-impl divergence
   - **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
   - **Lesson:** When a later block's skill text says a refusal "is expected" for a case the contract says must succeed, stop and report the divergence; do not document around it. Name a test after only what it asserts.
   - **Apply when:** a handoff block writes skill text that calls a subcommand an earlier block delivered, for a state the contract's Commands table does not list as a refusal.
   - **Tags:** contract-divergence, refusal, skill-text, test-name, adapter
   ```

7. **Reviewer-verdict line** for `~/.claude/logs/reviewer-verdicts.jsonl`. It is outside this gate's write scope:

   ```json
   {"ts":"2026-11-02T00:00:00Z","contract_path":"D:/Dev/HIPALANET/claude-agentic-auto-improve/.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md","divergence":true,"drift_summary":"record refuses unconfigured (Commands/Step 1.5 say record it); receipts lose source_ref; changed-items fed raw response","critical_count":1,"warn_count":3}
   ```
