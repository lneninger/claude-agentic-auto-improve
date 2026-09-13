"""Scripts-side bridge to the shared Claude path resolver.

``.claude/scripts/`` and ``.claude/hooks/`` are sibling directories. A script
launched as ``py -3 .claude/scripts/foo.py`` gets only its OWN directory on
``sys.path[0]``, so the hooks-side ``_project_paths`` helper is unreachable
without a bridge. This module is that bridge, and it is the single import site
for all seven scripts -- one seam to get right, one seam to fake in a test.

It follows the convention ``_contract_files.py`` already establishes in this
directory: an underscore-prefixed module imported by its siblings.

**This module deliberately has NO home-directory fallback.**

An earlier draft specified "fail soft with home-based defaults if the hooks
directory is absent". That was removed before implementation, because it
would have reconstituted the exact defect this work item exists to remove: a
silent fallback to ``~/.claude`` that leaves every script blind while still
exiting 0. Two distinct failure classes are at play, and only one of them
fails open:

* **A data file is missing** at a correctly-resolved root -- the registry, the
  area map, the ledger. That fails OPEN: the caller receives a neutral value,
  the process exits 0, the critic still runs. Knowledge being absent is a
  normal state.
* **The resolver itself cannot be found** -- this module cannot locate its
  ``hooks/`` sibling. That is a STRUCTURAL failure: the repository is
  malformed. It raises ``ImportError`` naming the path it looked for.

The trigger for the second case is near-impossible by construction, since the
hooks directory is resolved relative to this file inside the same checkout.
That is precisely why a fallback there would be untestable dead code whose
only reachable effect is to hide a real breakage. Do not "restore" it.

See ``.claude/concepts/2026-08-26-claude-scripts-path-resolution.md``
(INV-1, INV-3) and work item #35.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"

if not _HOOKS_DIR.is_dir():
    raise ImportError(
        f"_claude_paths: cannot locate the sibling hooks directory at {_HOOKS_DIR}. "
        "The Claude setup under .claude/ is malformed -- scripts/ and hooks/ must "
        "be siblings. Refusing to fall back to a home-directory default, which "
        "would leave every script silently blind (work item #35)."
    )

# APPEND, never insert at position 0: the scripts' own directory must keep
# import priority so the hooks half cannot shadow `_contract_files` or a
# future sibling of the same name.
_hooks_str = str(_HOOKS_DIR)
if _hooks_str not in sys.path:
    sys.path.append(_hooks_str)

try:
    import _project_paths as _pp
except ImportError as exc:  # pragma: no cover - structural failure
    raise ImportError(
        f"_claude_paths: found the hooks directory at {_HOOKS_DIR} but could not "
        f"import _project_paths from it ({exc}). Refusing to fall back to a "
        "home-directory default (work item #35)."
    ) from exc


# Re-exported resolver surface. Every one of these is a CALL-TIME function --
# never bind one to a module-level constant in a consumer, or the path is
# captured at import and neither a test nor a different checkout can redirect
# it (INV-2).
claude_roots = _pp.claude_roots
concepts_roots = _pp.concepts_roots
registry = _pp.registry
area_mapping_path = _pp.area_mapping_path
work_item_conventions_path = _pp.work_item_conventions_path
work_items_dir = _pp.work_items_dir
accuracy_state_path = _pp.accuracy_state_path
north_stars_roots = _pp.north_stars_roots
cache_dir = _pp.cache_dir
first_populated_dir = _pp.first_populated_dir
project_aliases = _pp.project_aliases
project_matches = _pp.project_matches
project_dir = _pp.project_dir
state_dir = _pp.state_dir
logs_dir = _pp.logs_dir
hook_file = _pp.hook_file

__all__ = [
    "claude_roots",
    "concepts_roots",
    "registry",
    "area_mapping_path",
    "work_item_conventions_path",
    "work_items_dir",
    "accuracy_state_path",
    "north_stars_roots",
    "cache_dir",
    "first_populated_dir",
    "project_aliases",
    "project_matches",
    "project_dir",
    "state_dir",
    "logs_dir",
    "hook_file",
]
