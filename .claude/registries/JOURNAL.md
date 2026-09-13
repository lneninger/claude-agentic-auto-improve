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

<!-- empty on day 1 — populated as lessons are discovered -->

---

<!-- empty on day 1 — populated as lessons are discovered -->
