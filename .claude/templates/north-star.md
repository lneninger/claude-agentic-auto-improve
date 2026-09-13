# North Star — <one-line aspiration title>

**Project:** <ProjectName>
**Slug:** <kebab-case-slug-matching-filename>
**Date created:** YYYY-MM-DD
**Status:** active
**Last reviewed:** YYYY-MM-DD

## Aspiration

<One paragraph in the user's own words. Resist re-writing — the user's framing IS the artifact.>

## Why this matters

<One sentence — the business value, the UX improvement, the engineering capacity unlocked. Concrete enough that a contract draft can defend itself against this.>

## Anti-patterns (what would BLOCK us getting there)

> List concrete code shapes / file paths / dependencies whose introduction would move the codebase AWAY from this north star. The `contract-critic` reads this list and BLOCKS contracts that introduce a listed anti-pattern unless they carry an explicit `Acknowledged conflict with:` line.

- <e.g. "Any new code that calls `System.IO.File.WriteAllText` on a user-visible path">
- <e.g. "A new feature that requires the operator user to author conditions">

## Current gap (Claude-maintained)

> Populated and updated by `/north-star-review`. Describes what currently exists that contradicts or doesn't yet support this aspiration. Cite file paths and mechanism names so the next reviewer can verify.

_Last updated: not yet reviewed_

- <gap-1>
- <gap-2>

## Suggested next steps (Claude-maintained)

> Populated and updated by `/north-star-review`. Ordered list of concrete contracts to draft next. Each line is a directly runnable `/design-first` invocation.

_Last updated: not yet reviewed_

1. `/design-first <concrete-task-title>` — <one-sentence-rationale>
2. `/design-first <next-task>` — <rationale>

## Related

- **Mechanisms** (from MECHANISMS.md, project section): <slugs that would need to extend or be replaced>
- **Areas** (from `.claude/area-mapping.json`): <area slugs implicated>
- **Adjacent north-stars**: <other thoughts in this same project that cluster with this one>
- **Lessons** (from JOURNAL.md): <entries whose `Apply when:` matches this aspiration's anti-patterns>

---

> **Lifecycle:**
> - Created by `/north-star "<aspiration>"` (skill prompts for fields).
> - Reviewed by `/north-star-review` (manual) or by data-architect Step 0.5 during `/design-first` (automatic).
> - Status: `active` → `achieved` when the codebase demonstrably satisfies the aspiration → `superseded` when replaced by a refined north-star (cite `Superseded by:`) → `abandoned` when explicitly dropped (cite reason).
> - `contract-critic` checklist item 13 BLOCKS contracts that introduce an Anti-pattern from an `active` north-star UNLESS the contract carries an `Acknowledged conflict with: <slug> — <reason>` line.
