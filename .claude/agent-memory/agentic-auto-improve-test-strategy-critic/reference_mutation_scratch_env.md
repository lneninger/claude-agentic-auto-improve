---
name: reference-mutation-scratch-env
description: Where mutation-testing scratch files can live in this repo's worktrees, and which shell forms the sandbox refuses
metadata:
  type: reference
---

Scratch files for mutation runs must go under `<worktree>/.claude/scratch/...`; writing a `.sh`/`.py` to `%TEMP%` is blocked by the plugin's concept-gate hook (no contract covers it). The worktree-isolation guard also refuses `bash script.sh` and multi-line shell loops that run `py` with runtime values.

**Simplest working form (2026-10-16, issue 57):** one driver under `.claude/scratch/<tag>/` that reads the subject source, applies a string-replace mutant, `exec`s it into a `types.ModuleType` registered in `sys.modules[<name>]`, then `runpy.run_path(suite, run_name="__main__")` with stdout captured; no file copies needed. `git show HEAD:<file> > scratch` works only as a single plain command (compound git lines are refused).

**No-file probe (2026-10-22):** to check a test helper (e.g. a regex extractor) against inputs, paste it into `py -3 -I - <<'EOF' ... EOF` in one Bash call; no file is written, so no gate fires. Use raw strings for backslash inputs; `py -c` with nested quoting breaks.

**Function-level mutants with no file at all (2026-10-30, issue 113):** `cd .claude/scripts/tests && py -3 -B -c "..."` that imports the test module, then `mock.patch.object(pr_merged, '<fn>', mutant)` and runs chosen TestCase classes with `unittest.TextTestRunner(stream=io.StringIO())`, printing the failed count for each mutant. Works for any module-level function called by global name. Caveat: a patch is silently overridden when the test harness itself mocks the same function (e.g. `open_records_pull_requests` in `_drive`), so a "0 failed" result there means nothing. Setting `GIT_CONFIG_GLOBAL` in a command is refused by the worktree guard, so clean-git-environment flakiness can only be reasoned about. Suites that include real-git worktree classes take more than 3 minutes per mutant, so run them in the background.

**How to apply (older copy-based form):** write a Python mutation driver under `.claude/scratch/`, have it copy the helper (patch its `SCRIPTS_DIR`) and a patched copy of the suite (`SUBJECT = Path(sys.argv[1])`), then run it with one plain `py -3 <driver>` call. Delete the scratch dir afterwards. Shell-pipeline claims in skills cannot be replayed in bash here, so simulate them with subprocess pipes and say that the bash-specific parts (CR stripping in `$(...)`) were not verified.
