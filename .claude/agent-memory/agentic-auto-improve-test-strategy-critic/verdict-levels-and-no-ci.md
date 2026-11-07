---
name: verdict-levels-and-no-ci
description: Layered verdict functions need one fault-injection fence per level; this repo has no CI test job, so POSIX/root-only rows never execute
metadata:
  type: project
---

This repo's `.github/workflows/` runs no tests (only version-bump), and the developer runs suites on Windows. POSIX-only or root-only rows (owner/mode checks) therefore never execute.

**Why:** In the #271 review (2026-11-06), the check-failed row fenced only the parent `lstat`, so the inner Session-folder `except Exception` was never reached. Removing it would let the I-4 catch-all allow, and no test would notice. The `st_uid` and `st_mode` checks were skip-only on the dev box.

**How to apply:** For any layered verdict (parent, then child), demand one fault fence per level. For POSIX security branches, demand in-process rows that inject `os.getuid` (`create=True`) and a per-path `lstat` stat override, so they run on every OS. Related: [[swap-tests-vs-abort-on-failure]].
