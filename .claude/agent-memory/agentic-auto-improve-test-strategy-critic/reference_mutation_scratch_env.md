---
name: reference-mutation-scratch-env
description: Where mutation-testing scratch files can live in this repo's worktrees, and which shell forms the sandbox refuses
metadata:
  type: reference
---

Scratch files for mutation runs must go under `<worktree>/.claude/scratch/...`; writing a `.sh`/`.py` to `%TEMP%` is blocked by the plugin's concept-gate hook (no contract covers it). The worktree-isolation guard also refuses `bash script.sh` and multi-line shell loops that run `py` with runtime values.

**How to apply:** write a Python mutation driver under `.claude/scratch/`, have it copy the helper (patch its `SCRIPTS_DIR`) and a patched copy of the suite (`SUBJECT = Path(sys.argv[1])`), then run it with one plain `py -3 <driver>` call. Delete the scratch dir afterwards. Shell-pipeline claims in skills cannot be replayed in bash here, so simulate them with subprocess pipes and say that the bash-specific parts (CR stripping in `$(...)`) were not verified.
