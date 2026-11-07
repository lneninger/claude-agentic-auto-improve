---
name: plan-apply-ticket-and-shadow-log-links
description: codegraph guard 0.16.x plan/apply split keeps a planned retry allow when the ticket delete fails (reusable ticket); shadow log and _error_log open through links
metadata:
  type: project
---

Two problems found in the codegraph guard after master's hooks redesign (#261), which landed as 0.16.x:
- `apply_state` keeps the planned `retry-escape-used` allow even when `os.remove(ticket)` fails. A read-only or locked ticket then allows the identical call over and over (probe: `chmod S_IREAD` on the ticket, retries all exit 0). Two identical parallel calls also both pass on one ticket. The pre-#271-merge branch fell through to a block instead.
- `<CLAUDE_PROJECT_DIR>/.claude/logs/codegraph-shadow.jsonl` is created with `makedirs` and `os.open(O_APPEND|O_CREAT)`, with no `O_NOFOLLOW` and no link check. `_error_log.log_event` behaves the same way (`Path.open("a")`). A link committed in a repository therefore redirects the appends to any file the user can write.

**Why:** both were filed as follow-ups in pass 5 of the #271 audit (2026-11-07), not as release blockers.
**How to apply:** in later guard reviews, check whether these two were fixed. Treat "apply never re-decides" as a smell wherever the effect it skips (consumption) is the security property. Related: [[unc-host-check-normpath-collapse]].

Probe harness tip: the worktree git guard rejects heredoc Python and any command with redirects. Write probe scripts with the Write tool under `%TEMP%\<dir>`, then run them with `py -3 -I <script> <args>`.
