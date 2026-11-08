#!/usr/bin/env python3
"""
codegraph-turn-tracker.py -- PostToolUse hook that marks the current
investigation turn as having used CodeGraph.

When any mcp__codegraph__* tool completes (even with an error, and whatever
its name: a legacy, current or future tool), this hook writes the Turn marker
``turn.json`` in the session's folder under the system temp folder:

    <system temp folder>/auto-improve-codegraph-<session key>/turn.json

The marker is keyed to the SESSION, not to the working directory, so a ``cd``
or ``EnterWorktree`` does not close the gate again. Its presence opens the
codegraph-first-guard gate for Read / Grep / Glob during the rest of the turn.

Hook contract (Claude Code):
    stdin:  JSON with { session_id, cwd, tool_name, tool_input: {...}, ... }
    exit 0: always (this hook never blocks)
    other:  fail-soft -- log to stderr, exit 0

Fail-soft is critical: this hook must not impede the PostToolUse pipeline.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import time

SESSION_PREFIX = "auto-improve-codegraph-"
MARKER_NAME = "turn.json"
_SESSION_ID_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9_-])?")  # never ends in "." (Windows strips it)
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def log(msg: str) -> None:
    print(f"[codegraph-turn-tracker] {msg}", file=sys.stderr)


def session_folder(payload: dict) -> str:
    """<system temp>/auto-improve-codegraph-<session key>: the session_id when it matches the grammar, else
    ``cwd-`` + 16 hex digits of SHA-256 of the normalised cwd (the process cwd when the payload has none)."""
    sid = payload.get("session_id")
    if isinstance(sid, str) and _SESSION_ID_RE.fullmatch(sid):
        key = sid
    else:
        cwd = payload.get("cwd")
        cwd = cwd if isinstance(cwd, str) and cwd else os.getcwd()
        key = "cwd-" + hashlib.sha256(os.path.normcase(os.path.normpath(cwd)).encode("utf-8", "replace")).hexdigest()[:16]
    return os.path.join(tempfile.gettempdir(), SESSION_PREFIX + key)


def folder_usable(folder: str) -> bool:
    """Create the folder when absent; False when it is a link, not a folder, another user's, or not writable."""
    try:
        os.mkdir(folder, 0o700)
    except FileExistsError:
        pass
    except OSError as e:
        log(f"could not create {folder}: {e}")
        return False
    try:
        st = os.lstat(folder)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode) or (getattr(st, "st_file_attributes", 0) & _REPARSE_POINT) or not stat.S_ISDIR(st.st_mode):
        return False
    if hasattr(os, "getuid") and st.st_uid != os.getuid():
        return False
    return os.access(folder, os.W_OK)


def write_marker(payload: dict, tool_name: str, tool_input: dict) -> None:
    folder = session_folder(payload)
    if not folder_usable(folder):
        log(f"the session folder {folder} cannot be used; the marker was not written")
        return

    # Best-effort first-80-chars summary of the tool input for debug.
    summary = ""
    try:
        for key in ("query", "pattern", "id", "symbol", "name", "path", "file_path"):
            v = tool_input.get(key)
            if isinstance(v, str) and v:
                summary = v[:80]
                break
        if not summary:
            summary = json.dumps(tool_input, ensure_ascii=False)[:80]
    except Exception:  # noqa: BLE001
        summary = ""

    body = {
        "ts": int(time.time()),
        "tool": tool_name,
        "summary": summary,
        "pid": os.getpid(),
    }
    target = os.path.join(folder, MARKER_NAME)
    # A random sibling created with O_EXCL (O_NOFOLLOW where available), then os.replace onto the final name: the
    # final name is never opened for writing, so a link planted there is replaced, not written through.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    temp = os.path.join(folder, ".tmp-" + os.urandom(8).hex())
    try:
        fd = os.open(temp, flags, 0o600)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write((json.dumps(body, ensure_ascii=False) + "\n").encode("utf-8"))
            os.replace(temp, target)
        except OSError:
            try:
                os.remove(temp)
            except OSError:
                pass
            raise
    except OSError as e:
        log(f"could not write the marker {target}: {e}")


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        log(f"failed to parse stdin payload: {e}")
        sys.exit(0)
    if not isinstance(payload, dict):
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    # Match Claude Code MCP tool naming convention: mcp__<server>__<tool>. Any CodeGraph tool opens the turn.
    if not isinstance(tool_name, str) or not tool_name.startswith("mcp__codegraph__"):
        sys.exit(0)

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    write_marker(payload, tool_name, tool_input)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        log(f"internal error (failing open): {e}")
        sys.exit(0)
