---
id: none
issue_offer: declined
title: Finished runs leave background sessions running, and the delivery cleanup cannot say which session holds a worktree folder
type: IMPROVEMENT
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: none
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: infra/cleanup-names-the-session-holding-a-worktree
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261018-infra-cleanup-names-the-session-holding-a-worktree
north_stars: none
contract: .claude/concepts/2026-10-18-cleanup-names-worktree-holder.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/460 (draft)
issue_link: none (no tracking issue was opened, so the pull request closes none)
status: shipped
created: 2026-10-18
---

# Finished runs leave background sessions running, and the delivery cleanup cannot say which session holds a worktree folder

## Problem statement
On 18 October 2026 the delivery cleanup (`cleanup_delivered.py`) for pull request 65 left a worktree and its merged branch behind. Its report said only `deferred: standing-tree` and `in-use`. Two Claude Code sessions held the folder: the session that did the work, which had finished but was still running in the background, and the `/flow` session that ran the cleanup. Windows will not delete a folder that is some process's working folder. Finding the holders took two hand-written scripts, a read of the background service log and a search of the documentation.

Cause found: pressing the left arrow on an empty prompt sends a session to the background, where it keeps running until it is stopped. The documentation says `/stop` ends a session, `claude stop <id>` stops one by id, and `/exit` only detaches an attached session. The background service ends a job session only after it has been idle for hours. Nothing in this plugin tells the user to stop a finished session, and nothing in the cleanup report says which session is in the way.

## Acceptance criteria
- [ ] When the cleanup defers or leaves a worktree because the folder is some process's working folder (the outcomes `standing-tree` and `in-use`), the item in the Cleanup Report carries a list of holders. The holders are the Claude Code sessions whose working folder is inside that worktree, found by asking Claude Code's own session list (`claude agents --json --all`, a documented read-only command that reports for each session its id, working folder, name and state). Each holder shows the session id, the session name and its state. A test that supplies a recorded session list, with one session inside a temporary worktree, shows the holder named.
- [ ] The one-line report names each holder and, for each Claude Code session, prints the exact `claude stop <session id>` command. That command is never cut by the line's length limit, on the same rule as the existing finish command.
- [ ] The detection only reads. The cleanup never stops, signals or changes a process, and a test proves no such call is made.
- [ ] Failure path: when the session list cannot be read (the `claude` command is missing, it fails, or its answer is not the expected list), the report says plainly that it cannot tell which session holds the folder and gives the reason. The outcome stays deferred or left, exactly as today. A tree is never reported as removed or free because the read failed.
- [ ] The report says plainly that the session list shows Claude Code sessions only, so a terminal, editor or other program holding the folder is not named, and the line "cannot rule out other programs" appears whenever no session is found for a folder that is still in use.
- [ ] The detection adds no new dependency (it runs the `claude` command with the Python standard library) and never reads another process's memory. The session that is running the cleanup is labelled as this session and gets no stop command, because the existing finish command already covers it.
- [ ] A worktree that is not held keeps today's behaviour and report text unchanged, and the existing rule against forcing removal keeps its test. All existing cleanup tests still pass.
- [ ] The closing message of `/task`, `/flow` and `/advance` says plainly that the work is delivered and that this session should be ended with `/stop` before the delivery cleanup runs. A check proves the sentence is present in each of the three skill files.
- [ ] The plugin copy is made and the plugin version is raised, following the repository's CONTRIBUTING rules for a plugin change.

## Out of scope
- A session stopping itself automatically at the end of a run. That is an opt-in follow-up, because it must survive the cleanup running afterwards from a separate process.
- Changing Claude Code's idle timer, the left-arrow behaviour, or anything inside Claude Code itself.
- Stopping any session from the cleanup. The cleanup names the holder and prints the command, and the user runs it.
- Reporting problems with the Claude Code documentation (the eight-hour job limit against the documented one hour). That goes through Claude Code's own feedback command.

## Known context
- Parent / epic: none
- Related items: pull request 65 (worktree removal over identical untracked files, merged), pull request 66 (its records, merged). The standing-tree deferral comes from pull request 65's contract and is unchanged in what it decides; only what it reports changes.
- Evidence kept in this session: the background service log at `C:\Users\lneni\.claude\daemon.log` (lines `bg spawned <id> (fleet)`, `bg retire <id>: idle-prompt, idle 8h`) and two scripts that read each process's working folder from its memory (PEB, the process environment block).
- Affected areas (best guess, to be confirmed by the contract): `.claude/scripts/cleanup_delivered.py` and `.claude/scripts/tests/test_cleanup_delivered.py`; `skills/task/SKILL.md`, `skills/flow/SKILL.md`, `skills/advance/SKILL.md`; `plugin.json`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json` and `.claude-plugin/marketplace.json` for the version.

## North-star alignment
- none — the register holds no active thought

## Open questions from intake
- Where does the closing sentence go in the three skills? → **Answer (assumed):** in each skill's existing end-of-run report section, as one short paragraph, so it is shown to the user last.
- How are holders found? → **Answer (user, 2026-10-18):** from Claude Code's own session list (`claude agents --json --all`), not by reading process memory. The first design pass tried process-memory reading and a safety check stopped it; the user chose the session list. Verified read-only: it returned id, cwd, kind, name, sessionId, startedAt and state for every session.
- Which platforms must the holder detection support? → **Answer (assumed):** Windows is required, because the `in-use` case exists only there. On other platforms the report says it cannot tell, rather than guessing. The contract may extend this.
- Should the cleanup also stop the holder when the user asks? → **Answer (assumed):** no. Stopping a session ends work the cleanup cannot judge. The cleanup prints the command and the user decides.
- Open an issue for this? → **Answer:** not asked. `issue_offer` stays `pending`, so `/ship` makes the offer later instead of this unattended run guessing.

## Size
M — new process-inspection code on a destructive-adjacent path, a report format change with tests, and text changes in three skills with a plugin version bump.

## Routing
non-trivial → /design-first

## Run log
- 2026-10-18: intake, design (draft, critic, user answers), contract approved by the user on 2026-10-30.
- 2026-10-30 to 2026-11-18: test-first cycle ran three times. Each cycle ended with a fresh code review and a fresh test-strategy review, and each review found warnings. Fixes made: no process-tree kill (only the runner's own child is ended), safe lookup of the `claude` program, UNC and device working folders unreadable, a 4 MiB output cap, a real-shape fixture and an opt-in trial against the real program, a stronger source tripwire, tests moved out of the slow end-to-end group, and the `claude` program started from its own folder with no environment variable created (the user's rule of 2026-11-18).
- 2026-11-18: the third review pass still lists four warnings, so the retry budget for the review stage is used up and the run stops here, as the flow requires. Open items for the operator:
  - Placement in `skills/advance/SKILL.md`: the closing paragraph and the `Next command` line. The implementation moved `Cleanup:` and `Trees:` ahead of `Next command:`, which changes master's report block. Two contract-consistent choices: keep master's order and put the paragraph directly before `Next command:`, or keep the new order and say the paragraph follows the report block.
  - Text safety: widen the unsafe-text rule from a code-point list to NFKC plus dropping the Unicode categories Cc, Cf, Zl and Zp (needs a change to invariant HN-6).
  - Non-text values in `name`, `state` and `kind` are turned into text instead of an empty string (a small code fix plus one test).
  - `_find_claude` runs `realpath` on every PATH folder even when no `claude` is found (a small code fix).
  - The journal entry dated 2026-10-31 recommends setting `NoDefaultCurrentDirectoryInExePath`; it needs a correction entry (the user's rule: no created environment variables).
  - Follow-ups recorded in the contract (not built): a Linux CI job for the in-process classes, moving the five world-based failure-path tests into fast unit tests, routing the end-to-end link test through the link, calling `_norm` once per record, bounding the temporary file size, DOS device names as the last part of a drive path, and a catch-all inside `attach_holders`.
- 2026-11-19: the operator chose the recommendations for the open items. All four warnings were fixed test-first and a last cold review found two more points, both fixed: the none-found text now says only what the list proves (the list shows background sessions only, verified on the operator's machine), and the `/advance` placeholder line now matches the block's style. Every test class passes in its own process (the manifests script has two failures that also occur on a clean copy of master: the `--fix` flag named by the finish-install skill, and a code-search guard hash). The version is 0.22.0 in all five places. The branch is one commit on top of master, not pushed; the push and the draft pull request wait for the operator's confirmation.
