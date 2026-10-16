---
id: none
title: Sub-issue titles carry their parent reference, and sub-issues can be hidden from the list
type: IMPROVEMENT
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: none
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/subissue-title-parent-ref
worktree: .claude/worktrees/20261015-feature-subissue-title-parent-ref
north_stars: none - the register holds no active thought
contract: .claude/concepts/2026-10-15-subissue-title-parent-ref.md
pr: none
issue_link: unknown
status: implementing
created: 2026-10-15
---

# Sub-issue titles carry their parent reference, and sub-issues can be hidden from the list

## Problem statement
Raw request: "check the issues for github repo for StockToolScalpingMachine and verify that there are been creating many issues that are difficult to follow. I need more specification like Parent reference in the title. Also any option to hide sub-issues from the list".

Evidence gathered at intake (read-only, 2026-10-15, repo `lneninger/StockToolScalpingMachine`): of the 100 most recent open issues, 37 are sub-issues of one parent (#638). Their titles read `[PERF] Screener (dotnet-backend-architect)` or `[PERF] Gate (test-strategy-critic) - t16-gate`. Nothing in the title names the parent, so a reader of the flat issue list cannot tell which work item a sub-issue belongs to. The titles come from the plugin's parent-aware intake (`skills/task/references/parent-aware-mode.md`), which builds `[<TYPE>] <bare title>` and nothing more.

On hiding: GitHub already supports it. `gh issue list --search "no:parent-issue"` (equivalently `-has:parent-issue`) returned 66 of the open issues in that repo, so sub-issues drop out. No label or new mechanism is needed to hide them, but nothing in the plugin tells the operator about the filter.

## Acceptance criteria
- [ ] The conventions file `.claude/work-item-conventions.json` declares the sub-issue title format (single source of truth, like the existing `issueTitle` block). The format, chosen by the user on 2026-10-16, puts the parent and the sub-task right after the effort tag: `[PERF] P:#638 ST:16 - Fix Earnings Index (dotnet-backend-architect)`, where `P` is the parent issue and `ST` is the sub-task. The title must explain itself, so the legend for `P` and `ST` is declared once in the conventions file and printed wherever the format is documented.
- [ ] A sub-issue title built in Parent-aware mode still matches the existing `issueTitle.pattern` (exactly one effort tag first).
- [ ] Parent-aware mode in `/task` builds the title from that declared format using `PARENT_ISSUE`, and says so in `parent-aware-mode.md`; the format is not restated inline in a second place.
- [ ] Failure path: if the parent number is missing or not a positive integer, the create is refused with a named reason; it never falls back to a title without the parent reference.
- [ ] A test asserts the composed title for a normal case, a parent number with the leading `#` already typed, and the refusal case.
- [ ] The plugin documents how to hide sub-issues from a list (`no:parent-issue`) and how to list one parent's children (`parent-issue:<owner>/<repo>#<n>` or the `gh issue view <n> --json subIssues` command), in the `/flow` skill where the operator first meets sub-issues.
- [ ] The plugin version is bumped, and the change is mirrored wherever the repo carries a second copy of the touched files.

## Out of scope
- Retitling the 37 sub-issues that already exist in StockToolScalpingMachine. That edits shared issues in another repository; it is a separate decision for the operator after this ships (offered as a follow-up).
- Changing how a sub-task's bare title is derived from its handoff heading (names such as `Gate (x) - t16-gate`).
- A new `sub-task` label. The native `no:parent-issue` filter already hides sub-issues without a new mechanism.
- Syncing the new version into StockToolScalpingMachine's vendored copy. That follows the release, as with earlier fixes.

## Known context
- Parent / epic: none
- Related items: StockToolScalpingMachine issues #638 (parent) and #655-#670 (its sub-issues)
- Affected areas (best guess, to be confirmed by the contract): `.claude/work-item-conventions.json`, `skills/task/references/parent-aware-mode.md`, `skills/task/SKILL.md`, `skills/flow/SKILL.md`, `.claude/scripts/` (a small title-composing helper plus its test), plugin manifest version

## North-star alignment
- none - the register holds no active thought

## Open questions from intake
- Which title shape? → **Answered by the user (2026-10-16):** `[TYPE] P:#<parent> ST:<k> - <bare title>`, replacing the intake assumption below. `ST` is read as the sub-task's position in the parent's plan, since the sub-issue's own number does not exist when the title is composed; this reading is OQ-4 in the contract, awaiting confirmation. Original assumption: `[TYPE] #<parent> - <bare title>`. The parent number sits right after the effort tag so it is the first thing read after the type, GitHub auto-links the `#638`, and the existing title pattern still matches. Alternative `[TYPE] <bare> (parent #638)` rejected because it pushes the reference to the far end of a long title, where lists truncate it.
- Should the parent's title also appear? → **Assumed:** no. A number is stable, a title is long and can be edited. The number links to it.
- Should we add a label to hide sub-issues? → **Assumed:** no; the native filter does it.
- Open a tracker issue for this work? → **Assumed:** no (id none). `/ship` Step 3.5 will ask once more at ship time.

## Size
M - a new shared title-format rule in the conventions file, read by two skills, with a helper and tests. It adds a rule to a file other skills read, so it goes through the design stage.

## Routing
non-trivial → /design-first

## Run log

- 2026-10-16: Design approved (title shape `P:#<parent> ST:<k>` chosen by the user). Test-first stage and implementation done; the helper's test file passes every check and the neighbouring suites pass (doctor and manifests suites fail only the same tests as clean master).
- Review stage failed three times and the retry budget is spent. Pass 1: version clash with master, shell variables lost between calls, unquoted placeholders, format copied into the flow note. Pass 2: a parent written `#638` crashed the verifier after the issue was created. Pass 3 (below).
- Pass 3 findings still open:
  - BLOCKER: master moved on (pull request #53 raised it to 0.9.1). Rebase onto the new master tip, raise all five version entries to 0.9.2, change the README note to "before 0.9.2", and update the contract lines that still say 0.9.1.
  - Shell block trims whitespace everywhere in the parent number (`tr -d`); trim the ends only so the helper stays the one validator. Same in the repair block and for the sub-issue number.
  - Helper crashes with a traceback when `effortTypes` is null or not a list; treat it as a named refusal.
  - Placeholders for numbers and the effort tag should be single-quoted, not double-quoted.
  - `${CLAUDE_PROJECT_DIR:-.}` in the block makes the helper's "root not determinable" refusal unreachable; amend the contract's I-6 wording or drop the fallback.
  - Contract wording: three lines disagree about the `subIssue` keys (legend included); the `conventions-missing` row omits the missing-pattern case; I-1 holds only for the shipped format.
  - Not recorded anywhere yet: the `parent-issue:` search qualifier returned 0 results on a real parent (#638) and was dropped from the flow note. Put that in the pull request description.
- Next: one more fix round (tests for the cases above first), then the verification stage, commit and draft pull request. Nothing has been pushed to a pull request.
