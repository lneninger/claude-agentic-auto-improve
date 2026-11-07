# Follow-up — Review leftovers from the memory client and cloud engineering contract

**Parent contract:** `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`
**Derived from:** the t16 re-review and the t10 documentation review, findings that Revision 8 did not take on
**Date:** 2026-11-03
**Status:** stub
**Estimated scope:** medium
**Issue:** #165

## What was noticed

Revision 8 fixes only the text defects that are cheap and certain (the t10 review's W1, W2, I1, I2, I3 and I5). The following findings stay open. Each one is described in full in the review file named beside it.

From `.claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t16-re-review-memory-boundary-fullstack-code-reviewer.md`:

- **W1 (warning):** Stage 1a of `skills/auto-improve-finish-install/SKILL.md` still runs the doctor's `--fix` without asking, which defeats the new report-then-ask check in the same skill.
- **I1:** one literal printed line in `skills/design-first/references/central-memory.md` lacks the Project history record suffix.
- **I2:** Step 5a in `skills/pr-merged/references/contract-completion.md` does not mention the new `default-branch-unknown` refusal.
- **I3:** one assertion in the new finish-install pin in `test_memory_off_parity.py` cannot fail.
- **I4 (question):** on `enabled`, an empty retrieval prints nothing and records nothing; the Data Shapes row "Memory exchange outcome" says otherwise.
- **I5 (question):** rewriting the section under `unconfigured` drops earlier `Retrieved:` lines.

From `.claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t10-review-documentation-fullstack-code-reviewer.md`:

- **I4:** the "Memory exchange outcome" vocabulary entry repeats the Data Shapes row that the code does not meet (the same point as t16's I4).
- **I6:** in `.claude/project-profile.md`, the `memory.retrieve-tool` and `memory.shape` rows say `none` turns memory off, but the code reports `unconfigured`. The README describes the code correctly.

## Why it matters

The t16 W1 is the only one that can surprise a user: a skill promises to ask before changing anything, then does not in one stage. The rest are wording and test strength.

## Suggested approach

One small contract, one implementer block and one review block. Decide I4 and I5 with the user first, because they are questions about intended behaviour, not defects.
