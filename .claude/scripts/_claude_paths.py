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

import os
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

# The five names of the Project hook launcher surface (Revision 9). A `_project_paths.py` from a release
# before the launcher imports cleanly and lacks them, so a bare attribute read below would raise
# AttributeError, which the callers that guard this import (they catch ImportError) would not catch.
# Raise ImportError instead, naming the file and each missing name, so they degrade as designed.
_LAUNCHER_NAMES = (
    "PROJECT_HOOK_LAUNCHER_SOURCE",
    "HOOK_CLASS_BLOCK",
    "HOOK_CLASS_WARN",
    "project_hook_launcher_parts",
    "project_hook_launcher_row",
)
_missing_launcher_names = [name for name in _LAUNCHER_NAMES if not hasattr(_pp, name)]
if _missing_launcher_names:
    raise ImportError(
        f"_claude_paths: the _project_paths.py at {getattr(_pp, '__file__', _HOOKS_DIR)} lacks the Project hook "
        f"launcher surface: {', '.join(_missing_launcher_names)}. Bring the hooks folder to the same release "
        "as the scripts."
    )


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
tree_kind = _pp.tree_kind
main_checkout_root = _pp.main_checkout_root
installed_plugin_root = _pp.installed_plugin_root


def _remote_host(text):
    """``None`` for a local path. For a UNC or device path (a leading pair of separators, either kind) the
    lower-cased host; ``"?c:"`` for a device path on a local drive; ``""`` when a device path names no host."""
    slashed = text.replace("\\", "/")
    if not slashed.startswith("//"):
        return None
    parts = [p for p in slashed[2:].split("/") if p]
    if parts and parts[0] in ("?", "."):
        if len(parts) > 2 and parts[0] == "?" and parts[1].upper() == "UNC":
            return parts[2].lower()
        if len(parts) > 1 and len(parts[1]) == 2 and parts[1][1] == ":" and parts[1][0].isalpha():
            return "?" + parts[1].lower()
        return ""
    return parts[0].lower() if parts else ""


def _hop_allowed(target, own, *also):
    """A pointer hop may be looked at when it is local, or a UNC or device path whose host is the host of the tree's
    own path or of any other spelling given (``also``: its ``os.path.realpath`` form). The text AND its normal form
    are judged, and a ``..`` segment inside a UNC or device path is never allowed: the text checked is the text opened."""
    allowed = {h for h in (_remote_host(o) for o in (own,) + also) if h}
    climbs = ".." in target.replace("\\", "/").split("/")
    for text in (target, os.path.normpath(target)):
        host = _remote_host(text)
        if host is not None and (not host or host not in allowed or climbs):
            return False
    return True


def _own_spellings(path):
    """The spellings of a tree's own path that count for the same-host rule: the written form, plus its
    ``os.path.realpath`` form when the written form is local (a mapped drive resolves to ``\\\\server\\share``).
    A path already written as UNC or device is never resolved: that would touch its host."""
    return (path,) if _remote_host(path) is not None else (path, os.path.realpath(path))


def _inline_worktree_own_root(path):
    """The same walk as ``_project_paths.worktree_own_root``, for a ``_project_paths.py`` from an earlier release
    that lacks it. Returns ``(own tree root, gitdir)``; see the helper's docstring for the contract. A gitdir that
    is a UNC or device path naming another host than the tree, holds neither ``/.git/worktrees/`` nor
    ``/.git/modules/``, or is cut off by the 4096-byte read cap is undecidable: ``(F, None)``, and nothing under it
    is touched."""
    import os

    def pointer(folder, first):
        raw = first[len("gitdir:"):].strip() if first.startswith("gitdir:") else ""
        if not raw or not _hop_allowed(raw, *_own_spellings(folder)):
            return None
        target = os.path.normpath(os.path.join(folder, raw)).replace("\\", "/")
        if not _hop_allowed(target, *_own_spellings(folder)) or not any(m in target.lower() for m in ("/.git/worktrees/", "/.git/modules/")):
            return None
        return target

    try:
        folder = os.path.abspath(path)
        while not os.path.exists(folder):
            parent = os.path.dirname(folder)
            if parent == folder:
                return None, None
            folder = parent
        while True:
            entry = os.path.join(folder, ".git")
            if os.path.isdir(entry):
                return folder, None
            if os.path.isfile(entry):
                try:
                    with open(entry, "rb") as fh:
                        data = fh.read(4096)
                    first = "" if len(data) >= 4096 and b"\n" not in data else data.split(b"\n", 1)[0].decode("utf-8").strip()
                except (OSError, ValueError, UnicodeError):
                    return None, None
                return folder, pointer(folder, first)
            parent = os.path.dirname(folder)
            if parent == folder:
                return None, None
            folder = parent
    except (OSError, ValueError):
        return None, None


# worktree_own_root is looked up with getattr: a `_project_paths.py` from an earlier release imports cleanly and
# lacks it, so a bare attribute read would raise AttributeError at import. TREE_HOP_REFUSAL is the Hop proof computed
# on the helper beside these scripts: the helper declares the constant, or it has the 0.15.2 shape (_hop_allowed and
# worktree_own_root both callable). worktree_own_root below is the helper's only when the helper provides it, otherwise
# the inline copy; the constant says nothing about which release the helper is (the same expression gates the
# codegraph guard and the installer).
_native_own_root = getattr(_pp, "worktree_own_root", None)
TREE_HOP_REFUSAL = getattr(_pp, "TREE_HOP_REFUSAL", False) is True or (
    callable(getattr(_pp, "_hop_allowed", None)) and callable(_native_own_root))
worktree_own_root = _native_own_root if (TREE_HOP_REFUSAL and callable(_native_own_root)) else _inline_worktree_own_root
# The Project hook launcher (Revision 9): the one source text, the row builder and the row reader.
# PROJECT_HOOK_LAUNCHER_SOURCE is a constant, not a call-time function: it is fixed text.
PROJECT_HOOK_LAUNCHER_SOURCE = _pp.PROJECT_HOOK_LAUNCHER_SOURCE
project_hook_launcher_row = _pp.project_hook_launcher_row
project_hook_launcher_parts = _pp.project_hook_launcher_parts
HOOK_CLASS_BLOCK = _pp.HOOK_CLASS_BLOCK
HOOK_CLASS_WARN = _pp.HOOK_CLASS_WARN

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
    "tree_kind",
    "main_checkout_root",
    "worktree_own_root",
    "TREE_HOP_REFUSAL",
    "installed_plugin_root",
    "PROJECT_HOOK_LAUNCHER_SOURCE",
    "project_hook_launcher_row",
    "project_hook_launcher_parts",
    "HOOK_CLASS_BLOCK",
    "HOOK_CLASS_WARN",
]
