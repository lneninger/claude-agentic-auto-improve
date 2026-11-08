# Follow-up — Record a CodeGraph MCP drop that happens after the session already used MCP

**Parent contract:** `.claude/concepts/2026-11-07-295-codegraph-gate-dropped-mcp.md`
**Derived from:** the parent's R-5 known limitation (second-pass critique WARN on criterion 5), not an Adjacent Areas scan
**Date:** 2026-11-07
**Status:** stub
**Estimated scope:** small
**Issue:** pending

## What was noticed

The parent writes one `cli-fallback` audit record per session, and only when no MCP call has succeeded earlier in that session (brief criterion 5, followed literally by the main session's decision). The incident that started #295 was a connection that dropped in the middle of a session, after earlier MCP calls worked. In that case the command-line route still opens the gate, but no record is written, so the audit log cannot show how often a mid-session drop happens.

## Why it was deferred

The brief's criterion 5 is authoritative for #295, and widening the condition needs its own decision on the record's reason and on per-turn versus per-session state.

## Suggested next step

Run `/design-first` on this stub once the parent ships: decide whether a second reason (for example `mcp-dropped`) is written when the command-line route opens the gate in a turn with no successful MCP call after an earlier successful one.

## Pre-derived context

- **Adjacent area:** none (`.claude/area-mapping.json` defines no areas)
- **Files implicated:**
  - `.claude/addons/codegraph/hooks/codegraph-turn-tracker.py`
  - `.claude/addons/codegraph/hooks/codegraph-turn-reset.py`
- **Mechanisms touched:**
  - #259 Session folder and the `logged-<reason>` rule
- **Journal entries to re-read when promoting:**
  - `2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval`

---

> **Lifecycle:**
> - Created by `data-architect` at Step 4.5 when an Adjacent Areas row is decided as `follow-up handle`.
> - Tracked by one GitHub issue per contract, opened by the main session at `/design-first` Step 3.4; the stub is the detail and the issue is what the user sees. A stub whose `Issue:` is still `pending` after approval is a defect.
> - Discovered by `/list-contracts` under the "Stubs / follow-ups" section.
> - Auto-archived to `<slug>.followup.archived.md` by `.claude/scripts/archive_stale_stubs.py` if older than 30 days and never promoted.
> - Promoted by running `/design-first` against the stub's `## What was noticed` paragraph — the resulting full contract should `superseded` this stub (rename the stub to `.followup.superseded.md` and add a `Superseded by:` line at the top).
> - `concept-gate.py` does NOT honor `Status: stub` as approved — you cannot write code authorized only by a stub.
