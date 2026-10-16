---
name: concept-gate-blocks-scratch-harness
description: concept-gate.py blocks writing any .py file (even a scratch mutation harness in %TEMP%); mutation checks must be by reading or requested from the caller
metadata:
  type: project
---
The plugin's concept-gate.py PreToolUse hook blocks Write of any .py outside `.claude/`, including a scratch mutation harness in %TEMP% (observed 2026-10-15, #50 review). The worktree-isolation guard also refuses Bash git commands aimed outside the worktree.

**Why:** the gate covers every non-trivial file write, not only project code; routing around it (a renamed extension, a Bash heredoc) would be evasion.

**How to apply:** in test-strategy reviews, do mutation-style analysis by reading assertions against code paths, say plainly that the verdicts were not executed, and recommend that the caller run a real mutation pass under an approved contract if one is needed. Single test classes can still be run (about 9 s per real-git world test on this host).
