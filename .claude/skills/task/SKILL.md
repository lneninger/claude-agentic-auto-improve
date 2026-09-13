---
name: task
description: "Intake a work item — a GitHub issue (this project's tracker), or a Jira/ADO item, or a free-text request — and turn it into a normalized Work Item Brief at .claude/work-items/, with acceptance criteria, size classification, an issue-linked branch, and optionally an isolated parallel worktree branched from master. Resolves ambiguity with the user BEFORE any design happens, grades the item against the active north-stars at .claude/north-stars/ (capturing a new one via /north-star when the intake text carries an aspiration), then runs /design-first automatically in the same turn — the handoff is pre-authorized by the /task invocation, not a question to put to the user. Use when: user says /task, '/task #123', 'start on this issue', 'pick up issue 42', 'work on this in a worktree', pastes a GitHub issue URL, or begins any piece of tracked work. This is the front door of the delivery chain."
user_invocable: true
---

# /task — Work Item Intake

The first stage of the delivery chain. Everything downstream (`/design-first` → `/tdd-first` → review → `/verify-before-done` → `/ship`) assumes a **Work Item Brief** exists and is unambiguous. This skill produces it.

**Chain position:**

```
/task → /design-first → /tdd-first → reviewers → /verify-before-done → /git-commit → /ship
 ^^^^
```

## Context — why this skill exists

The project's chain has always started at `/design-first`, which takes "the user's request, verbatim" as its input. That is fine when the user types a well-formed request in chat. It falls apart when the work originates in a tracker: the issue's acceptance criteria, its labels, its linked issues, the comment thread that amended it, and its definition-of-done all live outside the conversation, and the contract gets written against a paraphrase instead of the source.

This skill closes that gap. It pulls the work item, normalizes it to one shape regardless of tracker, forces the unknowns into the open **before** a contract is drafted, and gives `/ship` the tracker reference it needs to link the PR back to the work item.

**Hard rule that governs the whole skill: never invent work-item content.** If the tracker is unreachable or a field is empty, the brief records `UNKNOWN` and Step 3 asks the user. A fabricated acceptance criterion produces a contract that satisfies nobody.

## Step 0: Parse the invocation

The argument may be any of:

| Argument shape | Interpretation |
|---|---|
| `#123`, bare `123`, `gh#123` | **GitHub issue number in the current repo** (this project's tracker) |
| `https://github.com/<owner>/<repo>/issues/123` | GitHub issue URL (may be a different repo — respect the owner/repo in the URL) |
| `ABC-1234` or an `atlassian.net/browse/...` URL | Jira issue key — see 1c |
| `AB#1234` or a `dev.azure.com/.../_workitems/...` URL | Azure DevOps work item — see 1c |
| Anything else (free prose) | Untracked request — skip to Step 1d |
| *(empty)* | List open issues assigned to the user (`gh issue list --assignee @me`) and ask which to pick up |

A bare number is a GitHub issue. This project tracks work in GitHub Issues; do not
interpret `1234` as an Azure DevOps id.

Record the raw argument verbatim in the brief. Do not normalize away information (a URL carries org/project that a bare id does not).

## Step 1: Resolve the work item

Run the cascade top-down and stop at the first tracker that both **matches the argument shape** and **is actually available**. Availability means the tool exists in this session — check the tool list; do not assume.

### 1a. GitHub Issues — the primary tracker for this project

Requires the `gh` CLI. Check it first:

```bash
gh --version && gh auth status
```

Then fetch the issue in one call:

```bash
gh issue view <number> --json number,title,body,state,labels,assignees,milestone,url,comments
```

Pull from the result:

- **Title** — split it into the `[EFFORT]` prefix and the bare title (see Step 2.5). Store them separately in the brief; the prefix is metadata, not part of the title.
- **Body** — where acceptance criteria live in GitHub (there is no dedicated field, unlike ADO). Parse task-list checkboxes (`- [ ]`) as candidate criteria.
- **Labels** — often carry type (`bug`, `enhancement`) and area. Use them as a signal for Step 4 sizing and for the affected-areas guess.
- **Milestone**, **assignees**, **state**.
- **Comments** — GitHub discussions frequently amend or override the original body. Read them; the newest constraint wins. If a comment contradicts the body, surface it in Step 3 rather than silently picking one.
- **Linked issues / PRs** — scan the body and comments for `#N` references and record them as related items.

> **`gh` is mandatory here — there is no fallback.** Whenever the tracker repository
> is **private** — as this one is — `WebFetch` on an issue URL
> returns 404 to an unauthenticated client. Get the repository from `gh repo view`
> or the `origin` remote; never hardcode a slug in a skill. If `gh` is missing or unauthenticated,
> say so plainly and go to Step 1d (free text), telling the user:
>
> ```
> winget install --id GitHub.cli
> gh auth login
> ```
>
> Do not install it yourself, and do not try to reach the GitHub API with a token
> scraped from the environment.

### 1b. No issue number given

If the user invoked `/task` bare, list candidates and let them choose:

```bash
gh issue list --assignee @me --state open --limit 20 --json number,title,labels
```

Fall back to `gh issue list --state open` if nothing is assigned. Present via `AskUserQuestion`.

### 1c. Other trackers (Jira / Azure DevOps)

Only if the argument is clearly Jira- or ADO-shaped (this project does not normally use them). Look for `mcp__*atlassian*__*` / `mcp__*jira*__*`, or `mcp__*azure*devops*__*` / `mcp__*ado*__*` tools, and pull summary, description, acceptance criteria, state, parent/epic link, and labels. If the matching MCP is not installed, go to Step 1d.

### 1d. Free text / unreachable tracker

Treat the argument as the task statement. Set `Source: free-text` (or `Source: <tracker> (unreachable)`) in the brief. Every field the tracker would have supplied becomes `UNKNOWN` and is resolved in Step 3.

This is a fully supported mode, not a degraded one — a well-clarified free-text brief beats a badly-parsed ticket.

## Step 2: Write the Work Item Brief

Write to `.claude/work-items/<YYYY-MM-DD>-<id-or-slug>.md`. Create the directory if needed. `<ProjectName>` is derived from the repo folder name, matching the `.claude/concepts/` convention already in use.

> Note: `~/.claude/tasks/` is the harness's own task storage (UUID-named). Never write briefs there.

```markdown
---
id: <123 | ABC-1234 | none>
title: <work item title, WITHOUT the [EFFORT] prefix>
type: <FEATURE | BUG | IMPROVEMENT | REFACTOR | PERF | SECURITY | DOCS | CHORE | SPIKE>
source: <github | jira | azure-devops | free-text>
repo: <owner/repo — for github, so /ship can target the right repo>
url: <direct link to the work item, or none>
labels: [<github labels, verbatim>]
milestone: <name or none>
project: <ProjectName>
branch: <feature/123-slug — filled in Step 5>
worktree: <path to the isolated checkout, or none — filled in Step 5>
north_stars: <one-line grade summary from Step 3.5, e.g. advances gex-ui-narrative-insights,
             orthogonal to the rest — or none when the register holds no active thought.
             Keep it colon-free; the brief parser reads any colon line as a new key.>
contract: <path — filled by /design-first>
pr: <url — filled by /ship>
partial: <true when the PR will deliberately NOT complete this item — /ship then
         uses Refs #N instead of a closing keyword. Omit entirely when false.>
issue_link: <unknown — filled by /ship Step 5 from Step 4d's verdict:
            closes | refs | none | unresolved. Never write 'manual' here;
            that value is reserved for a human reconciling an issue by hand.>
status: intake
created: <YYYY-MM-DD>
---

# <title>

## Problem statement
<Why this work exists. One paragraph, in domain language. From the tracker's
description field, or from the user. Never invented.>

## Acceptance criteria
- [ ] <verifiable statement — the condition under which this item is done>
- [ ] <...>

## Out of scope
- <explicitly excluded, so the contract does not creep into it>

## Known context
- Parent / epic: <link or none>
- Related items: <links or none>
- Affected areas (best guess, to be confirmed by the contract): <paths>

## North-star alignment
- <advances | conflicts | orthogonal>: `<north-star-slug>` — <one sentence saying how>
- <one line per active north-star; write `none — the register holds no active thought`
  when it is empty. A `conflicts` line MUST carry the user's justification verbatim.>

## Open questions from intake
- <question> → **Answer:** <filled in Step 3>

## Size
<XS | S | M | L | XL> — <one-line justification>

## Routing
<trivial → direct implementer | non-trivial → /design-first>
```

Fields you could not resolve are written as `UNKNOWN` — never guessed, never left blank.

## Step 2.5: Effort-type prefix

Every issue title carries exactly one effort-type prefix: `[FEATURE] Add trailing-stop to close evaluator`.

Read the canonical list from **`.claude/work-item-conventions.json`** → `issueTitle`. Do not hardcode the tag list here or in `/ship` — that file is the single source of truth, and duplicating it is how the two skills drift apart. If a tag is missing, add it there.

The three canonical types are `[BUG]`, `[IMPROVEMENT]`, `[FEATURE]`; the file also defines `[REFACTOR]`, `[PERF]`, `[SECURITY]`, `[DOCS]`, `[CHORE]`, `[SPIKE]`.

### Procedure

1. **Match the title** against the `pattern` in the conventions file.
2. **Already prefixed and valid** → split it. `title:` in the brief holds the bare title *without* the prefix; `type:` holds the tag. Keeping them separate means `/ship` can compose the PR title from modules without inheriting the effort tag.
3. **Missing, malformed, or a tag not in the list** → derive a proposal, then confirm:
   - GitHub labels are the strongest signal (`bug` → `BUG`, `enhancement` → `FEATURE` or `IMPROVEMENT`).
   - The body's language is the next signal: a reproduction section implies `BUG`; "it would be nicer if" implies `IMPROVEMENT`; "we need a way to" implies `FEATURE`.
   - `FEATURE` vs `IMPROVEMENT` is the pair that gets confused most: **did the capability exist before?** If yes, it is `IMPROVEMENT`.
   - Propose via `AskUserQuestion` with your reasoning. Never assign the type silently — the prefix drives how the work is triaged, and guessing wrong mislabels it permanently.
4. **Fix it at the source.** Once confirmed, correct the issue title in GitHub so the tracker and the brief agree:

   ```bash
   gh issue edit <number> --title "[<TYPE>] <bare title>"
   ```

   Ask before editing — you are modifying a shared artifact other people are looking at. If the user declines, keep the correct `type:` in the brief and note that the issue title is out of sync.
5. **Free-text work (no issue)** → still classify. The type flows into the brief and into the title of the issue point 6 offers to open.
6. **Offer to open the issue** (work item #39). Free-text work has always been a
   first-class mode here, but it produced briefs with `id: none`, so `/ship` correctly
   omitted the closing line and the tracker never learned the work happened — 4 of the
   14 briefs in this repo, including PR #40's.

   **Gate — both must hold:** the Brief Id Reading is `absent` — per the
   `absentIdTokens` list in
   [.claude/work-item-conventions.json](../../work-item-conventions.json) →
   `issueLink`, whose values are **not** restated here (INV-8) — **and** `gh` is
   available and authenticated. Gate on the **id**, never
   on the `source:` string — that field is free prose in practice
   (`2026-08-26-trading-journal-recording-playback.md:5` reads
   `github (issue opened at intake from a free-text request)`).

   A brief whose id is `unresolved` (the `unresolvedIdTokens` list in `issueLink`)
   does **not** reach this offer. It is not
   "no issue", it is "nobody filled this in", and offering to *create* an issue for work
   that may already have one is how duplicates get made.

   **Action.** One `AskUserQuestion`, asked once (INV-5), quoting the exact title and body
   that would be created:

   ```bash
   gh issue create --title "[<TYPE>] <bare title>" --body "<problem statement + acceptance criteria from the brief>"
   ```

   On accept, write `id:`, `url:` and `repo:` back into the brief — Step 5b's
   `gh issue develop` then has a number to link the branch to, which is why this lands
   here and not in Step 1d.

   **Invent nothing.** If the brief's problem statement is empty, the offer does not fire;
   there is nothing honest to put in the issue body.

   **On decline:** `id: none` stays and the run continues normally — declining is a
   **success** path, not an error and not a warning. Note in the brief that `/ship`
   Step 3.5 will ask once more at ship time.

   **This point and `/ship` Step 3.5 share their wording — one mechanism, two call
   sites.** Creating an issue is modifying a shared artifact, so the same
   ask-before-you-touch-it rule as point 4 governs it.

**Exactly one prefix.** A change that is both a fix and an enhancement is two issues, not `[BUG][FEATURE]`. Multi-tagging belongs to PR titles (modules), never issue titles (effort).

## Step 3: Clarify before designing

This is the step that earns the skill its place. Read the brief you just wrote and interrogate it:

1. **Is every acceptance criterion verifiable?** "Works well" and "is fast" are not. Push each one to a form a test could assert. If the tracker's criteria are vague, that is a finding, not something to smooth over.
2. **Is there a criterion for the failure path?** Most tickets specify only the happy path.
3. **Does anything conflict with a project rule?** Check `CLAUDE.md` for the areas the item touches — an issue asking for something the architecture rules forbid must surface now, not at review.
4. **Does this touch a safety-critical path?** Match the item against the `safety-critical.roots`, `auth.roots` and `migration.root` slots of `.claude/project-profile.md`, plus any live external-action path those roots protect. If yes, note in the brief that `/tdd-first` is **mandatory with no opt-out** and that a domain reviewer will be required.
5. **Are there `UNKNOWN`s left?**

Use `AskUserQuestion` to resolve every gap. Batch related questions into one call rather than interrogating one at a time. Append each answer under `## Open questions from intake` and update the affected sections in place.

**Do not proceed to Step 4 while any acceptance criterion is unverifiable or any `UNKNOWN` remains.** Guessing here is exactly the failure this skill exists to prevent.

## Step 3.5: Grade the item against the north-stars

`.claude/north-stars/` is this project's WHAT-WE-WANT register. Until now it was read in exactly one place — `data-architect` Step 0.5, which only runs under `/design-first`. That left two holes this step closes. An XS/S item never reaches a contract, so it was never graded against the direction at all. And an aspiration the user voiced during intake was lost unless they separately remembered to type `/north-star`.

Run this step for every item, whatever its size, after Step 3's clarification and before Step 4 sizes it. A conflict can change both the scope and the route, so the grade has to land first.

### 3.5a. Read the active register

Scan `.claude/north-stars/` for every `.md` file whose `**Status:**` line reads `active`. For each one, read the same three sections `data-architect` reads: **Aspiration**, **Anti-patterns**, **Suggested next steps**. The Anti-patterns section is the load-bearing one — its backticked snippets are the concrete shapes that signal a contradiction.

If the directory is missing or holds no active thought, write `north_stars: none` in the brief and go to Step 4. Nothing else here applies.

### 3.5b. Grade the work item

For each active north-star, pick exactly one relationship. Use the same three words `data-architect` Step 0.5 uses, so the two grades can be compared instead of translated:

- **advances** — the item implements one of that north-star's Suggested next steps, or otherwise moves the codebase toward the aspiration.
- **conflicts** — the item introduces one of its Anti-patterns.
- **orthogonal** — neither.

Record every grade in the brief's `## North-star alignment` section, one line each, with a sentence saying how, and summarize it in the `north_stars:` frontmatter field. "Orthogonal to all of them" is a valid and common outcome — write it down anyway. Silence reads as a skipped step, not as a clean bill.

### 3.5c. Surface a conflict before sizing, not after

A `conflicts` grade is a user decision, not a note to file and walk past. Raise it through `AskUserQuestion` — fold it into the same call that closes any remaining Step 3 gaps — quoting the anti-pattern the item would introduce and the north-star it belongs to. Three answers are legitimate:

- **Rescope the item** so the anti-pattern is avoided. Amend the acceptance criteria in the brief.
- **Accept the conflict.** Record the user's justification verbatim under `## North-star alignment`. For M/L/XL that text is what `data-architect` turns into the contract's `## Acknowledged conflict with north-star` section; without it `contract-critic` blocks the contract on its north-star checklist item, so an unrecorded acceptance simply buys a round trip later.
- **The north-star is stale** — the aspiration has been overtaken by events. Do not edit or retire it from here. Say so plainly and let the user run `/north-star` to supersede it.

### 3.5d. Capture a new aspiration when the intake surfaces one

Work items arrive carrying more than the work. An issue body, a comment thread, or the user's own framing at intake often states a direction — "eventually the operator should never author this by hand", "indicators should come from models, not hand-tuned constants" — sitting right next to the concrete request.

When that happens, invoke `/north-star` through the `Skill` tool with the user's own wording, before you continue the intake. **This is pre-authorized by the `/task` invocation on the same terms as the Step 6 handoff** — it is not a separate decision to put to the user, and `/north-star` runs its own clarifying questions to refine the aspiration and its anti-patterns.

Then keep the two apart: the aspiration becomes a north-star file, the concrete request stays the work item, and the brief cites the new slug under `## North-star alignment`. Do NOT fold the aspiration into the acceptance criteria. An item that must satisfy a long-horizon direction before it counts as done never gets done.

Two boundaries:

- **Never convert the work item itself into a north-star.** `/north-star` refuses concrete tasks by design, and a ticket does not become an aspiration by being ambitious.
- **Never invent an aspiration the user did not voice.** This step captures direction that is already in the text. It does not editorialize the project's direction on the user's behalf.

### 3.5e. Carry the grade forward

- **M / L / XL** — the grade travels to `/design-first` on the Step 6 `NORTH_STARS:` line. `data-architect` Step 0.5 verifies it against the register instead of deriving it cold, and escalates to the user where it disagrees.
- **XS / S** — the item skips `/design-first` entirely, so the brief's `## North-star alignment` section is the only north-star gate it will ever pass. Whatever is written there is the whole record.

## Step 4: Size and route

Classify, and record the justification in the brief:

| Size | Shape | Route |
|---|---|---|
| **XS** | Typo, log line, comment, config bump, pure rename | Direct edit — the `concept-gate.py` trivial allowlist covers it. No contract. |
| **S** | One-branch bug fix in one function, no new data shape | Usually `/debug` → `/tdd-first`. Contract only if it touches a mechanism. |
| **M / L / XL** | Any new feature, entity, endpoint, component, field, migration, or multi-file structural refactor | `/design-first` — mandatory |

Apply `/design-first` Step 1's own rule when torn: **if unsure, treat as non-trivial.** A short contract is cheaper than a parallel data shape.

**Record the route, then take it.** The size decides which skill runs next; it is not a proposal to put to the user. Step 6 carries the handoff and its pre-authorization.

Set `status: clarified` in the frontmatter.

## Step 5: Workspace — branch, optionally a parallel worktree

**Pre-flight.** Read the current branch first. **Detached HEAD, mid-rebase, or mid-merge → halt.** Tell the user to resolve it before any branch or worktree is created; both paths below produce garbage from an unresolved index.

### 5a. Pick the workspace shape

| Shape | What you get | Use when |
|---|---|---|
| **Branch in place** *(default)* | A new branch in the current working tree | One item at a time, tree is clean, nothing else running |
| **Branch + parallel worktree** *(opt-in)* | A second checkout on disk branched from `origin/master`; the current tree keeps its branch and its uncommitted work | Anything below |

Offer the worktree — never assume it. Ask via `AskUserQuestion` when any of these hold, and honour an explicit request ("do this in a worktree" / "just branch here") without asking at all:

- Another work item is in flight on the current branch, or the tree holds unrelated WIP.
- Parallel or background sessions will run against this repo.
- The item is long-running, broad, or risky (migrations, cross-cutting refactor, live order flow).
- The user is currently standing on a feature branch and this is a *new*, unrelated item — branching here would stack the new work on top of unreviewed commits.

Naming is identical for both shapes. Follows this repo's convention (`feature/rbac-role-permission-system`), with the issue number in front when one exists:

- `feature/<issue#>-<kebab-slug>` — e.g. `feature/42-role-permissions`
- `fix/<issue#>-<kebab-slug>` for issues labelled `bug`
- Drop the number prefix only for free-text work with no issue

### 5b. Branch in place

- **On `master` / `main`** → propose the branch and create it after confirming. When `gh` is available, let GitHub create the link itself:

  ```bash
  gh issue develop <number> --name feature/<number>-<slug> --base master --checkout
  ```

  This registers the branch against the issue in GitHub's UI (a "linked branch"), which plain `git switch -c` does not do. Fall back to `git switch -c <name>` if `gh` is missing or the command fails.
- **Already on a feature branch** → keep it *only if this work genuinely belongs there* (a follow-up to the same item). Confirm with the user. If it is a new item, this is the worktree case — go to 5c rather than stacking on unreviewed commits.

### 5c. Branch + parallel worktree from master

**The base is the entire point of this shape. Get it wrong and the isolation is worthless.**

1. **Base is always freshly-fetched `origin/master`.** Never local `master` (it is routinely stale), never the current `HEAD`.
2. **Do not create the worktree with `EnterWorktree`'s `name:` form.** That form picks its base from the `worktree.baseRef` setting — `fresh` means `origin/<default-branch>`, but `head` means *your current local HEAD*. If the setting is `head` and you are standing on a feature branch, you silently seed the new item with that branch's commits. Create the tree with an explicit `git worktree add` naming the base, then enter it by path.
3. **A worktree does not carry uncommitted changes.** The current tree keeps them. If this item depends on WIP sitting in the parent tree, a worktree is the wrong tool — commit or finish that work first.
4. **Git refuses to check out one branch in two worktrees.** One worktree per work item, and the directory name follows the convention below so `git worktree list` reads as a dated, classified list of in-flight items.
5. **The stash stack is shared across worktrees.** A `git stash` in one tree is visible in all of them — never use the stash to move work between them.

**Name the directory `<YYYYMMDD>-<action>-<slug>`** — written `<wt>` in the commands below. Both prefixes are required:

- **`<YYYYMMDD>`** — the date the worktree is cut, no separators (e.g. `20260822`). This is what makes `.claude/worktrees/` sort chronologically and makes a tree that has been sitting abandoned for weeks obvious on sight.
- **`<action>`** — the main action the item performs: `feature`, `bug`, `infra` (others where none of those fit). Classify the *work*, not the file types it touches — a bug whose fix happens to add a migration is still `bug`.
- **`<slug>`** — the same kebab slug as the branch, issue number included when there is one.

Examples: `20260822-bug-18-mobile-dashboard-empty-selection`, `20260821-feature-11-centralized-file-storage`, `20260818-infra-broker-capability-base`.

The directory name and the branch name are deliberately **not** identical. The branch keeps GitHub's `feature/` / `fix/` prefixes because `gh issue develop`, the linked-branch UI and `/ship` all depend on them; the directory carries the date and action because it is what a human reads in `git worktree list`. Record the full worktree path in the brief's `worktree:` field so the two are never guessed at from each other.

**Create it.** With `gh` (keeps the issue↔branch link and does *not* move the current checkout — note the absence of `--checkout`):

```bash
gh issue develop <number> --name feature/<number>-<slug> --base master
git fetch origin
git worktree add .claude/worktrees/<wt> \
  --track -b feature/<number>-<slug> origin/feature/<number>-<slug>
```

Without `gh`, or for free-text work with no issue:

```bash
git fetch origin master
git worktree add .claude/worktrees/<wt> -b <branch-name> origin/master
```

**Verify the base before writing the brief.** A fresh branch off master has the same tip as master — prove it rather than assuming:

```bash
git rev-parse origin/master
git -C .claude/worktrees/<wt> rev-parse HEAD          # must match the line above
git -C .claude/worktrees/<wt> rev-parse --abbrev-ref HEAD   # must be the new branch
```

If the two SHAs differ, the worktree was seeded from the wrong ref. Remove it and redo — do not "fix it later with a rebase."

**Keep it out of the parent's `git status`.** A worktree nested under the repo is not ignored automatically. Confirm `.claude/worktrees/` is listed in `.gitignore` (or `.git/info/exclude`) and add it if not; otherwise the second checkout shows up as a large untracked directory in every later status and diff.

**Enter it only if this session continues the work.** Use the `EnterWorktree` tool with `path: .claude/worktrees/<wt>` — the path form enters the tree you just built rather than creating another one, and `ExitWorktree` will not delete a path-entered worktree, which is what keeps it available to parallel sessions. If instead this tree is being prepared for a *different* session or a background job, stay where you are and hand the path over.

**Open the worktree in its own VS Code window.** The repository's `<project.name>.code-workspace` file — `project.name` is a slot in `.claude/project-profile.md` — is git-tracked, so `git worktree add` already placed a correct copy at the worktree root. Open **that** copy, never the parent tree's:

```bash
code -n ".claude/worktrees/<wt>/<project.name>.code-workspace"
```

`-n` forces a **new** window instead of reusing the current one, so the parent tree's window stays open beside it — which is the entire point of a parallel worktree.

**The copy works untouched, and there is an invariant that keeps it that way.** VS Code resolves each `folders[].path` against the directory holding the workspace file, so:

- **Every folder INSIDE the repo is relative on purpose** — the repository root `.` and the `frontend.root-container` slot's directory among them. They follow whichever tree the file sits in, so in a worktree they resolve to *that* worktree. Never make these absolute; that is what would pin every copy back to the parent tree.
- **Every folder OUTSIDE the repo must be absolute.** A relative `../sibling` resolves from `<repo>/.claude/worktrees/<wt>/`, where `..` is `.claude/worktrees/` — not the repo's parent. It silently renders as a missing folder. This is a real bug that was fixed on 2026-08-22: a sibling folder written as `../<sibling>` had to become its full absolute path.

VS Code does **not** do variable substitution in `folders[].path`, so absolute is the only mechanism available for the outside-the-repo case. **Never hand-edit the workspace file inside a worktree** — it is tracked, so the edit rides along in every commit and pollutes the PR diff with machine-local paths. If a copy is wrong, fix the root file and let the correction reach worktrees through master.

Verify a new tree's copy resolves before handing it off:

```bash
py -3 -c "import json,pathlib,sys; h=pathlib.Path(sys.argv[1]); ws=json.load(open(next(h.glob('*.code-workspace')),encoding='utf-8')); [print(('OK   ' if (p if (p:=pathlib.Path(f['path'])).is_absolute() else h/p).exists() else 'BROKEN '), f['path']) for f in ws['folders']]" ".claude/worktrees/<wt>"
```

**Lifecycle.** After `/ship` merges the PR:

```bash
git worktree remove .claude/worktrees/<wt>
git worktree prune
```

Never delete the directory by hand — that leaves stale worktree metadata behind and git keeps reserving the branch.

### 5d. Record it

Write the branch name into the brief's `branch:` field and the worktree path (or `none`) into `worktree:`. `/ship` reads both back — it must push the branch from the tree that actually holds the commits.

## Step 6: Hand off to /design-first

**This handoff is automatic and pre-authorized. Do not ask for permission, and do not hand the command back to the user to type.** Invoking `/task` on an M/L/XL item *is* the request for the chain this skill fronts — the contract is `/task → /design-first → …`, declared in the first line of this file. Stopping at Step 5 to print a `/design-first` command the user must run themselves delivers an intake and calls it a delivery. Run it in the same turn that finished Step 5.

**This authorization extends to the agents `/design-first` dispatches on its own** — `data-architect` at its Step 2 and `contract-critic` at its Step 2.5, both spawned via the `Agent` tool. A standing "do not spawn agents unless the user asked for it" rule is *satisfied* here, not overridden: the user asked when they typed `/task`. Do not treat those dispatches as a separate decision requiring its own approval.

What still belongs to the user is unchanged: `/design-first` Step 3 presents the draft contract and resolves every Open Question and critique BLOCKER through `AskUserQuestion`, and only the user flips `Status` to `approved`. The chain runs itself up to that gate — it does not run past it.

**Stop and ask only when:**

- the user explicitly scoped the request to intake ("just write the brief", "don't design it yet", "size this for me"); or
- Step 3 did not actually finish — an acceptance criterion is still unverifiable, or an `UNKNOWN` is unresolved. Then the handoff is not due yet, and the fix is to finish Step 3, not to ask whether to continue.

For M/L/XL, invoke `/design-first` via the Skill tool, passing the **brief path** as the authoritative input rather than a paraphrase:

```
TASK: <brief title>
CONTEXT: Work Item Brief at .claude/work-items/<file>.md — read it first;
         it carries the acceptance criteria, out-of-scope list, and intake answers.
         Do not re-derive requirements from the chat.
WORK_ITEM: <id> (<url>)
NORTH_STARS: <the Step 3.5 grades, verbatim from the brief — or 'none'.
         Verify them against the register; do not re-derive them cold. Escalate
         to the user where your grade differs from intake's.>
```

The data-architect must treat the brief's acceptance criteria as requirements input to the contract. When the contract is written, write its path back into the brief's `contract:` field and set `status: designing`.

**If Step 5c created a worktree, settle the working directory before handing off.** Either enter the worktree (`EnterWorktree` with its `path`) or state the path explicitly in the `CONTEXT:` block above so whoever implements works inside it. A contract implemented in the parent tree while the branch lives in the worktree produces exactly one outcome: a branch with no commits on it, discovered at `/ship`.

For XS/S, skip `/design-first` and go straight to the implementer (or `/debug` for a bug), but still keep the brief — `/ship` uses it to write the PR body. That transition is equally pre-authorized: the size classification already made the call, so route into it rather than asking. The brief's `## North-star alignment` section travels with the item — for XS/S that grade is the only north-star check the work will get, which is why Step 3.5 runs before the route is taken rather than after.

## Status lifecycle

The `status:` frontmatter field tracks the item through the chain. Each stage updates it:

`intake` → `clarified` → `designing` → `implementing` → `verifying` → `shipped`

## Anti-patterns (halt immediately)

- **Inventing acceptance criteria** because the tracker field was empty. Ask.
- **Paraphrasing the issue into the contract** instead of passing the brief. The paraphrase drops the criteria that were not obvious to you — especially ones added in comments.
- **Skipping Step 3 because the ticket "looks clear."** Tickets that look clear are the ones that ship the wrong thing.
- **Creating the branch before clarifying.** A branch named after a misunderstood ticket outlives the misunderstanding. The same applies to the worktree — a whole checkout named after a misread ticket is worse.
- **Seeding the worktree from the current feature branch.** The base is freshly-fetched `origin/master`, always, verified by SHA. A tree seeded from a half-finished branch inherits its commits, its bugs, and its review surface — and the isolation you asked for is gone.
- **Creating a worktree and then implementing in the parent tree.** The branch ends up empty. Enter the worktree or hand its path to the implementer.
- **Reaching for a worktree to escape uncommitted work you actually need.** Worktrees do not carry WIP. Commit it or finish it.
- **`rm -rf` on a worktree directory.** Use `git worktree remove` then `git worktree prune`, or git keeps the branch reserved and the metadata stale.
- **Routing an M-sized item to a direct edit** to save the contract. The `concept-gate.py` hook will block the write anyway.
- **Stopping after Step 5 to ask whether to run `/design-first`.** Step 4 set the route and Step 6 pre-authorizes the handoff, so the question strands a clarified brief with no contract — and printing the command for the user to type themselves is the same failure with extra steps. Clarify in Step 3, then chain.
- **Sizing an item before grading it against the north-stars.** Step 3.5 runs first for a reason: an XS/S route skips `/design-first`, and with it the only other place the register is ever read. Grade it, then size it.
- **Recording a `conflicts` grade without asking.** The conflict is the user's call to make. Noting it in the brief and proceeding hands `contract-critic` a blocker the user never saw.
- **Folding a captured aspiration into the acceptance criteria.** The north-star is the long horizon and the work item is this week. Merging them produces an item that cannot be finished.
- **Writing the brief anywhere but `.claude/work-items/`.** As of 2026-08-22 the brief IS committed to the repo — that is deliberate, so a work item travels with the branch instead of living only on one workstation. It is still not a *product* deliverable: it does not ship to users and it does not belong under `docs/` or `src/`.

## When NOT to use this skill

- Pure research or code-reading questions with no deliverable.
- Mid-flight work already past intake — pick up where you left off; do not re-intake.
- Ad-hoc exploration where no work item exists and none is wanted.

## Skill integrations

- **Hands off to** `/design-first` (M/L/XL) or `/debug` (bugs) or a direct implementer (XS).
- **Invokes** `/north-star` at Step 3.5d, when the intake text carries an aspiration alongside the concrete request. That invocation is pre-authorized by `/task` itself.
- **Reads** `.claude/north-stars/` at Step 3.5 and writes the grade into the brief, which `data-architect` Step 0.5 then verifies rather than re-derives. `/north-star-review` remains the only thing that maintains a north-star's Current gap and Suggested next steps sections — this skill never edits a north-star file.
- **Feeds** `/ship`, which reads the brief's `id`, `url`, `contract`, `branch`, and `worktree` fields to build the PR body, link back to the tracker, and push from the tree that holds the commits.
- **Composes with** `superpowers:using-git-worktrees` when the user wants the isolation rationale rather than this skill's concrete recipe.
- **Complements** `/list-contracts` — that skill shows design state, this one shows intake state.
