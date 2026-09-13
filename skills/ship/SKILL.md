---
name: ship
description: "Turn a finished work item into a pull request that GitHub actually links back to its issue. Reads the Work Item Brief for the branch, worktree, contract and issue id, runs /verify-before-done, composes the PR title from the modules the diff really touches, pushes from the tree that holds the commits, opens the PR, then verifies the Closing Link with verify_issue_link.py and performs at most ONE repair. Writes pr:, issue_link: and status: shipped back into the brief. Use when: user says /ship, 'open the PR', 'ship it', 'raise a pull request', or after /verify-before-done passes on a completed item. This is the last stage of the delivery chain."
user_invocable: true
---

# /ship — Pull Request and Closing Link

The final stage of the delivery chain. `/task` opened the work item and `/design-first`,
`/tdd-first` and the reviewers delivered it; this skill turns those commits into a pull
request and proves the tracker learned about it.

**Chain position:**

```
/task → /design-first → /tdd-first → reviewers → /verify-before-done → /git-commit → /ship
                                                                                      ^^^^^
```

## Context — why this skill exists

Opening a pull request is the easy half. The half that silently fails is the link back to
the work item, and it fails in a way that looks exactly like success.

**A `Closes #N` line in a pull-request body is a REQUEST for a link, never proof of one.**
GitHub declines the request without saying so when the reference is cross-repository, when
the pull request's base is not the default branch, or when several numbers are comma-joined
onto one keyword. The body still reads `Closes #12`, the pull request still merges, and the
issue stays open. `.claude/work-item-conventions.json` states this as
`resolvesToClosingLink: false`, and `verify_issue_link.py` exists because of a measurement:
five of the last twelve merged pull requests in the originating repository carried no
resolved link at all.

So this skill's real job is not "open a pull request." It is: open one, then **ask GitHub
whether the link resolved**, and treat the answer as the deliverable. The only admissible
proof is the forge's own resolved reference, which `gh pr view --json
closingIssuesReferences` reports — and which populates on OPEN pull requests, so the repair
can happen before merge rather than being discovered after it.

**Hard rule that governs the whole skill: never report a link you have not seen resolved.**
Writing `issue_link: closes` because the body says `Closes #N` reintroduces the exact defect
this skill exists to prevent.

## Step 0: Find the Work Item Brief

The brief is the input. Everything else is read from it, never re-derived from the chat.

1. If the user named one, use it.
2. Otherwise match the current branch against the `branch:` field of every brief in
   `.claude/work-items/`. That is the reliable key — the branch is what carries the commits.
3. If nothing matches, list the briefs whose `status:` is not `shipped` and ask.

**No brief → halt.** Do not improvise one, and do not open a pull request without one. A
brief written after the fact records what you did, not what was asked, and the acceptance
criteria are the only thing that makes the PR body checkable. Send the user to `/task`.

Read and hold: `id`, `url`, `repo`, `title`, `type`, `branch`, `worktree`, `contract`,
`partial`, `issue_link`, `status`.

**An `id:` reading of `UNKNOWN` or `unknown` halts here.** Those are the
`unresolvedIdTokens` in `work-item-conventions.json` → `issueLink`, and they mean nobody
filled the field in — which is not the same as "this work has no issue" and must never be
treated as one. Ask the user for the issue number, or for permission to set `id: none`.

## Step 1: Pre-flight

Four checks, in order. Each has produced a wasted pull request at least once.

### 1a. Stand in the tree that holds the commits

If the brief's `worktree:` field names a path, **the commits are there, not here.** Either
enter it (`EnterWorktree` with `path:`) or run every git command in this skill with
`git -C <worktree>`. Pushing from the parent tree pushes a branch with none of the work on
it, and the pull request opens empty.

Confirm before continuing:

```bash
git -C <tree> rev-parse --abbrev-ref HEAD     # must equal the brief's branch:
git -C <tree> status --short                  # uncommitted work is not shipped
```

### 1b. The branch must actually differ from the base

```bash
git -C <tree> fetch origin
git -C <tree> log --oneline origin/<base>..HEAD
```

An empty list means the implementation happened somewhere else — the classic outcome of a
contract implemented in the parent tree while the branch lived in a worktree. Halt and say
so; do not open an empty pull request.

### 1c. Never ship from the default branch

If `HEAD` is `master` or `main`, halt. `/ship` opens pull requests; it does not push to the
default branch, force-push, or merge. Those three are the user's, always.

### 1d. Run the verification gauntlet

Invoke `/verify-before-done`. **A failure halts the ship.** This is the last gate before the
work becomes visible to other people, and "the tests were already red before I started" is
not a reason to open the pull request — it is a reason to say so and stop.

## Step 2: Compose the pull-request title

**Issue titles carry ONE effort tag; pull-request titles carry EVERY touched module.** The
two conventions are different on purpose and both live in
`.claude/work-item-conventions.json`. Read them from there. Do not restate the tag lists in
this file — that file is the single source of truth, and duplicating it is how `/task` and
`/ship` drift apart.

```
[<MODULE>]...[<MODULE>] <Title>
```

The `<Title>` is the brief's `title:` field, which `/task` already stripped of its
`[EFFORT]` prefix. **Do not re-add the effort tag.** A pull request is described by what it
touches, not by why it was raised.

### Deriving the modules

From the diff, never from memory:

```bash
git -C <tree> diff --name-only origin/<base>...HEAD
```

Then, for each path, walk `prTitle.map` and collect every tag whose globs match. Emit them
in `prTitle.order`, never in discovery order.

Three traps, all of which have fired before:

- **`ignore.globs` first.** Those paths contribute no tag and must not trigger the unmapped
  prompt. They are not shippable source.
- **`**` crosses a directory separator; a single `*` does not.** `src/*` means the direct
  children of `src` and never a nested file. **Python's `fnmatch` disagrees** — there `*`
  crosses `/` — so a matcher built on it over-matches and tags modules the diff never
  touched. This is a verified failure mode, recorded in the conventions file itself. Use
  `pathlib.PurePath.match` or an explicit segment-wise matcher.
- **`atLeastOne: true`.** A title with no module tag is invalid.

### When a path matches nothing

`prTitle.map` ships as an **empty template** — its `order` and `map` arrays name a project's
own source layout, and nothing else in the generic asset set does. So in a repository that
has not populated it, *every* path is unmapped.

Do not invent a tag. Ask the user via `AskUserQuestion`, quoting the unmapped paths and
proposing tags derived from the top-level directories, then **write the accepted answer back
into `prTitle.map` and `prTitle.order`** in the same turn. That is the extension seam: the
map is meant to grow the first time each module is shipped, so the second pull request
touching that module needs no prompt.

## Step 3: Compose the pull-request body

Built from the brief, so the reviewer reads what was asked rather than what you remember:

```markdown
## What this delivers
<the brief's problem statement, one paragraph>

## Acceptance criteria
- [x] <each criterion from the brief, ticked only if genuinely met>

## Out of scope
<verbatim from the brief, so a reviewer does not ask for it>

## Design
Contract: <the brief's contract: path, or "none — <size> item, routed direct">

## Verification
<the actual /verify-before-done output: what ran, what passed, what failed and why
 that failure is acceptable. Never "all tests pass" without the numbers.>

## North-star alignment
<the brief's grade, verbatim>

Closes #<id>
```

Rules for the closing line:

- **One keyword per line** (`oneKeywordPerLine: true`). Comma-joining numbers onto one
  keyword is one of the ways GitHub silently declines the link.
- Same repository: `Closes #<n>`. Cross-repository: `Closes <owner>/<repo>#<n>`.
- **`partial: true` in the brief means `Refs #<n>`, not `Closes`.** The item is deliberately
  not completed by this pull request, and a closing keyword would shut a live work item.
- **`id: none` means no line at all.** That is a success path, not a defect — see Step 3.5.

An unticked acceptance criterion is not a blocker to shipping, but it **must** be visible in
the body with a one-line reason. Silently ticking everything is how an item is reported
delivered and reopened a week later.

## Step 3.5: Offer to open an issue when there is none

**Gate — both must hold:** the brief's id reading is `absent` (the `absentIdTokens` list in
`work-item-conventions.json` → `issueLink`, whose values are not restated here) **and** `gh`
is available and authenticated. Gate on the **id**, never on the `source:` string — that
field is free prose in practice.

A brief whose id is `unresolved` never reaches this offer; Step 0 already halted on it.
Offering to *create* an issue for work that may already have one is how duplicates get made.

**This point and `/task` Step 2.5 point 6 share their wording — one mechanism, two call
sites.** `/task` asked at intake; this is the second and last ask, at the moment the work
becomes visible. One `AskUserQuestion`, asked once, quoting the exact title and body:

```bash
gh issue create --title "[<TYPE>] <bare title>" --body "<problem statement + acceptance criteria>"
```

On accept, write `id:`, `url:` and `repo:` back into the brief **before** Step 4 composes
the body, so the closing line can reference it. On decline, `id: none` stays, the body
carries no closing line, and Step 4d's verdict will be `not-applicable` — which resolves to
`issue_link: none` and is a **success**, not a warning.

**Invent nothing.** If the brief's problem statement is empty, the offer does not fire.

## Step 4: Push and open the pull request

### 4a. Push from the right tree

```bash
git -C <tree> push -u origin <branch>
```

### 4b. Open it

Write the body to a file rather than passing it inline — a shell will mangle the backticks
and the checklist.

```bash
gh pr create --base <base> --head <branch> \
  --title "<composed title>" --body-file <path> --draft
```

Open as a **draft** unless the user asked otherwise, and say that you did. A draft is
reversible; a review request pinging five people is not.

### 4c. Capture the number

```bash
gh pr view --json number,url,isDraft
```

### 4d. Verify the Closing Link — the step that earns the skill its name

Never conclude this from the body you just wrote. Ask the forge:

```bash
py -3 .claude/scripts/verify_issue_link.py --brief <brief path> --pr <n> --json
```

The script performs **no mutation** of any GitHub object; it only reads. It returns a
`verdict` from a closed set of fifteen. Branch on it:

| Verdict | Meaning | Action |
|---|---|---|
| `linked` | GitHub reports a resolved closing reference | Success. `issue_link: closes` |
| `not-applicable` | No issue to link (`id: none`), or no conventions data file | Success. `issue_link: none` |
| `exempt-partial` | `Refs #N` on a deliberately partial item | Success. `issue_link: refs` |
| `absent-repairable` | No link, and the body can be repaired | **The one repairable row** — see below |
| `still-absent` | Repair was attempted and the link is still missing | HALT. `issue_link: unresolved` |
| everything else | `unverifiable`, `malformed-id`, `unresolved-id`, `issue-unreachable`, `issue-already-closed`, `pr-not-open`, `foreign-closing-ref`, `unexpected-closing-ref`, `not-linkable`, `refs-without-partial` | HALT. Report the `reason` and `remediation` verbatim |

**The repair loop runs at most ONCE** (`maxRepairAttempts: 1`). On `absent-repairable` the
result carries a `bodyDiff`. Apply it with a single `gh pr edit --body-file <path>`, then
re-invoke the script **with `--repair-attempted`** and take the second verdict as final:

```bash
gh pr edit <n> --body-file <repaired path>
py -3 .claude/scripts/verify_issue_link.py --brief <brief path> --pr <n> --repair-attempted --json
```

Do not loop further. A second failure is a real condition — usually a cross-repository
reference or a non-default base — and hammering `gh pr edit` will not change it.

**On any halting verdict the pull request stays open and the work is not lost.** Report the
verdict, the reason and the remediation, and say plainly that the tracker was not linked.
That is an honest partial delivery; a silent `status: shipped` is not.

## Step 5: Write the outcome back into the brief

Only from Step 4d's verdict, never from intent:

- `pr:` — the URL from Step 4c.
- `issue_link:` — `closes` | `refs` | `none` | `unresolved`, exactly as the verdict maps.
  **Never write `manual`.** That value exists in `linkStates` for a human who reconciled an
  issue by hand, and an agent writing it fakes a human action.
- `status:` — `shipped` only when Step 4d returned a non-halting verdict. On a halting
  verdict leave the previous status and record why.

Commit the brief update on the branch so the record travels with the work.

## Step 6: Worktree lifecycle, after the merge

Only after the pull request is merged, and only for a worktree this chain created:

```bash
git worktree remove .claude/worktrees/<wt>
git worktree prune
```

Never `rm -rf` the directory — that leaves stale metadata and git keeps the branch reserved.
Do not remove a worktree the user entered by path for their own purposes.

## Anti-patterns (halt immediately)

- **Reporting a link because the body says `Closes #N`.** The body is a request. Only the
  forge's resolved reference is proof, and `resolvesToClosingLink: false` says so in the
  conventions file.
- **Treating an `UNKNOWN` id as "no issue".** Absent and unresolved mean opposite things.
  Folding them together is how an unresolved field ships unlinked and is reported as success.
- **Writing `issue_link: manual`.** Reserved for a human.
- **Looping the repair.** One attempt, by contract.
- **Pushing from the parent tree when the brief names a worktree.** The pull request opens
  with none of the work in it.
- **Guessing module tags instead of deriving them from the diff**, or building the matcher
  on `fnmatch`, where `*` crosses `/` and silently over-matches.
- **Re-adding the `[EFFORT]` tag to the pull-request title.** Effort tags belong to issues,
  module tags to pull requests.
- **Ticking every acceptance criterion to make the body look clean.**
- **Opening the pull request when `/verify-before-done` failed.**
- **Merging, force-pushing, or pushing to the default branch.** None of the three belong to
  this skill.

## When NOT to use this skill

- Mid-flight work that is not finished — `/ship` is a terminal stage, not a checkpoint.
- A change with no work item and no intent to create one; use `/git-commit` and stop.
- Repositories whose forge is not GitHub. The verification step is `gh`-only, and without it
  the link cannot be proven — which, by this skill's own rule, means it must not be claimed.

## Skill integrations

- **Fed by** `/task`, which writes the `id`, `url`, `repo`, `contract`, `branch`, `worktree`
  and `partial` fields this skill reads back.
- **Runs** `/verify-before-done` at Step 1d as a hard gate.
- **Drives** `.claude/scripts/verify_issue_link.py` at Step 4d — the only production caller.
- **Shares** `.claude/work-item-conventions.json` with `/task`: that file owns the effort
  tags, the module map and the `issueLink` keyword data, and neither skill restates them.
- **Shares its Step 3.5 wording** with `/task` Step 2.5 point 6 — one mechanism, two call
  sites, so a free-text item is offered an issue at intake and once more at ship time.
- **Follows** `/git-commit`, which produces the commits this skill pushes.
