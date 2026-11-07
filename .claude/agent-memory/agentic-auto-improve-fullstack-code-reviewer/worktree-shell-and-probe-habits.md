---
name: worktree-shell-and-probe-habits
description: How to run probes and long suites in this repo's worktree-isolated review sessions without being refused or stalling
metadata:
  type: feedback
---

Write probe scripts to a scratch folder outside the repo (e.g. C:\Temp\<tag>\) with the Write tool and run them with `py -3 -I <script> <repo path>`; never inline heredocs or multi-step `cd && cat > … && py …` chains.

**Why:** the worktree isolation guard refuses compound Bash commands it cannot verify (heredoc + cd + py in one line was refused in the #271 pass-3 review). `unittest discover -s .claude/scripts/tests` takes well over 10 minutes; a foreground wait loop gets moved to the background.

**How to apply:** start the full scripts discover in the background FIRST (before reading code), run the hook suites in the foreground one at a time (never concurrently: the real-folder leak checks false-fail when anything else runs the hooks), and run targeted `-k` subsets of the installer suite if the discover has not finished when the report is ready. Never create placeholder files inside `.claude/reviews/` — they show up as stray files in git status. Related: [[codegraph-guard-review-checklist]].
