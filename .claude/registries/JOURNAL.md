# Adaptive Engineering Journal

> **Purpose:** append-only log of lessons learned across concept contracts. Captures pitfalls caught pre-approval by `contract-critic`, contract-vs-code divergences caught post-implementation by `fullstack-code-reviewer`, and manually-logged insights via `/journal-add`. Read by `data-architect` (Step 1) and `contract-critic` on every run so past lessons become forward-looking checklist items.
>
> **Maintained by:**
> - `contract-critic` outputs that the user confirms during `/design-first` Step 5 → entry appended automatically with `Trigger: pre-approval critic`.
> - `fullstack-code-reviewer` post-implementation, when it detects justified contract-vs-code divergence (the contract had a defect) → entry appended with `Trigger: post-impl divergence`.
> - `/journal-add` skill → manual entry, any project, any time.
>
> **Structure:** two tiers. Universal lessons apply across every project. Project sections hold codebase-specific lessons. `data-architect` and `contract-critic` always consult BOTH tiers.
>
> **Append-only:** never reorder or rewrite past entries. If a lesson is later refined, append a new entry that references the old one by date+title. The historical trail matters.

---

## Entry shape

```markdown
### YYYY-MM-DD — <short, scannable title>
- **Trigger:** pre-approval critic | post-impl divergence | manual
- **Source contract:** `.claude/concepts/<slug>.md` (or `N/A` for manual)
- **Lesson:** <one-line, actionable — "do X" or "avoid Y when Z">
- **Apply when:** <pattern future critic should match against — concrete signal a contract should heed this>
- **Tags:** <comma-separated keywords for grep — e.g. `reuse, MarketElements, field-resolver`>
- **Areas:** <optional; omit when the lesson applies universally. Comma-separated area slugs from `.claude/area-mapping.json` (e.g. `ingestion-job, signalr-hub`). Manual `Trigger: manual` entries with `Source contract: N/A` may use this field to tell the cross-area scanner which buckets the lesson applies to.>
```

### Tag conventions

- **`ui-evolution`** — set on any lesson that should be re-read by `ui-ux-designer` on every invocation (Step 0 grep). Use when the lesson refines a design-system primitive, a Material/Tailwind interaction rule, an accessibility pattern, or a recurring UI mistake worth eventual promotion via `/promote-ui-rule`.
- **`app:<name>`** — optional sub-tag naming one application from the project profile's `frontend.roots` slot, used when a `ui-evolution` lesson is scope-specific (for example, a `dark` app demands `-400` text where a `light` app uses `-700`; the polarity per app is the `frontend.theme-polarity` slot). Lessons without an `app:*` tag apply to every app.
- **`recurring-mistake`** — set alongside `ui-evolution` when the lesson is the THIRD or later occurrence of the same anti-pattern; `/promote-ui-rule` reads this signal to gate promotion of the rule into `architecture-guard.rules.json`.

Retroactive tagging of pre-2026-05-20 entries is NOT performed — the journal is append-only. Existing entries that pre-date these conventions remain untagged; new entries should adopt the conventions when applicable.

---

## Universal lessons (apply to every project)

### 2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work
- **Trigger:** pre-approval critic
- **Source contract:** `.claude/concepts/2026-10-04-auto-improve-finish-install-skill.md`
- **Lesson:** Write configuration in the form a real consumer already runs, and prove it with one harmless invocation before the code depends on it.
- **Apply when:** a contract writes hook commands or other host-read configuration that depends on a variable being expanded in a particular syntax
- **Tags:** `hooks, settings-json, env-expansion, assumption`

### 2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case
- **Trigger:** pre-approval critic
- **Source contract:** `.claude/concepts/2026-10-04-auto-improve-finish-install-skill.md`
- **Lesson:** Before marking a reused parser VERIFIED, feed it a template with placeholders and a file with the row missing, not only a filled file.
- **Apply when:** a contract reuses an existing parser for a template-fed file and claims placeholder handling is verified
- **Tags:** `reuse, parser, load_slot, placeholder, verified`

### 2026-10-04 — A root locator can return the consumer itself under vendoring
- **Trigger:** pre-approval critic
- **Source contract:** `.claude/concepts/2026-10-04-auto-improve-finish-install-skill.md`
- **Lesson:** A helper that finds the plugin by checking for a file the plugin ships also matches a vendored project that copied that file; never use it as the template source without excluding the project itself.
- **Apply when:** a contract reuses a lookup that is satisfied by a file present in both the plugin and a vendored consumer
- **Tags:** `plugin-root, vendored, find_plugin_root, reuse`

### 2026-10-04 — Detect an install mode by what the sync actually delivers
- **Trigger:** pre-approval critic
- **Source contract:** `.claude/concepts/2026-10-04-auto-improve-finish-install-skill.md`
- **Lesson:** Check the sync configuration's plugin-only list before requiring a file for a mode; a mode that demands an undelivered file never matches the real consumer.
- **Apply when:** a contract detects how assets reached a project by the presence of a particular file
- **Tags:** `install-mode, sync-config, plugin_only, detection`

### 2026-10-04 — Check a documented guard behaviour against the guard's code
- **Trigger:** pre-approval critic
- **Source contract:** `.claude/concepts/2026-10-04-auto-improve-finish-install-skill.md`
- **Lesson:** A README statement about a guard's fail direction or bypass must be verified in the hook source; a guard without a bypass blocks new users, and a report must say so.
- **Apply when:** a contract documents or reports what a blocking guard does when its input is missing or unconfigured
- **Tags:** `guard, fail-closed, codegraph-first, readme-drift, hooks`

### 2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control
- **Trigger:** pre-approval critic
- **Source contract:** `.claude/concepts/2026-10-05-working-agreements-session-start.md`
- **Lesson:** A scan that must keep certain names out of the plugin cannot prove it works against a hashed list, because the positive control has to plant the real name. Keep the literal list in the consuming project and plant a made-up word as the control.
- **Apply when:** a contract adds a genericity or leak scan, or any test that must prove a forbidden token is caught
- **Tags:** `genericity, positive-control, hashing, project-tokens, tests`

### 2026-10-05 — Text delivered to the model must say which rule wins against a skill's gate
- **Trigger:** pre-approval critic
- **Source contract:** `.claude/concepts/2026-10-05-working-agreements-session-start.md`
- **Lesson:** When a contract ships rule text that tells the model to follow it in every action, state the precedence: a project instruction or a skill's explicit gate wins. Check each shipped rule against the skills that already exist before approving it.
- **Apply when:** a contract ships standing instructions, agreements or prompt text that a hook delivers to the model
- **Tags:** `agreements, precedence, design-gate, prompt-injection, session-start`

### 2026-10-05 — Do not add shared state to stop a duplicate the install tool already refuses
- **Trigger:** pre-approval critic
- **Source contract:** `.claude/concepts/2026-10-05-working-agreements-session-start.md`
- **Lesson:** Before adding a marker file or lock to prevent double delivery, read the install tool: if it already refuses the mode that causes the duplicate, rely on that and state the residual risk in plain words. A marker adds a race and a timing window that can swallow a legitimate delivery.
- **Apply when:** a contract adds a marker, lock or time window to prevent two copies of a hook from both acting
- **Tags:** `duplicate-delivery, marker-file, race, install-mode, hooks`

### 2026-10-05 — A size budget must bound the summary it adds, not only the items it keeps
- **Trigger:** post-impl divergence
- **Source contract:** `.claude/concepts/2026-10-05-working-agreements-session-start.md`
- **Lesson:** When a budget rule says "name every dropped item", the summary line can grow past the budget and make the text longer than before the drop. Bound the summary (a few names, then a count) and add a final hard length check. Probe with many tiny items plus one big item.
- **Apply when:** a contract limits delivered text size and also requires the text to list what was dropped or skipped
- **Tags:** `size-budget, closing-line, host-cap, session-start, probe`

### 2026-10-05 — A documented "missing file means the default" must read one named location only
- **Trigger:** post-impl divergence
- **Source contract:** `.claude/concepts/2026-10-05-working-agreements-session-start.md`
- **Lesson:** The shared `hook_file()` helper searches the hook's folder, then the project, the current directory and the home folder. A fail-soft rules file read through it lets a project decoy set the limit. Read the rules file from the hook's own folder directly, clamp the value, and test the missing-file case with a decoy in each other place.
- **Apply when:** a contract says a rules or settings file falls back to built-in defaults when missing, or says a project must not change a limit under a plugin install
- **Tags:** `rules-file, hook_file, fail-soft, decoy, clamp`

### 2026-10-05 — Neutralise every field echoed from untrusted input, not only the body
- **Trigger:** post-impl divergence
- **Source contract:** `.claude/concepts/2026-10-05-working-agreements-session-start.md`
- **Lesson:** When project text is quoted and cleaned before it reaches the model, every other field derived from the same file (file name, path, slug, title) that is echoed anywhere in the output must be neutralised too. A file name carrying a line separator forged a plugin heading through the closing line. List every output field built from untrusted input and probe each with the payload.
- **Apply when:** a contract delivers text from a lower-trust source next to higher-trust text and also echoes names, paths or titles of that source
- **Tags:** `prompt-injection, file-name, origin-label, quoting, session-start`

### 2026-10-05 — Count a host's size cap the way the host counts, and prove the cap with a real trial
- **Trigger:** post-impl divergence
- **Source contract:** `.claude/concepts/2026-10-05-working-agreements-session-start.md`
- **Lesson:** The host cap on delivered context is not documented as to what happens above it. A real trial showed text above about ten thousand characters is lost entirely, and the host most likely counts UTF-16 units, not Python characters. Measure with the host's unit, keep a margin below the documented number, and put the trial result in the contract before freezing tests.
- **Apply when:** a contract delivers text into the model's context through a hook and depends on a size limit the host does not fully document
- **Tags:** `host-cap, utf-16, session-start, trial, size-budget`

### 2026-10-15 — A cleanup wired to run before its own trigger event has fired never runs
- **Trigger:** pre-approval critic
- **Source contract:** `.claude/concepts/2026-10-15-auto-cleanup-delivered-worktrees.md`
- **Lesson:** Do not wire an automatic step to a moment when the thing it checks is still pending (here: the records pull request is unmerged). Make the step safe to repeat and run it on every call, so the first call after the event does the work.
- **Apply when:** a contract adds an automatic step that depends on a merge, approval or status that lands after the step's trigger point
- **Tags:** `trigger-timing, idempotent, cleanup, pr-merged, advance`

### 2026-10-15 — Locate a script from the plugin root, never from the main checkout after moving there
- **Trigger:** pre-approval critic
- **Source contract:** `.claude/concepts/2026-10-15-auto-cleanup-delivered-worktrees.md`
- **Lesson:** A relative script path resolved after `cd` to the main checkout can run a stale or missing copy. Resolve the script absolutely, plugin root first, before changing directory.
- **Apply when:** a skill runs a repo script after moving the shell to another checkout
- **Tags:** `script-path, plugin-root, vendoring, cd, stale-copy`

### 2026-10-15 — Reuse the existing brief-linkage reader; a second one misses edge cases
- **Trigger:** pre-approval critic
- **Source contract:** `.claude/concepts/2026-10-15-auto-cleanup-delivered-worktrees.md`
- **Lesson:** A new reader that links a brief to a contract duplicates `find_linked_brief` and misses briefs with `contract: none`. Call the existing reader and add a fallback on the brief's branch.
- **Apply when:** a contract needs to map a work item brief to a contract, branch or worktree
- **Tags:** `brief-lookup, find_linked_brief, duplicate-parser, contract-none`

### 2026-10-15 — A fallback that finds "the brief" by the caller's own branch must prove the brief belongs to this contract
- **Trigger:** post-impl divergence
- **Source contract:** `.claude/concepts/2026-10-15-auto-cleanup-delivered-worktrees.md`
- **Lesson:** When an ownership lookup falls back to the starting tree's branch (or to any name-shaped match such as a prefix-matched advance-worktree name), check that the found item names this contract (its `contract:` is unset or this slug; the name was actually truncated) before treating it as owned. Otherwise a destructive step run from another work item's tree adopts that item's branch and worktree.
- **Apply when:** a contract derives a set of things to delete or mutate from the caller's current branch, folder name or a prefix match, rather than from a field that names the contract
- **Tags:** `ownership, brief-lookup, fallback, destructive, cross-item`

### 2026-10-16 — An unset ownership field is not proof of ownership
- **Trigger:** post-impl divergence
- **Source contract:** `.claude/concepts/2026-10-15-auto-cleanup-delivered-worktrees.md`
- **Lesson:** When a destructive step adopts an item through a fallback, accept it only when a field positively names this contract. "Unset" (`contract: none`, a placeholder) must reject the candidate, or the step must be limited to evidence that is GitHub-verified for this contract (recorded pull request heads), never the caller's current branch.
- **Apply when:** an ownership rule reads "the field is unset OR names this contract", and the item feeds a delete, a remote push or any other mutation
- **Tags:** `ownership, contract-none, fallback, destructive, placeholder`

### 2026-10-16 — A skill step that moves the shell must come after every later step that reads the working tree
- **Trigger:** post-impl divergence
- **Source contract:** `.claude/concepts/2026-10-15-auto-cleanup-delivered-worktrees.md`
- **Lesson:** If a skill step runs `cd <other checkout>` in the session's persistent shell, every later step that resolves a script by a relative path or reads files relative to the working directory now reads the other checkout. Run such a step in a subshell `( cd ... && ... )`, or make it the very last command of the skill.
- **Apply when:** a skill text inserts a `cd` into a step that is followed by other steps (a final status call, a report built from a script run)
- **Tags:** `cd, shell-state, skill-ordering, relative-path, stale-read`

### 2026-10-15 — A script that reads a project-owned file must be told which project, not search for one
- **Trigger:** pre-approval critic
- **Source contract:** `.claude/concepts/2026-10-15-subissue-title-parent-ref.md`
- **Lesson:** Under a plugin install, a shared multi-root locator ranks the plugin's own `.claude` folder ahead of the consumer's when the project directory variable is unset, so a project-owned file the consumer has not updated is silently replaced by the plugin's copy and the intended "missing" refusal never fires. Pass the path explicitly from the skill, and refuse when it cannot be determined.
- **Apply when:** a contract adds a helper that reads a project-authored file (conventions, rules, profile) through `work_item_conventions_path()` or another multi-root locator, and relies on a missing file or block producing a refusal
- **Tags:** `locator, plugin-install, conventions, fail-loud, explicit-path`

### 2026-10-15 — A new tracker-title field must be known before the issue exists
- **Trigger:** pre-approval critic
- **Source contract:** `.claude/concepts/2026-10-15-subissue-title-parent-ref.md`
- **Lesson:** A title composed before the create call cannot contain the new issue's own number. When a user asks for "the sub-issue number" in the title, ask what it counts, and use a value known up front (the sub-task's position in the parent's plan) rather than a create-then-rename round trip.
- **Apply when:** a contract changes a tracker title format that is built before the create call and the request mentions an identifier of the item being created
- **Tags:** `tracker, title, ordinal, create-then-retitle`

### 2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test
- **Trigger:** pre-approval critic
- **Source contract:** `.claude/concepts/2026-10-15-subissue-title-parent-ref.md`
- **Lesson:** `test_skill_script_lookup.py` cuts every lookup block at its first `py -3 "$VAR"` line. Moving or extending a lookup block in a skill without listing that test in the run list lets a break through unseen.
- **Apply when:** a contract moves, copies or extends a script-lookup block inside any skill or reference file
- **Tags:** `skill-lookup, test-run-list, vendoring`

### 2026-10-16 — A "missing project file" refusal must cover both the unset root and the set-but-absent file
- **Trigger:** post-impl divergence
- **Source contract:** `.claude/concepts/2026-10-15-subissue-title-parent-ref.md`
- **Lesson:** The contract's guard refused only when the project directory variable was unset. With the variable set and no conventions file in that project, the shared locator still fell through to the plugin's own file and the helper composed a title from it. When a helper falls back from an explicit path, read exactly `<project root>/<file>` and refuse in both cases; never fall through to a multi-root locator. Also: a value a helper normalises (a parent written `#638`) must be passed on in its normalised form to every later command in the same block, and a block that creates a tracker record must print the new record's id before any step that can fail.
- **Apply when:** a contract's invariant says "refuse when the project root cannot be determined" for a project-owned file, or a skill block validates an input and then runs a mutating command with it
- **Tags:** `locator, plugin-install, fail-loud, contract-amendment, normalised-value, orphan-record`

### 2026-10-16 — Never let free text start an argument handed to a native program from Git Bash
- **Trigger:** post-impl divergence
- **Source contract:** `.claude/concepts/2026-10-15-subissue-title-parent-ref.md`
- **Lesson:** Git Bash turns an argument of the form `--option=/text` into a Windows path before a native program such as `py` sees it, so `/flow note` arrived as `C:/Program Files/Git/flow note` and a public issue title would have been silently corrupted. A test that passes the value as an argument list without a shell cannot show this; only a replay in the real shell can. Prefix free text with a character the receiver trims (one space) or send it through a file or standard input, and add a replay test with a title that starts with `/`.
- **Apply when:** a skill's shell block passes free text (a title, a name, a message) to a native program as an argument on Windows
- **Tags:** `git-bash, msys, path-conversion, free-text-argument, replay-test`

### 2026-10-17 — Git for Windows lists files beneath an untracked junction; a parent-link check is load-bearing
- **Trigger:** post-impl divergence
- **Source contract:** `.claude/concepts/2026-10-17-worktree-removal-untracked-identical.md`
- **Lesson:** The contract ASSUMED git does not list files beneath an untracked junction or symlink folder and called the parent-link check "defence in depth". That is FALSIFIED: `git status --porcelain -z --untracked-files=all` printed `?? d/f.txt` where `d` was a junction to a folder outside the tree. Any step that deletes or rewrites a path taken from git's status must check every folder between the tree root and the file for a link (`_is_link`) and check real-path containment, and must do it immediately before the mutation, not only before a slow subprocess.
- **Apply when:** a contract deletes, moves or overwrites files whose paths come from `git status` / `git ls-files` in a worktree that may hold junctions or symlinks (node_modules links, shared folders)
- **Tags:** `junction, symlink, git-status, delete-safety, windows`

### 2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-10-17-worktree-removal-untracked-identical.md
- **Lesson:** Before allowing a class of paths through a gate, grep the gate's own tests for fixtures that live in that class (for example marker-less temp folders). Give them the marker the rule keys on instead of weakening the rows.
- **Apply when:** a contract changes what a hook allows or blocks, or how it finds the project root
- **Tags:** concept-gate, hook-tests, fixtures, allowlist

### 2026-10-17 — Judge "identical to master" by git's view, not raw bytes, on Windows
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-10-17-worktree-removal-untracked-identical.md
- **Lesson:** Compare a working-tree file to a committed blob with `git hash-object` (filters on), so autocrlf checkouts count as identical. Raw-byte comparison never matches a CRLF checkout of an LF blob.
- **Apply when:** a contract compares working-tree files with committed content before deleting or skipping them
- **Tags:** autocrlf, crlf, hash-object, cleanup, windows

### 2026-10-22 — Describe a broken install by the rows each install age really has
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-10-18-remove-plain-language-hook.md
- **Lesson:** When a contract documents what breaks if a project deletes a shipped hook file but keeps its rows, read how each registration was written in each plugin version. Since 0.9.8 the guard had one prompt-submit row and ran at Stop only through the dispatcher, so only older installs had a direct Stop row. A real call of the launcher confirms the exit code, not which rows exist.
- **Apply when:** a contract removes or renames a hook file, or changes how a hook is registered, and documents the effect on existing installs
- **Tags:** hooks, removal, vendored-install, registrations, readme-note

### 2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-10-22-webdesign-plugin-skills.md
- **Lesson:** When the user accepts a critic finding or answers an Open Question in a way that changes a Data Shape, edit that shape (value-object fields, halt table rows, convention clauses) in the same pass that flips Status. A one-line "accepted all recommendations" note leaves the implementer to invent the change and the reviewer to judge it as divergence.
- **Apply when:** a contract's Open Questions or Critique section records an answer or acceptance, and the Data Shapes, Invariants or New Mechanisms text still reads as it did before that answer (here: no `root-undeterminable` halt row, and no host built-in clause for `dataviz`)
- **Tags:** design-first, contract-amendment, critic-warn, open-questions, data-shapes

### 2026-10-28 — State the real trigger of a hook, not the printing condition
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
- **Lesson:** Read the hook registration (event and matcher) before writing a cost statement. A hook with no matcher starts a program on every prompt even when it prints only on keywords.
- **Apply when:** a contract states how often or how much a hook costs
- **Tags:** hooks, cost, matcher, userpromptsubmit

### 2026-10-28 — A new term's definition must be true against every existing member
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
- **Lesson:** Before defining a term such as Add-on by a universal negative, check each existing member. Two add-ons still keep human-only environment switches, so the claim was false the day it was written.
- **Apply when:** a contract proposes a VOCABULARY.md term that generalises over existing add-ons, hooks or mechanisms
- **Tags:** vocabulary, add-on, kill-switch, universal-claim

### 2026-10-28 — A rule that writes a slot the vocabulary calls frozen needs a vocabulary amendment
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
- **Lesson:** If an invariant writes a profile slot that a VOCABULARY.md term says is never changed, propose the amendment to that term in the same contract and name a second-run skip rule with a test.
- **Apply when:** a contract has an install or tool writing authored or none-valued project profile slots
- **Tags:** profile-slot, placeholder-slot, idempotence, vocabulary

### 2026-10-28 — Guard messages must use names the guard emits and degrade when a cited document is absent
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
- **Lesson:** Map rule names from the guard's own emitted rule names, and cite an installed document path only when the file exists; otherwise name the install skill.
- **Apply when:** a contract changes a hook's block or warn text to cite external documents
- **Tags:** guard, messages, rule-ids, absent-document

### 2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
- **Lesson:** Read the Extend-by line of the nearest MECHANISMS.md entry before declaring a New Mechanism; removal of what an apply wrote extends the apply entry.
- **Apply when:** a contract lists a New Mechanism that mirrors an existing entry's inverse operation
- **Tags:** mechanisms, reuse, extend-by, removal

### 2026-10-30 — A delivery rule must name every route into delivery, not only the one the author had in mind
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-10-30-parent-branch-delivery-rule.md
- **Lesson:** When a contract adds a rule about how work is delivered, list every flow that can produce the delivered shape (direct design, hand-run loop, single pull request, web merge, legacy work) in a table with the enforcement point and a test for each; test the rule against the code, not only against the flow the author imagined.
- **Apply when:** a contract changes how sub-tasks, branches, pull requests or version raises are produced or recorded
- **Tags:** delivery, bypass-flows, choke-point, parent-branch

### 2026-10-30 — A rule that refuses must give already-delivered work a named way out
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-10-30-parent-branch-delivery-rule.md
- **Lesson:** When a new refusal can fire on work that already merged, add an explicit owner-only exit and make the loop's next command name it, so the refused command is never suggested twice.
- **Apply when:** a contract adds a refusal to a record, dispatch or completion step that has in-flight or legacy cases
- **Tags:** refusal, legacy, escape-hatch, loop

### 2026-10-30 — One shared reader must own the filtering, not only the selection
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-10-30-parent-branch-delivery-rule.md
- **Lesson:** When two code paths read the same records, put the match filter inside the shared function; a parity test that bypasses each path's own filter proves less than it claims.
- **Apply when:** a contract unifies readers of briefs, records or contracts across the delivery scripts
- **Tags:** brief-linkage, parity-test, matcher, reuse

### 2026-10-30 — Widening a CI trigger changes who the check judges; list every pull request kind the old filter excluded
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-10-30-parent-branch-delivery-rule.md
- **Lesson:** When a contract drops a workflow's `branches:` filter, enumerate every head/base pair the filter used to skip and give each a mode; "not a `task/*` head, so unaffected" was false, because the default mode now judges stacked and hand-named pull requests into non-default bases that were never checked before.
- **Apply when:** a contract edits `on:` triggers, branch filters or path filters of a CI workflow, or adds a mode keyed on a head-ref pattern
- **Tags:** ci, workflow-trigger, version-bump, stacked-pr

### 2026-10-30 — A failed record written by a new rule must not be the input of an older guard that blocks the rule's own exit
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-10-30-parent-branch-delivery-rule.md
- **Lesson:** Before a rule writes a `failed` record (R-8), trace every guard that reads failed records (G-3 refuses `--accept-single-branch`, `escalate` halts the loop) and name the way out for in-flight work; otherwise a contract that was mid-flight at upgrade reaches a dead end with no owner command.
- **Apply when:** a contract adds a new `failure:` kind, a new failed-record writer, or a human-only exit guarded by existing refusals
- **Tags:** failed-record, legacy, escape-hatch, guard-interplay

### 2026-11-01 — A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for
- **Trigger:** post-impl divergence
- **Source contract:** D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261031-infra-71-warn-on-unshipped-hook-rows\.claude\concepts\2026-10-31-warn-on-unshipped-hook-rows.md
- **Lesson:** When a contract reuses an existing token or path reader for a check that reports absence, list the row forms the reader mis-splits (here `shlex.split(posix=False)` splits `"$CLAUDE_PROJECT_DIR"/.claude/hooks/x.py` into two tokens) and either fix the reader or prove each form is never reported; a basename-only consumer hid the split, a path-existence consumer turns it into a false finding on a working row.
- **Apply when:** a contract adds a finding of the form "file X is missing" on top of a reader whose existing callers use only the file name, or reuses `_launch_tokens` / `_launched_raw_tokens` for a new purpose
- **Tags:** false-positive, token-reader, shell-quoting, reuse, hook-row

---

<!-- empty on day 1 — populated as lessons are discovered -->

