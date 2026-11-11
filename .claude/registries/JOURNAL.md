<!-- registry-layout: 2 -->

# Adaptive Engineering Journal

> **Purpose:** append-only log of lessons learned across concept contracts. Captures pitfalls caught pre-approval by `contract-critic`, contract-vs-code divergences caught post-implementation by `fullstack-code-reviewer`, and manually-logged insights via `/journal-add`. Read by `data-architect` (Step 1) and `contract-critic` on every run so past lessons become forward-looking checklist items.
>
> **Maintained by:**
> - `contract-critic` outputs that the user confirms during `/design-first` Step 5 → entry appended automatically with `Trigger: pre-approval critic`.
> - `fullstack-code-reviewer` post-implementation, when it detects justified contract-vs-code divergence (the contract had a defect) → entry appended with `Trigger: post-impl divergence`.
> - `/journal-add` skill → manual entry, any project, any time.
>
> **Structure:** two tiers. Universal lessons apply across every project. Project lessons (registry layout 2) live in domain files `JOURNAL/<domain>.md` beside this file, named by the `## Project tier` pointer at its end. `data-architect` and `contract-critic` always consult BOTH tiers.
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

### 2026-11-01 — After merging a base that changes the row shape a feature reads, re-check every coverage claim and round-trip test against the merged writer
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-10-31-warn-on-unshipped-hook-rows.md
- **Lesson:** After merging a base that changes the shape of the rows a feature reads (here the Project hook launcher row replacing the exec-form row), re-check every README and contract coverage sentence and every writer-to-reader round-trip test against the rows the merged writer now produces; the feature's own tests stayed green on hand-built old rows while the rows actually written today were skipped and its prose claimed they were covered.
- **Apply when:** a feature reads data another change's writer produces
- **Tags:** merge, row-shape, round-trip, coverage-claim, hook-row

### 2026-11-02 — A sweep that deletes every proven file in a folder must route EVERY local reader of that folder through the remote evidence, not only the one the contract was about
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-02-pr-merged-records-leftover-cleanup.md
- **Lesson:** Before a contract deletes local copies "because origin holds them", grep every reader of that folder (`load_records`, `load_delivery`, review gates, anything under `RESULTS_DIR`) and route each one through the remote-backed evidence; I-7 listed only the sub-task record readers, so the swept Contract Delivery Record (`contract-delivery.yaml`) left `delivery = load_delivery(slug)` at None, which un-delivers parent-branch contracts, bypasses G-5 and re-suggests `--record-delivery`.
- **Apply when:** a contract adds a deleter, mover or sweep over a folder that one or more local loaders read, and its evidence rule names only some of those loaders
- **Tags:** sweep, delete, evidence, local-reader, delivery-record

### 2026-11-02 — A skill written around an adapter refusal hides a contract divergence
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
- **Lesson:** When a later block's skill text says a refusal "is expected" for a case the contract says must succeed, stop and report the divergence; do not document around it. Name a test after only what it asserts.
- **Apply when:** a handoff block writes skill text that calls a subcommand an earlier block delivered, for a state the contract's Commands table does not list as a refusal.
- **Tags:** contract-divergence, refusal, skill-text, test-name, adapter

### 2026-11-02 — A rule every session needs goes in a shipped agreement, not a once-run step
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
- **Lesson:** Before putting a standing instruction in an onboarding skill or one design step, check Session-start context delivery and list the routes (direct edit, `/debug`, `/journal-add`, sessions that never design) that would never see it.
- **Apply when:** a contract adds a standing instruction to `/auto-improve-finish-install`, one skill step or any once-run path
- **Tags:** agreements, session-start, standing-guidance, reach

### 2026-11-02 — Search a proposed term against agent frontmatter and host docs before adding it
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
- **Lesson:** If the words already name something else (`memory: project`, the host's "project memory"), rename the term instead of adding "it is not X" to its definition.
- **Apply when:** a contract proposes a VOCABULARY term that reuses a word the repository or host already uses
- **Tags:** vocabulary, term-collision, naming, agent-memory

### 2026-11-02 — Describe a fixer a skill runs by everything it writes, and keep the skill's confirm-first promise
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
- **Lesson:** Describe `plugin_doctor.py --fix` (or any list-driven fixer) from its own requirement list (`REQUIREMENTS`, `apply_fixes`), and run it only after the user confirms the listed set.
- **Apply when:** a contract triggers `--fix` or another fixer that creates every missing item
- **Tags:** plugin-doctor, fix-scope, confirmation, side-effects

### 2026-11-02 — Name the tests a fix may change by the state they guard, after reading them
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
- **Lesson:** Before telling an implementer to change tests "around" given lines, read each one; a test that guards a neighbouring invariant (here `disabled`, I-M0) is named as unchangeable.
- **Apply when:** a fix block's CONSTRAINTS tell the implementer to change or relax tests by line number
- **Tags:** tests, invariant, fix-scope, line-reference

### 2026-11-02 — A path that calls a command must say how it finds the command's input
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
- **Lesson:** When a step calls a command that needs an input (`record --brief`), state on that same path how the input is found and what happens when it is absent; a rule that lives only on a sibling path turns a normal case into a reported failure.
- **Apply when:** one branch of a skill step (unconfigured, disabled, error) calls a command whose argument is resolved only on another branch
- **Tags:** skill-steps, missing-input, brief-linkage, degradation

### 2026-11-02 — A revision that adds a path adds its failure modes
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
- **Lesson:** For each new script call, fixer run or degraded path a revision adds, add a Failure Modes entry whose mitigation cites a mechanism.
- **Apply when:** a contract revision adds blocks or Extension Points and leaves `## Failure Modes & Mitigations` unchanged
- **Tags:** failure-modes, amendment, revision, completeness

### 2026-11-02 — After amending a contract, update every summary of the block graph
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
- **Lesson:** Re-check the header Revision line, the Handoff intro's block count and graph, and the prioritised plan's Depends on against the new blocks.
- **Apply when:** a revision adds, removes or re-links handoff blocks
- **Tags:** amendment, summary-drift, handoff-graph

### 2026-11-02 — Edit a reversed sentence where it stands
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
- **Lesson:** When an amendment reverses an earlier claim, edit that sentence; do not keep it and add a later bullet that contradicts it.
- **Apply when:** a revision changes a claim made earlier in the same section
- **Tags:** amendment, self-contradiction, scope-note

### 2026-11-02 — Keep a review-fix block to the review's findings
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
- **Lesson:** Put text for a new requirement in the block that owns the requirement, so each block's review judges one thing.
- **Apply when:** one revision adds both review fixes and a new user requirement
- **Tags:** block-scope, review-fix, separation

### 2026-11-02 — A rule titled 'every' must list every line it covers
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
- **Lesson:** A rule for "every state" or "every printed line" names each line, including failure and skipped lines, and a test pins each.
- **Apply when:** a contract adds text to every output line or state of a step
- **Tags:** every-claim, printed-lines, coverage

### 2026-11-02 — A "fails the build" claim must name the workflow that runs the check
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
- **Lesson:** Before documenting that a test "fails the build" or "is enforced", find the CI workflow or hook that runs it; if none does, say "run it before committing" instead.
- **Apply when:** documentation or a contract states that a scan or test suite enforces a rule
- **Tags:** ci, enforcement-claim, readme-drift, text-scan

### 2026-11-03 — When resolving a conflict hunk by keeping both sides, drop the base lines the other side rewrote
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
- **Lesson:** Before keeping both sides of a conflict hunk, diff each side against the merge base; lines one side left unchanged and the other side rewrote belong to the rewrite only, or the merge restores deleted text beside its replacement.
- **Apply when:** a merge resolves a prose or procedure conflict "keeping both behaviours", especially numbered steps
- **Tags:** merge, conflict-resolution, base-text, duplicate-steps

### 2026-11-05 — A bridge re-export that silently falls back to an inline copy must also say which one it gave
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-05-codegraph-guard-fail-open.md
- **Lesson:** When a contract asks a re-export to fall back to an inline copy AND asks a caller to behave differently when the native function is missing, specify the signal the caller reads (an exported flag such as `WORKTREE_OWN_ROOT_NATIVE`); without it the two requirements contradict and the implementer has to invent a new export.
- **Apply when:** a contract or addendum adds a `getattr`-with-fallback re-export to `_claude_paths.py` (or any bridge) and, in the same breath, a "missing helper" branch in a consumer
- **Tags:** bridge, re-export, fallback, older-helper, contract-addendum

### 2026-11-05 — A hardening fix applied to a shared classifier must be checked against every consumer of that classifier
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-05-codegraph-guard-fail-open.md
- **Lesson:** Before you narrow what a shared classifier accepts (here `_git_file_kind`, under `tree_kind`) for a security reason, list its callers and the action each takes on the new outcome. A rule that is safe for the new caller (the add-on's guard, which fails open on `undecidable`) can wall an existing enforcing caller (the main-checkout guard, which blocks on `undecidable`). Bare-repository worktrees and `--separate-git-dir` checkouts went from decidable to blocked.
- **Apply when:** a review or security fix asks for "the same refusal" in a function the contract lists as "consumed as-is", or in any helper behind `tree_kind`, `main_checkout_root` or another MECHANISMS.md classifier
- **Tags:** shared-classifier, tree-kind, hardening, regression, consumers

### 2026-11-05 — A same-host path rule must compare against both the written and the realpath form of the tree's own path
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-05-codegraph-guard-fail-open.md
- **Lesson:** On Windows `os.path.realpath` turns a mapped network drive (`Z:\`) into its UNC form (`\\server\share`). A rule that refuses a UNC target "unless it names the same host as the tree's own path" must take the host set from both the unresolved and the realpath'd own path, and must judge a hop after `realpath` against the folder it hops from. Otherwise a repository on a mapped drive whose worktree sits on another volume reads `undecidable`, and an enforcing caller walls it. Separately, a caller-side check placed after a call into an older helper only discards that helper's answer; the probe has already happened. Gate the call itself on the helper's release.
- **Apply when:** a contract adds a host, drive or "same location" comparison on paths, or a caller-side check meant to protect against an older shared helper
- **Tags:** unc, mapped-drive, realpath, older-helper, path-hardening

### 2026-11-05 — An "older release" test fixture must be pinned to a fixed commit or a frozen copy, never to HEAD
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-05-codegraph-guard-fail-open.md
- **Lesson:** Do not load "the previous release" of a file with `git show HEAD:<path>` in a test. Before the commit HEAD is the old release and the test passes; the moment the change is committed HEAD IS the new release, and every row that asserts "this helper lacks X" fails (five W-13 rows did, simulated by the pass-4 reviewer). Pin the fixture to the last release's commit or tag (checked with `git cat-file -e`, skipped when absent), or check in a frozen copy under the test's fixtures.
- **Apply when:** a contract or addendum asks a test to compare against "HEAD's", "the current", or "the last release's" copy of a file that the same change edits
- **Tags:** test-fixture, older-helper, git-show, head, self-invalidating-test

### 2026-11-06 — An exception sentence that names the outcome of a later call must list every outcome that call can have
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-06-session-folder-owner-and-tool-named.md
- **Lesson:** The contract's E1 and I-7b sentences say the repeat after a `retry-ticket-unwritten` block "is blocked once more (as `source-target`)". The guard's ticket step gives `ambiguous-target` when every target is of the unknown class (a Grep with only a pattern, a generic Glob), so the sentence is false for those calls at ten shipped sites and in the guard's own banner. Before you write a sentence that predicts which reason a later call gets, read the branch that picks the reason and name every value it can return, or name the outcome without the reason ("blocked once more, this time with the retry recorded").
- **Apply when:** a contract adds a message or doc sentence that predicts the block reason, exit code or log event of a future call
- **Tags:** guard-message, block-reason, exception-sentence, doc-drift

### 2026-11-06 — Judge a drive letter with a no-I/O check before any realpath, because realpath of a mapped drive can block
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-06-session-folder-owner-and-tool-named.md
- **Lesson:** The contract assumed `os.path.realpath` of a mapped network drive returns `\\server\share` (ASSUMED, to be recorded). The recorded row found a real mapped `Z:` on the developer machine (`net use`: Disconnected), and `os.path.realpath('Z:\\')` gave no answer in 10 seconds; measured again, `realpath('Z:\\x')` took 21.1 s and returned `Z:\x` unchanged, not the share, so the rule judged it local. A hook that resolves a drive before judging it can hang until the host's hook timeout, and a timed-out hook is a non-blocking error, which is an allow. When a rule must decide whether a drive letter is remote, ask the local drive table first (`GetDriveTypeW`, no network I/O) and refuse `DRIVE_REMOTE` there. Call `realpath` only after that check, and only for a drive the table calls fixed.
- **Apply when:** a contract adds a Windows path rule that calls `realpath`, `resolve()`, `samefile` or any opening call on a path whose drive letter may be a mapped network drive, inside a hook with a timeout
- **Tags:** windows, mapped-drive, realpath, hook-timeout, fail-closed

### 2026-11-07 — A contract that reorders a hook's decision steps must be re-read against every contract that reorders the same steps before either merges
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-06-session-folder-owner-and-tool-named.md
- **Lesson:** #271 put "no source target, allow" first so that nothing is resolved for a markdown read, while #261 (merged first) had moved the Turn marker check ahead of target classification for a cheaper hot path. A marker may only be read from a folder proven usable, so the merge had to resolve the per-user session folder on every call, non-source reads included: the contract's step 1 became false, the parent is now created on a markdown read, and every guard call pays the Windows drive check (about 8 ms for the `ctypes` import on first use). The bench and the docs written for #261 still described its order and its temp-folder layout. When two open contracts change the order or the state location of the same hook, name the other contract in each one's Preconditions, restate the merged order and its per-call cost in whichever lands second, and re-run the first one's measurement on the merged code.
- **Apply when:** a contract renumbers or reorders decision steps, or moves the state, of a hook or guard that another open (unmerged) contract also edits
- **Tags:** merge, decision-order, hot-path, concurrent-contracts, bench

### 2026-11-03 — A stop list checked against a moving default branch needs a rule for changes outside the edited lines
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
- **Lesson:** When a block stops on "master changed a file on the stop list", say in the block which kind of change still allows it to go on (for example a hunk outside the lines the block edits, proven by a quoted git diff and a clean git merge-tree), so a busy default branch does not force a contract amendment for every changelog paragraph.
- **Apply when:** a fix or merge block's pre-check compares origin/<default> against a stop list of shared, often-edited files such as README.md
- **Tags:** pre-check, stop-list, moving-base, merge-tree, amendment

### 2026-11-07 — A failed tool call is a different hook event, and a row's `if` matches each sub-command
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-07-295-codegraph-gate-dropped-mcp.md
- **Lesson:** Do not design a hook's "did the call succeed" rule around fields of `tool_response`. Claude Code fires `PostToolUseFailure` (no `tool_response`, an `error` text) for a non-zero Bash exit and for an errored MCP call, so a hook registered on `PostToolUse` only sees successes and the success signal is the event name. An MCP `tool_response` is a list of content blocks, not an object. A row's `if: "Bash(<word> *)"` is not a starts-with test: it matches each sub-command of a compound line and strips leading `VAR=value`, so `cd x && <word> y` reaches the hook and the hook must narrow by itself. The contract's `mcp-error` route, its "tool_response an object" rule and its "exactly what `if` admits" definition were all wrong; live trial L1/L2/L7 caught them.
- **Apply when:** a contract defines a success, failure or trigger condition for a hook from the payload shape or from an `if` pattern without a live trial having recorded the real payloads and the real `if` matches
- **Tags:** hook-event, posttoolusefailure, if-pattern, success-signal, live-trial

---

<!-- empty on day 1 — populated as lessons are discovered -->

### 2026-11-06 — A plugin repository that is also installed resolves its own older copy as "the plugin"
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-04-domain-split-registries.md
- **Lesson:** When a check compares a project against "the installed plugin", decide explicitly what happens when the project IS the plugin's source and an older installed copy exists; a stale cache copy turns the plugin's newest entries into "client-authored" findings. Skip only the advisory that the stale copy makes false (here R3 universal-candidate) when the project holds the plugin's own manifest, print one line saying how many were skipped, and never downgrade a finding: a vendored client that copied the manifest then loses an advisory, never a finding.
- **Apply when:** a contract resolves a separate plugin root (separate_plugin_root, find_plugin_root) to classify ownership, and the plugin's own repository is one of the projects it runs on.
- **Tags:** plugin-root, vendoring, ownership, cache-copy, assumption-falsified

### 2026-11-06 — A sub-task that flips the state an earlier sub-task's test pins must re-run that suite
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-04-domain-split-registries.md
- **Lesson:** A sub-task that changes the state that an earlier sub-task's test pins must re-run that suite. Briefs that flip repository state (migration applies, registry rewrites) need a `Run:` line that names every suite pinning that state; here t8 migrated this repository to layout 2 and t3's suite, which pinned the old flat state, stayed red on the parent branch because nothing re-ran it.
- **Apply when:** a brief flips repository state (a migration apply, a registry rewrite, a layout marker) that a test written by an earlier sub-task asserts on, and no CI workflow runs that suite.
- **Tags:** sub-task, regression, state-pin, run-line, brief

### 2026-11-07 — A fail-soft reader must not record "seen" for what it could not read
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-04-domain-split-registries.md
- **Lesson:** When a reader degrades to "no entries" because a dependency is missing, the caller must tell that apart from an empty file and skip every state write (seen sets, seeded markers, reader versions); otherwise the first healthy run treats all history as new.
- **Apply when:** a tracker or cache keys "already processed" on the output of a parser that has an ImportError or fail-soft path returning an empty result.
- **Tags:** fail-soft, seen-cache, retroactive-fire, lazy-import, degraded-path

### 2026-11-07 — A parent branch that shares files with a moving default branch must take the default branch in through a sub-task before its landing
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-04-domain-split-registries.md
- **Lesson:** The landing merges the default branch and resolves only union and regenerated paths. When the default branch rewrote a file the parent branch also rewrote (here the journal tracker, moved by each side onto a different shared reader), the landing halts. As soon as both sides touch one file, merge the default branch into the parent branch through a reviewed sub-task, decide which shared reader survives, and run the default branch's new suites there.
- **Apply when:** a contract delivered through a parent branch changes a file the default branch has changed since the parent branch was cut.
- **Tags:** parent-branch, landing, merge, shared-reader, unresolvable-conflict

### 2026-11-07 — Merge rules written for a long-lived branch must heed the default branch's journal, not only the branch's own
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-11-04-domain-split-registries.md
- **Lesson:** A lesson the default branch added after the branch was cut is not in the branch's journal, yet it arrives with the merge and binds it. Read the default branch's JOURNAL.md (git show origin/<default>:.claude/registries/JOURNAL.md) before writing conflict-resolution rules.
- **Apply when:** a contract writes rules for merging the default branch into a parent or other long-lived branch.
- **Tags:** merge, journal, parent-branch, conflict-resolution

### 2026-11-07 — No tool enforces how a pull request into a parent branch is merged; the next block must prove it
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-11-04-domain-split-registries.md
- **Lesson:** The repository allows merge commit, squash and rebase, and the Merge-direction check judges only the target. When a sub-task's value depends on a merge commit (a merge of the default branch), say so to the owner in its pull request, and open the next block with a check from the parent tip that the default branch's merge base moved.
- **Apply when:** a sub-task's pull request must be merged with a merge commit.
- **Tags:** merge-method, parent-branch, squash, run-first

### 2026-11-07 — Adapters that rebuild an old reader over a stricter grammar must list every behaviour difference
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-11-04-domain-split-registries.md
- **Lesson:** Keeping the old reader's tests as acceptance tests proves only the forms those fixtures hold. Read both readers side by side, list each form they read differently (fences, prose sections, legacy headings, continuation, field repeats), and pin each with a fixture row.
- **Apply when:** a contract replaces a reader's body with an adapter over another reader and keeps the old names.
- **Tags:** adapter, shared-reader, behaviour-difference, fixtures

### 2026-11-07 — A clean landing check goes stale when the default branch moves; re-run it immediately before launching
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-04-domain-split-registries.md
- **Lesson:** a merge-tree check proves a clean merge for the two commits it named, nothing more. Here the t14 review's check passed against origin/master a241f5c, and one registry-mirroring commit later (aa3f715) the same command conflicted in MECHANISMS.md and VOCABULARY.md, because new entries landed beside lines the parent branch had rewritten. Record the default branch's commit with every clean result, re-run the check as the last step before launching the landing, and treat a registry-only conflict as a small merge block, not a redesign.
- **Apply when:** a contract delivered through a parent branch waits between its last review and its landing while the default branch keeps merging.
- **Tags:** parent-branch, landing, merge-tree, stale-check, registries

### 2026-11-07 — A merge block's pull request must paste each required output, not tick a line that says it passed
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-04-domain-split-registries.md
- **Lesson:** When a contract block says "paste the output in the pull request" (Base-line checks, side-by-side comparisons, older-test greps), the description must carry the raw output per item; a ticked summary turns a verified check into an asserted one, and the reviewer must redo every check. Likewise, when the implementer finds that the contract mis-predicts the code (an exit code, a grep that cannot pass), the next block or an amendment must fix the text, not only the pull request note.
- **Apply when:** a contract block lists evidence to paste in a pull request, or a pull request records "the contract's wording does not match the code".
- **Tags:** evidence, pull-request, merge-block, contract-text, review

### 2026-11-09 — A change that adds a module-level import to a vendored script must update the vendored-file list in the same change
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-04-domain-split-registries.md
- **Lesson:** Sub-task 2 of issue #235 moved helpers into `_preview_apply.py` and `_plugin_root.py` and made `auto_improve_finish_install.py` import them at module level, but the Hook registration check's `VENDORED_FILES`, its test's own copy of that list and README step 2 still named five files, so a vendored five-file copy exited 2. No block ran `test_check_hook_registrations.py`, and no CI workflow runs it, so the landing's P8 step was the first to fail (run 20261109T154140Z-97de67). When a change adds or moves a module-level import in a script that a checker vendors, update that checker's vendored-file list, its docs and its registry entry in the same change, and put that checker's suite and the landing's verification steps in the block's Run list.
- **Apply when:** a block adds or moves a module-level import in a script named in a vendored-file list (a `VENDORED_FILES` constant, a README copy list or a sync configuration).
- **Tags:** vendoring, imports, landing, verification, test-coverage

### 2026-11-11 — A path-normalisation rule that lists the unsafe forms must also reject absolute paths
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-11-finish-install-step3-proposals.md
- **Lesson:** Decision 1 rejected a profile root that is empty, `.`, or holds `..` or `*`, but said nothing about a leading `/` or a drive letter, so `/srv/Api` and `C:/Outside/Web` became areas whose patterns never match a repository-relative path, and `project / Path("C:", ...)` read an `angular.json` outside the project. When a contract normalises an operator-written path that must be repository-relative, list "absolute (leading `/` or `\`, a drive letter, a UNC prefix)" among the rejected forms and add a test row for each.
- **Apply when:** a contract turns a profile slot, a config value or a command-line argument into a repository-relative path, glob or area pattern, and its rejection list names `..` but not absolute forms.
- **Tags:** path-normalisation, absolute-path, profile-slot, area-map, glob

### 2026-11-11 — A consent question whose trigger depends on the operator's own answer must be decidable before that answer
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-11-finish-install-step3-proposals.md
- **Lesson:** Decision 7 asks for one answer holding the tokens and "yes or no to the narrowing statement when it applies", but `narrows` was computed only from the confirmed `--token` list, so the first preview (no tokens yet) always said `narrows: false`, the skill never asked, and the final apply was refused `narrowing-unconfirmed`, forcing a second confirmation on the main first-install path. A "no" also blocked the other two files, because the write is all or none. When a gate depends on a choice the operator makes in the same answer, have the plan report the condition before the choice (for example "would narrow if any token is named"), and say what a "no" does to the rest of the plan.
- **Apply when:** a contract combines a single-confirmation flow with a gate flag (`--confirm-*`) whose condition is derived from flags the operator chooses in that same confirmation.
- **Tags:** one-confirmation, consent-gate, preview-hash, narrowing, skill-flow

## Project tier

This file holds only the Universal tier. Project entries live in domain files beside it, one file per domain, named `JOURNAL/<domain>.md`.

The file `general.md` always exists in that folder, and every `.md` file in the folder is read.
