---
id: 242
issue_offer: opened
title: Extract the shared apply and plugin-root helpers
type: BUG
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/242
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-04-domain-split-registries/t2-extract-the-shared-apply-and-plugin-root-helpers
worktree: none
north_stars: inherited from .claude/work-items/2026-11-04-235-domain-split-registries.md
parent_issue: 235
base: fix/235-domain-split-registries
contract: .claude/concepts/2026-11-04-domain-split-registries.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/252
issue_link: deferred
status: shipped
created: 2026-11-04
---

# Extract the shared apply and plugin-root helpers

## Problem statement
Sub-task 2 of the approved contract `.claude/concepts/2026-11-04-domain-split-registries.md` (parent issue #235). The contract's handoff block below is the whole specification.

## Acceptance criteria
### 2. Extract the shared apply and plugin-root helpers (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/scripts/_preview_apply.py`
- `.claude/scripts/_plugin_root.py`
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/scripts/tests/test_preview_apply.py`
- `.claude/scripts/tests/test_plugin_root.py`

**Pre-written TASK block:**
```
TASK: Extract _plan_digest and _atomic_write into _preview_apply.py and _separate_plugin_root with its helpers into
_plugin_root.py, unchanged, and import every moved name back in auto_improve_finish_install.py; add the new
stage_and_replace to _preview_apply.py.
CONTEXT: concept contract ("Shared helpers", "Import chain", Plugin root resolution VO, Reused Mechanisms).
FILES: as listed.
CONSTRAINTS:
  - Moved names: _plan_digest, _atomic_write; _separate_plugin_root (exported also as separate_plugin_root),
    _same_dir, _norm, _manifest_names_plugin, _load_json_lenient, _claude_home, _version_key, _cache_roots,
    PLUGIN_NAME. Read :180-394 first; a helper also used elsewhere in finish-install is imported back, never copied.
    _backup_write stays where it is. find_plugin_root is imported from plugin_doctor inside the function only.
  - Both modules: stdlib only at import, no sys mutation, no sys.path change. finish-install behaviour unchanged.
  - stage_and_replace(writes, backup_dir) exactly per the contract steps (a)-(d).
  - Tests: finish-install's names are the moved objects; a clean-process import of each module leaves
    sys.dont_write_bytecode and sys.path unchanged; stage_and_replace: success; staging failure touches no target;
    replace failure on the 2nd of 3 restores the 1st and deletes a created file; backups land only in backup_dir.
    separate_plugin_root: the project's own tree is rejected (vendored fixture: project holds the plugin's template,
    scripts and even a copied manifest; no other candidate -> None); a cache copy with the manifest is returned; an
    override equal to the project -> None.
  - Run: py -3 .claude/scripts/tests/test_preview_apply.py ; py -3 .claude/scripts/tests/test_plugin_root.py ;
    py -3 .claude/scripts/tests/test_auto_improve_finish_install.py ; py -3 .claude/scripts/tests/test_check_version_bump.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

## Out of scope
- Everything outside the files listed in the handoff block.

## Known context
- Parent / epic: #235
- Contract: .claude/concepts/2026-11-04-domain-split-registries.md

## North-star alignment
- inherited from .claude/work-items/2026-11-04-235-domain-split-registries.md

## Open questions from intake
- none

## Size
Task of an approved contract; not sized here.

## Routing
task of .claude/concepts/2026-11-04-domain-split-registries.md - dispatched by /advance
