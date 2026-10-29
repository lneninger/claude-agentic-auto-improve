# Follow-up — Deferred items from the angular-tailwind rule documents contract

**Parent contract:** `.claude/concepts/2026-10-28-angular-tailwind-rule-documents.md`
**Derived from:** Non-Goals and Open Questions of the parent (the cross-area scan had no areas to score)
**Date:** 2026-10-28
**Status:** stub
**Estimated scope:** medium
**Issue:** #86

## What was noticed

The parent contract settles the rules the old hook printed and the conflicts issue #84 lists. It leaves the following open:

- **Guard weak spots:**
  - the hard-coded `projects` parent folder and the `/ClientApp/` and `/features/` folder names;
  - scanning only `*.component.*` files;
  - the hex-colour regex matching template reference variables such as `#add`;
  - `relative` and `absolute` never checked;
  - the multi-edit gap;
  - the height-chain check seeing only the edited fragment;
  - stylesheet rules that only warn;
  - documents and comments that point at the old global hooks folder (for example the guard docstring's `~/.claude/hooks/architecture-guard.exceptions.json`);
  - a design document that cites a reference path that does not exist.
- **Kill switches of the other add-ons:** issue #84's decision 3 ("no environment-variable switches for ordinary add-ons") was applied to `angular-tailwind` only. `codegraph` (`CLAUDE_SKIP_CG`) and `strict-shell-gate` (`CLAUDE_BASH_GATE`, `CLAUDE_CONCEPT_GATE`) keep theirs as recorded human-only overrides. The maintainer decides whether those are safety overrides that stay, or switches to remove.
- **Advisor keyword:** the disabled advisor's keyword `ui` can never match. The pattern needs at least three characters. This matters only if the hook is turned back on, and `DISABLED.md` records it.
- **Doctor and preload gaps:**
  - `plugin_doctor.py --drift` does not compare add-on documents, and reports no finding when a disabled add-on hook is still installed;
  - the `python-ai-developer` agent preloads a `python-ai` skill that the plugin does not ship.
- **Candidate patterns not shipped:** the status badge, table rules beyond T-023, the card surface and the `constrained-panel` wrapper pair.
- **Untested delivery route:** project `.claude/rules/` files with path frontmatter, as another way to deliver rules (alternative E).

## Why it was deferred

Each item is either a guard weak spot that no settled conflict depends on, or a pattern that failed or was uncertain under the issue's "only colours change" test. The brief's out-of-scope list keeps both kinds out of this contract.

## Suggested next step

Run `/design-first` on the guard weak spots as one contract. Decide each candidate pattern with the maintainer before writing any rule text.

## Pre-derived context

- **Adjacent area:** none (`.claude/area-mapping.json` has no areas)
- **Files implicated:**
  - `.claude/hooks/architecture-guard.py`
  - `.claude/scripts/plugin_doctor.py`
  - `agents/python-ai-developer.md`
  - `.claude/addons/angular-tailwind/documents/UI-UX-PATTERNS.md`
  - `.claude/addons/codegraph/addon.json`
  - `.claude/addons/strict-shell-gate/addon.json`
- **Mechanisms touched:** Guard rules file, Vendored-asset drift, Scroll-edge CSS primitive
- **Journal entries to re-read when promoting:**
  - 2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures
  - 2026-10-04 — Check a documented guard behaviour against the guard's code
