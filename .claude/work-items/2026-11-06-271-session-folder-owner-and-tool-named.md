---
id: 271
issue_offer: pending
title: Windows owner check for session folders and the codegraph-tool-named refusal (held from #259)
type: SECURITY
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/271
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: fix/271-session-folder-owner-and-tool-named
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261106-bug-271-windows-session-owner-check
north_stars: none
contract: .claude/concepts/2026-11-06-session-folder-owner-and-tool-named.md
pr: UNKNOWN
issue_link: unknown
status: verifying
created: 2026-11-06
---

# Windows owner check for session folders and the codegraph-tool-named refusal (held from #259)

## Problem statement
Two security decisions were held back from #259 (pull request #270) for an owner decision; neither is a regression.

1. The CodeGraph guard and tracker hooks keep session state in a folder under the system temp folder. On POSIX the folder is created `0700` and its owner is checked. On Windows there is no owner check. If `TMP` points at a folder shared between users, another user could plant a session folder holding a `turn.json`, which silently opens the gate for the victim's session. The pruner could also delete another user's old folders. Default Windows temp is per-user, so the precondition is a shared `TMP`.
2. The installer refuses when a settings layer names a single CodeGraph tool (for example `mcp__codegraph__codegraph_explore`). The security review suggested a finding in `--check` and the preview instead. Issue #259 itself asked for a loud failure on a per-tool entry. The preview sentence about what `mcp__codegraph__*` auto-approves may also need to say more.

## Acceptance criteria
- [ ] Session folders for the guard, tracker and reset hooks live under a per-user parent: `%LOCALAPPDATA%` on Windows, a `0700` per-user folder on POSIX. A folder under a shared `TMP` is no longer read or pruned.
- [ ] A test shows a planted session folder with a `turn.json` in a shared temp folder does NOT open the gate for another user's session.
- [ ] The pruner deletes only folders under the caller's own per-user parent, and a test shows a foreign or linked entry is left alone.
- [ ] The gate logs once when it opens from a marker this session's tracker did not write.
- [ ] The `codegraph-tool-named` refusal stays; its message names each entry and layer and the one-step way out (widen to `mcp__codegraph__*`), and a test pins that.
- [ ] One capability constant is exported from the shared path helper and the guard, the bridge and the installer gate on it.
- [ ] A comment pins the probe order in the `commondir` hop of `_git_file_kind`.
- [ ] `skills/auto-improve-codegraph-install/SKILL.md` no longer says it "does not build the index" where it offers `codegraph init -i`.
- [ ] Failure path: if the per-user parent cannot be created or is not owned by the user, the hooks fail closed (gate stays shut) and say why.

## Out of scope
- A hostile `gitdir:` that is a symlink to a UNC path (git follows it the same way; documented, not changed).
- Turning `codegraph-tool-named` into a finding (owner chose to keep the refusal).
- Checking the folder owner's SID on Windows (owner chose the per-user parent instead).

## Known context
- Parent / epic: none
- Related items: #259, #270 (pull request), #261 (hook redesign)
- Affected areas (best guess, to be confirmed by the contract): `.claude/addons/codegraph/hooks/codegraph-first-guard.py`, `codegraph-turn-tracker.py`, `codegraph-turn-reset.py` (session folder and pruner), `.claude/hooks/_project_paths.py` and `.claude/scripts/_claude_paths.py` (shared path helper, `_hop_allowed`, `WORKTREE_OWN_ROOT_NATIVE`), `.claude/scripts/auto_improve_finish_install.py` (`codegraph-tool-named` refusal), `skills/auto-improve-codegraph-install/SKILL.md`, plus their tests.
- Optional small items in the issue: one shared capability constant gating guard, bridge and installer; a comment pinning the probe order in the `commondir` hop of `_git_file_kind`; skill wording at lines 160 and 208 versus line 131 ("does not build the index" versus offering `codegraph init -i`); a hostile `gitdir:` symlink to a UNC path followed before any check.
- Safety-critical: yes. This is a security gate, so `/tdd-first` is mandatory and `security-auditor` review is required.

## North-star alignment
- none — the register holds no active thought

## Open questions from intake
- Q1. Windows session-folder protection: per-user parent folder, or check the folder owner's security identifier (SID)? → **Answer:** Per-user parent folder (owner, recommended option).
- Q2. `codegraph-tool-named`: keep the refusal, or turn it into a finding in `--check` and the preview? → **Answer:** Keep the refusal (owner, recommended option).
- Q3. Should the preview say more about what `mcp__codegraph__*` auto-approves? → **Answer:** Assumed no: the #270 sentence already states what the wildcard auto-approves; only the refusal message is improved. Overrule at the contract gate.
- Q4. Which of the four optional small items are in this change? → **Answer:** Assumed: constant, probe-order comment and skill wording are in; the UNC symlink item is out. Overrule at the contract gate.

## Size
M — security change across three hooks, a shared helper and the installer, with a contract needed for the two decisions.

## Routing
non-trivial → /design-first

## Run log

Stopped by `/flow` on 2026-11-06 at the retry budget: the review stage failed three times (three review passes, each followed by a test-first fix round).

- Contract approved by the owner after two critic passes: `.claude/concepts/2026-11-06-session-folder-owner-and-tool-named.md` (history: `.claude/contract-history/2026-11-06-*.round-1.md`, `.round-2.md`).
- State of the code: uncommitted in this worktree. Suites verified by the main session with exit codes: `test_codegraph_first_guard.py` 1158 passed / 0 failed / 3 skipped (POSIX or root only); `test_addons.py`, `test_worktree_path_guards.py` (190/190), `test_codegraph_session_parent_docs.py`, `test_plugin_manifests.py` (191), `test_auto_improve_finish_install.py` (395) all exit 0. `test_gate_cost.py` (needs an environment variable) and `test_cleanup_delivered.py` (timed out, unrelated) were not run to completion. The full scripts folder `unittest discover` never finished and was not used.
- Review passes: pass 1 (security Medium x2, test-strategy High x2, code reviewer 4 warnings) fixed in round 1; pass 2 (security Medium: doubled-separator and `\??\` spellings; code reviewer: drive check ran after the slow path lookup) fixed in round 2; pass 3 (below) is open.
- **Open at stop (one condition, named by both pass-3 reviewers):** in `session_parent_base` (identical in the guard, tracker and reset hooks) a Windows base that has a root but no drive letter (`\AppData\Local`, `/x/y`) skips the drive-type check, resolves against the cwd's drive and can reach a mapped network drive. Fix: `if os_name == "nt" and not ntpath.splitdrive(raw)[0]: return None, "not-absolute"` after the `isabs` check, plus rows for `\x` and `/x/y` whose fake `realpath` raises if called. Pass-3 security also suggested: refuse any `//` text that is not exactly `//?/` or `//./` as remote; allow only drive types 2, 3 and 6; report a `ctypes` failure as `check-failed`; escape the `--check` output too.
- Reviewers' verdicts: security pass 3 pass-with-conditions (no release blocker, one merge condition above); code reviewer pass 3 fix-then-ship (shippable once that warning is fixed).
- Follow-ups that are NOT part of this change (to become issues if the owner agrees): non-ASCII stdin decoding on Windows fails open (pre-existing); other modules keep per-session state in the shared temp folder (`_project_paths.py` session marker, `stop-dispatcher.py`, `concept_changed_check.py`, `integration-check.py`); profiles on a volume with no drive letter (FSLogix/VHDX) are refused as `remote` with a false fix line; POSIX base folder owner/mode race; leak checks false-fail when a live session runs hooks during a suite; contract wording "pure" for the Parent base.
- Update 2026-11-07: the owner approved one more fix round (drive-less path, leading-`//`, drive-type allowlist, `check-failed`, `--check` escaping); a fourth security check passed with no release blocker (two Low follow-ups: drive letter that appears only in the `realpath` form, bare `\\?\C:` device base). Verification ran (suites exit 0, guard suite 1377 passed / 0 failed / 3 skipped) and the work was committed locally as `e9cbc05` on `fix/271-session-folder-owner-and-tool-named`. Not pushed, no pull request.
- **Blocked on the base branch:** `origin/master` moved 50 commits ahead (now plugin 0.16.2; this branch is 0.15.3). Master carries the merged codegraph hooks redesign (#261): it changes `codegraph-first-guard.py`, `codegraph-turn-reset.py`, `addon.json`, `auto_improve_finish_install.py`, the decision table, README, both codegraph skills, VOCABULARY and JOURNAL, the same files this change edits. `check_version_bump.py` fails on the committed branch for that reason (version must be raised above master's). The branch needs a rebase or merge onto master and a re-decision on how the per-user session parent fits the redesigned hooks, then a version above 0.16.2, before any push.
