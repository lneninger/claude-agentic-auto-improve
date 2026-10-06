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

---

<!-- empty on day 1 — populated as lessons are discovered -->
