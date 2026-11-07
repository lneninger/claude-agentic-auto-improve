#!/usr/bin/env python3
"""
codegraph-turn-tracker.py -- PostToolUse hook that marks the current
investigation turn as having used CodeGraph.

When any mcp__codegraph__* tool completes successfully (event PostToolUse, whatever
its name: a legacy, current or future tool), or a Bash call of a Counted ``codegraph``
command succeeds (the command-line route), this hook writes the Turn marker
``turn.json`` in the session's folder under the system temp folder:

    <system temp folder>/auto-improve-codegraph-<session key>/turn.json

The marker is keyed to the SESSION, not to the working directory, so a ``cd``
or ``EnterWorktree`` does not close the gate again. Its presence opens the
codegraph-first-guard gate for Read / Grep / Glob during the rest of the turn.

The success signal is the EVENT NAME: a failed tool call reaches the host's PostToolUseFailure event (never registered
here), and a payload of that event is ignored. Output text is never read.

Route: ``mcp`` (a MCP call) beats ``cli`` (the command line). ``mcp-seen`` is a sticky flag created after a MCP call.
The first command-line call of a session with no ``mcp-seen`` writes one ``cli-fallback`` record (``logged-cli-fallback``).

Hook contract (Claude Code):
    stdin:  JSON with { session_id, cwd, hook_event_name, tool_name, tool_input: {...}, ... }
    exit 0: always (this hook never blocks)
    other:  fail-soft -- log to stderr, exit 0

Fail-soft is critical: this hook must not impede the PostToolUse pipeline.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import stat
import sys
import tempfile
import time

SESSION_PREFIX = "auto-improve-codegraph-"
MARKER_NAME = "turn.json"
MCP_SEEN_NAME = "mcp-seen"
CLI_FALLBACK_FLAG = "logged-cli-fallback"
#: The Counted commands: the subcommands whose command line mirrors a CodeGraph MCP tool.
COUNTED_COMMANDS = frozenset({"query", "explore", "context", "node", "callers", "callees", "impact", "files"})
_CONTROL_RE = re.compile(r"[;&|<>`\n\r]|\$\(")
_SUMMARY_UNSAFE_RE = re.compile(r"[^A-Za-z0-9_. -]+")
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


def counted_subcommand(tool_input: dict) -> tuple[str, str] | None:
    """(subcommand, summary) when the Bash command is a Counted command in the strict form, else None.

    One simple command, an optional single trailing `` 2>&1``, no control operator, no background run; the raw text starts
    with ``codegraph `` and token 0 is exactly ``codegraph``. That is narrower than the row's ``if``, which matches each
    sub-command of a compound command and strips ``VAR=`` prefixes, so the host starts this hook for forms it does not count."""
    command = tool_input.get("command")
    if not isinstance(command, str) or tool_input.get("run_in_background"):
        return None
    text = command[:-5] if command.endswith(" 2>&1") else command
    if _CONTROL_RE.search(text) or not command.startswith("codegraph "):
        return None
    try:
        tokens = shlex.split(text, posix=True)
    except ValueError:
        return None
    if len(tokens) < 2 or tokens[0] != "codegraph" or tokens[1] not in COUNTED_COMMANDS:
        return None
    summary = _SUMMARY_UNSAFE_RE.sub(" ", " ".join(tokens[1:3])).strip()[:80]
    return tokens[1], summary


def bash_succeeded(payload: dict) -> bool:
    """A Bash PostToolUse that carries no failure mark: ``tool_response`` is an object and it was neither interrupted nor an
    error. The host sends no exit-code field; a failed call arrives as PostToolUseFailure, which main() already refused."""
    response = payload.get("tool_response")
    if not isinstance(response, dict):
        return False
    return not any(response.get(key) is True for key in ("interrupted", "is_error", "isError"))


def existing_route(folder: str) -> str | None:
    """The route of the Turn marker already in the folder (``mcp`` for one with no route), or None when there is none."""
    try:
        with open(os.path.join(folder, MARKER_NAME), "r", encoding="utf-8") as fh:
            body = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(body, dict):
        return None
    return "cli" if body.get("route") == "cli" else "mcp"


def create_flag(folder: str, name: str) -> bool:
    """Create an empty flag file; True when it exists afterwards."""
    try:
        fd = os.open(os.path.join(folder, name), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return True
    except OSError:
        return False
    os.close(fd)
    return True


def record_cli_fallback(payload: dict, folder: str, subcommand: str) -> None:
    """The once-per-session ``cli-fallback`` record: a counted command-line call was accepted and no MCP call has succeeded
    this session. The flag is created only after the record landed."""
    if os.path.lexists(os.path.join(folder, MCP_SEEN_NAME)) or os.path.lexists(os.path.join(folder, CLI_FALLBACK_FLAG)):
        return
    try:
        from _error_log import log_event
    except Exception:  # noqa: BLE001 - the helper is optional: no record, no flag
        return
    sid = payload.get("session_id")
    landed = log_event(hook="codegraph-turn-tracker", event="cli-fallback",
                       session_id=sid if isinstance(sid, str) and sid else None,
                       details={"reason": "mcp-unavailable", "command": subcommand})
    if landed is not False:
        create_flag(folder, CLI_FALLBACK_FLAG)


def write_marker(payload: dict, tool_name: str, tool_input: dict, route: str = "mcp", summary: str | None = None) -> str | None:
    """Write the Turn marker; return the session folder, or None when nothing was written."""
    folder = session_folder(payload)
    if not folder_usable(folder):
        log(f"the session folder {folder} cannot be used; the marker was not written")
        return None
    if route == "cli" and existing_route(folder) == "mcp":
        return folder  # the stronger route of the turn stays

    # Best-effort first-80-chars summary of the tool input for debug.
    if summary is None:
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
        "route": route,
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
        return None
    return folder


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        log(f"failed to parse stdin payload: {e}")
        sys.exit(0)
    if not isinstance(payload, dict):
        sys.exit(0)

    # The success signal is the event name: a PostToolUseFailure payload (a failed call) never opens the gate. A payload that
    # names no event (an older host) is read as before.
    event = payload.get("hook_event_name")
    if event is not None and event != "PostToolUse":
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    if not isinstance(tool_name, str):
        sys.exit(0)

    # Match Claude Code MCP tool naming convention: mcp__<server>__<tool>. Any CodeGraph tool opens the turn.
    if tool_name.startswith("mcp__codegraph__"):
        response = payload.get("tool_response")
        folder = write_marker(payload, tool_name, tool_input, route="mcp")
        if folder is not None and not (isinstance(response, dict) and (response.get("is_error") is True or response.get("isError") is True)):
            create_flag(folder, MCP_SEEN_NAME)
        sys.exit(0)

    # The command-line route: a Counted command in the Bash tool that succeeded.
    if tool_name == "Bash":
        counted = counted_subcommand(tool_input)
        if counted is not None and bash_succeeded(payload):
            subcommand, summary = counted
            folder = write_marker(payload, "codegraph " + subcommand, tool_input, route="cli", summary=summary)
            if folder is not None:
                record_cli_fallback(payload, folder, subcommand)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        log(f"internal error (failing open): {e}")
        sys.exit(0)
