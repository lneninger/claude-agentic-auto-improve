"""
PostToolUse hook for Edit|Write|MultiEdit.

When Claude edits a C# file (or a generator-related tool file) that would
invalidate the auto-generated Angular models, this hook touches one or both
dirty-flag files:
  .claude/.models-dirty-rest  -> REST client regeneration needed (NSwag)
  .claude/.models-dirty-hub   -> SignalR hub client regeneration needed (Tapper)

The Stop hook (regenerate-models-on-stop.py) drains these flags at end-of-turn
and runs the appropriate tools/generate-*.cmd script.

Never blocks Claude's turn: always exits 0. Silent no-op for non-sentinel paths.
See .claude/hooks/sentinel-paths.json for the single source of truth on what
counts as a REST vs Hub sentinel.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
SENTINEL_CONFIG = HOOKS_DIR / "sentinel-paths.json"
LOG_FILE = HOOKS_DIR / "models-regen.log"
DIRTY_REST = REPO_ROOT / ".claude" / ".models-dirty-rest"
DIRTY_HUB = REPO_ROOT / ".claude" / ".models-dirty-hub"


def log(msg: str) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(f"[{datetime.now().isoformat(timespec='seconds')}] mark: {msg}\n")
    except OSError:
        pass


def load_patterns() -> tuple[list[str], list[str]]:
    try:
        data = json.loads(SENTINEL_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log(f"sentinel-paths.json unreadable: {exc}")
        return [], []
    return list(data.get("rest", [])), list(data.get("hub", []))


def _to_repo_relative(path: str) -> str | None:
    """Normalize tool_input.file_path to a forward-slash, repo-relative path."""
    if not path:
        return None
    try:
        resolved = Path(path).resolve()
    except (OSError, ValueError):
        return None
    try:
        rel = resolved.relative_to(REPO_ROOT)
    except ValueError:
        return None
    return rel.as_posix()


_GLOB_REGEX_CACHE: dict[str, re.Pattern[str]] = {}


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Convert a glob with ** support into an anchored regex.

    ** matches any number of path segments (including zero), * matches any
    characters except '/', ? matches a single non-'/' character. All other
    regex metacharacters are escaped.
    """
    cached = _GLOB_REGEX_CACHE.get(pattern)
    if cached is not None:
        return cached

    out: list[str] = ["^"]
    i = 0
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                i += 2
                if i < n and pattern[i] == "/":
                    # `**/` in the middle: zero or more directory segments.
                    i += 1
                    out.append("(?:.*/)?")
                else:
                    # `**` at end (or bare): match any descendants/anything.
                    out.append(".*")
            else:
                out.append("[^/]*")
                i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c in r".+()[]{}|^$\\":
            out.append("\\" + c)
            i += 1
        else:
            out.append(c)
            i += 1
    out.append("$")

    compiled = re.compile("".join(out))
    _GLOB_REGEX_CACHE[pattern] = compiled
    return compiled


def _matches_any(rel: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if _glob_to_regex(pattern).match(rel):
            return True
    return False


def _touch(flag: Path) -> None:
    try:
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.touch(exist_ok=True)
    except OSError as exc:
        log(f"failed to touch {flag.name}: {exc}")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    tool_input = payload.get("tool_input", {}) or {}
    tool_name = payload.get("tool_name", "")

    # MultiEdit carries an edits[] array; Edit/Write carry file_path directly.
    candidate_paths: list[str] = []
    file_path = tool_input.get("file_path")
    if isinstance(file_path, str) and file_path:
        candidate_paths.append(file_path)
    # Some tool shapes nest it under 'path'
    alt_path = tool_input.get("path")
    if isinstance(alt_path, str) and alt_path:
        candidate_paths.append(alt_path)

    if not candidate_paths:
        return 0

    rest_patterns, hub_patterns = load_patterns()
    if not rest_patterns and not hub_patterns:
        return 0

    rest_hit = False
    hub_hit = False
    matched_for_log: list[str] = []

    for raw in candidate_paths:
        rel = _to_repo_relative(raw)
        if not rel:
            continue
        if _matches_any(rel, rest_patterns):
            rest_hit = True
            matched_for_log.append(f"REST:{rel}")
        if _matches_any(rel, hub_patterns):
            hub_hit = True
            matched_for_log.append(f"HUB:{rel}")

    if rest_hit:
        _touch(DIRTY_REST)
    if hub_hit:
        _touch(DIRTY_HUB)

    if matched_for_log:
        log(f"{tool_name}: " + ", ".join(matched_for_log))

    return 0


if __name__ == "__main__":
    sys.exit(main())
