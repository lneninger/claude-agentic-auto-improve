# Follow-up — The shipped plain-language guard names one person in its messages

**Parent contract:** `.claude/concepts/2026-10-05-working-agreements-session-start.md`
**Derived from:** design investigation for the parent (not a scanner result; the cross-area scan could not be run, see the parent's Adjacent Areas)
**Date:** 2026-10-05
**Status:** stub
**Estimated scope:** small
**Issue:** pending

## What was noticed

The parent contract makes the shipped working agreements generic and adds a test that fails when a shipped agreement names a person, a project or a machine path. The plugin's own end-of-turn writing checker does not meet that bar. `.claude/hooks/plain-language-guard.py` names one specific person as the one who asked for the plain-language writing rule, twice, in its stop message (`BLOCK_HEADER`, around line 576), and names the same person in its module docstring (around line 5) and in a comment on transcript reading (around line 151). The stop message is shown to the model in every project that installs the plugin. The parent's genericity test scans only the agreement files, so it does not catch this.

## Why it was deferred

The parent's brief rules the plain-language guard out of scope, apart from reading its text, and changing a shipped hook's message is a behaviour change with its own tests.

## Suggested next step

Run `/design-first` on this stub: replace the person's name with "the user" in the guard's messages and comments, and extend the parent's genericity scan to cover the hook sources' user-facing strings.

## Pre-derived context

- **Adjacent area:** none mapped (the plugin's `.claude/area-mapping.json` has an empty `areas` set)
- **Files implicated:**
  - `.claude/hooks/plain-language-guard.py`
  - `.claude/hooks/tests/test_plain_language_guard.py` (any case that asserts on the header text)
  - `.claude/hooks/tests/test_working_agreements.py` (the genericity scan, once the parent ships)
- **Mechanisms touched:**
  - `Project-name check`
  - `Guard rules file`
- **Journal entries to re-read when promoting:**
  - `2026-10-04 — Check a documented guard behaviour against the guard's code`

---

> **Lifecycle:** see `.claude/templates/followup-stub.md`.
