---
name: json-only-cli-tests-miss-text-renderer
description: finish-install subcommand tests drive main() with --json only; check the SKILL.md command lines for a missing --json and probe the text renderer
metadata:
  type: project
---

Suites for `auto_improve_finish_install.py` subcommands pass `--json` on every call, so `_render_text` is never run. In #21 (project-files, 2026-11-11), SKILL.md step 2d ran `--apply` WITHOUT `--json`, and the text renderer crashed with KeyError 'path' on a `nothing-to-do` result (a re-run, or every file skipped).

**Why:** a branch in the renderer is keyed on result fields (`token-proposals`, `gitignore-hint`+`written`, else `files[].path/action`). Any new result shape lands in the old fallback.

**How to apply:** for any new subcommand, grep SKILL.md for its command lines. If one runs without `--json`, require one text-mode test for each result status (plan, applied, nothing-to-do, refused). A quick check is `py -3 -c` that builds the test's Base fixture and calls `fi.main` without `--json`. No scratch file is needed, see [[concept-gate-blocks-scratch-harness]].
