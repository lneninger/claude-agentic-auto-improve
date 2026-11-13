---
name: parent-branch-tip-review-traps
description: Where a final review of a parent branch (blocks 1-N) finds real defects that each block's own green run missed
metadata:
  type: feedback
---

On a final review gate over a parent branch, re-run every named suite on the TIP, not only per block, and read each block PR body for failures it called "outside this task's files".

**Why:** in the #165 t10 review (2026-11-12) two suites were red on the tip while every block PR said green. (1) The main session's `origin/master` merge into the parent branch brought in a line that a block's whole-file text pin rejects. That merge is not a block and nobody reviewed it. (2) Three blocks each saw the same `test_plugin_doctor` unshipped-name failure, filed it as someone else's, and no block owned it. CI's `tests` job runs only two suites, so neither is caught at the landing.

**How to apply:** use `git diff <merge-base with origin/master>..<tip>` as the range. Trace each red line with `git log -- <file>` to see whether it came from master or from a block. Grep the block PR bodies (`gh pr view N --json body`) for "skip", "outside" and "not met". To prove a pin fails before its fix, load the test module with importlib and apply its helper to `git show <base>:<file>` text. Related: [[worktree-shell-and-probe-habits]].
