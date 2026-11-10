# Follow-up — Run the 7-day rollback check of the CodeGraph cut-over

**Parent contract:** `.claude/concepts/2026-11-09-codegraph-hooks-cutover.md`
**Derived from:** the parent's Q4 (rollback rule, answered by the user on 2026-11-09), not an Adjacent Areas row
**Date:** 2026-11-09
**Status:** stub
**Estimated scope:** trivial
**Issue:** #262
**Owner:** the user

## What was noticed

The cut-over was approved without shadow data (waiver of 2026-11-09). After the cut-over, its measurement log cannot tell a false block from a true one, so the rollback rule rests on one measured number and on the user's judgement. The rule: roll back if more than 10% of gated calls fail open on the transcript (`fail-open:transcript-*` in the report's enforced section), or if the user reports any block they judge wrong.

## Why it was deferred

It can run only after the cut-over has been installed for 7 days in `StockToolScalpingMachine` and `StockToolScalpingMachine.Playwright`.

## Suggested next step

Seven days after both projects re-run `/auto-improve-codegraph-install`, run the report in each one, in PowerShell:

```
py -3 .claude/scripts/codegraph_shadow_report.py --project D:\path\to\StockToolScalpingMachine
py -3 .claude/scripts/codegraph_shadow_report.py --project D:\path\to\StockToolScalpingMachine.Playwright
```

Read the "enforced" section's fail-open share, and whether the log hit its 10 MB cap. Add any blocks you judged wrong. Then record one line per project on issue #262: either "keep", or "roll back", with the reason. A rollback follows `.claude/addons/codegraph/DISABLED.md`: run `/auto-improve-codegraph-uninstall` in a project at once, or ship a revert release.

## Pre-derived context

- **Adjacent area:** none
- **Files implicated:**
  - `.claude/scripts/codegraph_shadow_report.py` (read only)
  - `.claude/addons/codegraph/DISABLED.md` (the rollback route)
- **Mechanisms touched:**
  - Shadow decision log (enforced mode)
- **Journal entries to re-read when promoting:**
  - 2026-10-15 — A cleanup wired to run before its own trigger event has fired never runs

---

> **Lifecycle:** tracked by issue #262. Closed when both projects have a recorded "keep" or "roll back" line.
