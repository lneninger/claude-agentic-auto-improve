#!/usr/bin/env python3
"""
_plugin_root.py -- the guarded lookup of the installed plugin tree, shared by finish-install and the
registry tools.

``_separate_plugin_root`` and the helpers it calls are extracted unchanged from
``auto_improve_finish_install.py`` (which imports every name back); it is also exported as
``separate_plugin_root``. Its "own copy" candidate is this module's tree, the same folder as before.

Standard library only at import, and importing this module changes no ``sys`` state.
``find_plugin_root`` is imported from ``plugin_doctor`` inside the function, so the caller's
``sys.path`` must already reach the scripts folder (the CLI scripts put it there).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)

PLUGIN_NAME = "agentic-auto-improve"


def _norm(path: Any) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _same_dir(a: Path, b: Path) -> bool:
    try:
        return _norm(a.resolve()) == _norm(b.resolve())
    except OSError:
        return _norm(a) == _norm(b)


def _load_json_lenient(path: Path) -> Any:
    """Parse a JSON file, tolerating a byte order mark; None when absent or unreadable."""
    try:
        return json.loads(path.read_bytes().decode("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _claude_home(claude_home: Optional[Path]) -> Path:
    """The Claude home: the argument, else CLAUDE_CONFIG_DIR, else ~/.claude."""
    if claude_home:
        return Path(claude_home)
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        return Path(env)
    return Path(os.path.expanduser("~")) / ".claude"


def _manifest_names_plugin(root: Path) -> bool:
    data = _load_json_lenient(root / ".claude-plugin" / "plugin.json")
    return isinstance(data, dict) and data.get("name") == PLUGIN_NAME


def _version_key(path: Path) -> Tuple[Tuple[int, ...], str]:
    return tuple(int(n) for n in re.findall(r"\d+", path.name)), path.name


def _cache_roots(home: Optional[Path]) -> List[Path]:
    """Plugin copies in the provider cache of THE Claude home (the argument, CLAUDE_CONFIG_DIR,
    else ~/.claude), newest version first. No other home is searched."""
    found = [p for p in _claude_home(home).glob("plugins/cache/*/%s/*" % PLUGIN_NAME) if p.is_dir()]
    return sorted(found, key=_version_key, reverse=True)


def _separate_plugin_root(project: Path, plugin_root: Optional[Path], home: Optional[Path] = None,
                          needs: Optional[Callable[[Path], bool]] = None) -> Optional[Path]:
    """The plugin tree to read from; never the project itself.

    ``plugin_root`` is a hard override. Without it the candidates are tried in order:
    CLAUDE_PLUGIN_ROOT (Claude Code sets it for the install that is running), the copy this
    script lives in, then the provider cache under the Claude home (newest version first).
    A candidate equal to the project is rejected, and with ``needs`` the first candidate that
    really carries the needed file wins, so a vendored project (whose own tree has no
    template and no hooks.json) goes on to the next candidate. When none carries it, the first
    admissible candidate is returned so the plugin's agents can still be found. Every
    candidate, the override included, must be THIS plugin: ``.claude-plugin/plugin.json`` with
    ``name`` equal to PLUGIN_NAME; another plugin's tree or one with no manifest is skipped.
    """
    from plugin_doctor import find_plugin_root
    if plugin_root is not None:
        override = find_plugin_root(str(plugin_root))
        if override is None or _same_dir(override, project) or not _manifest_names_plugin(override):
            return None
        return override
    candidates: List[Path] = []
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        candidates.append(Path(env))
    candidates.append(Path(_SCRIPTS_DIR).parent.parent)
    candidates += _cache_roots(home)
    admissible = [c for c in candidates
                  if c.is_dir() and not _same_dir(c, project) and _manifest_names_plugin(c)]
    for candidate in admissible:
        if needs is None or needs(candidate):
            return candidate
    return admissible[0] if admissible else None


separate_plugin_root = _separate_plugin_root
