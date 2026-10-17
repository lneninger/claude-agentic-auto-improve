---
name: reference-mutation-scratch-env
description: Where mutation-testing scratch files can live in this repo's worktrees, and which shell forms the sandbox refuses
metadata:
  type: reference
---

Scratch files for mutation runs must go under `<worktree>/.claude/scratch/...`; writing a `.sh`/`.py` to `%TEMP%` is blocked by the plugin's concept-gate hook (no contract covers it). The worktree-isolation guard also refuses `bash script.sh` and multi-line shell loops that run `py` with runtime values.

**Simplest working form (2026-10-16, issue 57):** one driver under `.claude/scratch/<tag>/` that reads the subject source, applies a string-replace mutant, `exec`s it into a `types.ModuleType` registered in `sys.modules[<name>]`, then `runpy.run_path(suite, run_name="__main__")` with stdout captured; no file copies needed. `git show HEAD:<file> > scratch` works only as a single plain command (compound git lines are refused).

**How to apply (older copy-based form):** write a Python mutation driver under `.claude/scratch/`, have it copy the helper (patch its `SCRIPTS_DIR`) and a patched copy of the suite (`SUBJECT = Path(sys.argv[1])`), then run it with one plain `py -3 <driver>` call. Delete the scratch dir afterwards. Shell-pipeline claims in skills cannot be replayed in bash here, so simulate them with subprocess pipes and say that the bash-specific parts (CR stripping in `$(...)`) were not verified.
