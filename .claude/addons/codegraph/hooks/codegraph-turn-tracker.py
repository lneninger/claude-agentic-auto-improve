#!/usr/bin/env python3
"""
codegraph-turn-tracker.py -- PostToolUse hook that marks the current
investigation turn as having used CodeGraph.

When any mcp__codegraph__* tool completes (even with an error, and whatever
its name: a legacy, current or future tool), this hook writes the Turn marker
``turn.json`` in the session's folder under the Per-user session parent:

    <Per-user session parent>/auto-improve-codegraph-<session key>/turn.json

The Per-user session parent is the folder ``auto-improve-codegraph`` in
``%LOCALAPPDATA%`` on Windows, and in ``$XDG_CACHE_HOME`` (else ``~/.cache``,
mode 0700) on POSIX. The system temp folder is never used (issue #271). When the
parent or the session folder cannot be used, no marker is written, one line says
why and that the gate stays shut, and the hook still exits 0.

The marker is stamped ``writer`` = ``codegraph-turn-tracker`` (see MARKER_WRITER) and
``session`` = the session key, so the guard can tell a marker this tracker wrote
from a Foreign marker. It is keyed to the SESSION, not to the working directory,
so a ``cd`` or ``EnterWorktree`` does not close the gate again. Its presence
opens the codegraph-first-guard gate for Read / Grep / Glob during the rest of
the turn.

Hook contract (Claude Code):
    stdin:  JSON with { session_id, cwd, tool_name, tool_input: {...}, ... }
    exit 0: always (this hook never blocks)
    other:  fail-soft -- log to stderr, exit 0

Fail-soft is critical: this hook must not impede the PostToolUse pipeline.
"""

from __future__ import annotations

import hashlib
import json
import ntpath
import os
import posixpath
import re
import stat
import sys
import time

SESSION_PREFIX = "auto-improve-codegraph-"
MARKER_NAME = "turn.json"
MARKER_WRITER = "codegraph-turn-tracker"
_SESSION_ID_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9_-])?")  # never ends in "." (Windows strips it)
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def log(msg: str) -> None:
    try:
        sys.stderr.reconfigure(errors="backslashreplace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    try:
        print(f"[codegraph-turn-tracker] {msg}", file=sys.stderr)
    except Exception:  # noqa: BLE001 - a diagnostic line must never change the verdict
        pass


def _is_link_stat(st: os.stat_result) -> bool:
    """Delivery cleanup's link test: a symlink, or on Windows a reparse point (junction). Never a Python 3.12-only helper."""
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & _REPARSE_POINT)


# ---------------------------------------------------------------------------
# Per-user session parent (issue #271). One inline copy in each of the three codegraph hooks, pinned by a parity test:
# an add-on copies a helper only when the project lacks it, so an old helper must not be a dependency.
# ---------------------------------------------------------------------------
PARENT_NAME = "auto-improve-codegraph"
#: The closed set of Parent problems. The Session folder inside a usable parent adds ``session-<link / not-a-folder /
#: foreign-owner / unwritable / check-failed>``.
PARENT_PROBLEMS = ("unset", "not-absolute", "remote", "cannot-create", "link", "not-a-folder", "foreign-owner",
                   "open-mode", "unwritable", "check-failed")
_LOCAL_DEVICE_HOST_RE = re.compile(r"\?[a-z]:")


def _remote_host(text: str) -> str | None:
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


def _own_spellings(path: str) -> tuple:
    """The spellings of a tree's own path that count for the same-host rule: the written form, plus its
    ``os.path.realpath`` form when the written form is local (a mapped drive resolves to ``\\\\server\\share``).
    A path already written as UNC or device is never resolved: that would touch its host."""
    return (path,) if _remote_host(path) is not None else (path, os.path.realpath(path))


def session_parent_base(env, os_name: str) -> tuple:
    """The Parent base rule, a pure function of the environment mapping and the OS name: ``(base, problem)``. It reads
    ONLY ``env`` (no expanduser, no pwd, no os.environ). Windows: ``LOCALAPPDATA``. POSIX: ``XDG_CACHE_HOME``, and when
    that is unset or empty ``HOME`` + ``/.cache`` (the XDG default); both unset or empty gives ``unset``. A set but
    relative value gives ``not-absolute`` and is never skipped to the next name. On Windows a base that is a network
    path (any spelling ``_own_spellings`` gives has a host that is not the local-drive form) gives ``remote``; the
    empty host of a device path counts as remote. Exactly one of the two is None."""
    if os_name == "nt":
        path_module, raw = ntpath, env.get("LOCALAPPDATA") or ""
    else:
        path_module, raw = posixpath, env.get("XDG_CACHE_HOME") or ""
        if not raw:
            home = env.get("HOME") or ""
            raw = posixpath.join(home, ".cache") if home else ""
    if not raw:
        return None, "unset"
    if os_name == "nt" and raw.replace("\\", "/")[:4] == "/??/":
        return None, "remote"  # the NT object-manager prefix reaches any device or share: refused from the text, no I/O
    if os_name == "nt" and raw.replace("\\", "/")[:2] == "//" and raw.replace("\\", "/")[:4] not in ("//?/", "//./"):
        return None, "remote"  # '//' or '\\' that is not exactly the device prefix: a UNC host (or a spelling of one)
    if not path_module.isabs(raw):
        return None, "not-absolute"
    if os_name == "nt" and not ntpath.splitdrive(raw)[0]:
        return None, "not-absolute"  # rooted with no drive: Win32 would resolve it against the cwd's drive
    if os_name == "nt":
        slashed = raw.replace("\\", "/")
        device = slashed[:4] in ("//?/", "//./")
        if device and ".." in slashed.split("/"):
            return None, "remote"  # Win32 collapses the '..' before it opens the path: the text judged is not the path opened
        canon, stripped = raw, raw
        if device:
            rest = slashed[4:].lstrip("/").replace("/", "\\")  # doubled separators after the prefix collapse in Win32
            canon = "\\\\" + slashed[2] + "\\" + rest
            stripped = rest if rest[1:2] == ":" else ("\\\\" + rest[4:] if rest[:4].upper() == "UNC\\" else canon)
        letter = (stripped if stripped[1:2] == ":" else "")[:1]
        if letter and not (letter.isascii() and letter.isalpha()):
            return None, "not-absolute"  # a drive designator that is not an ASCII letter (1:, ' ':, .:)
        if letter:
            # a drive letter in any spelling: the drive table (no network I/O) is asked BEFORE any realpath
            try:
                import ctypes
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(letter + ":\\")
            except Exception as exc:  # noqa: BLE001 - undecidable is refused (a true diagnosis), never allowed
                return None, "check-failed", "%s: %s" % (type(exc).__name__, exc)
            if drive_type not in (2, 3, 6):  # removable, fixed, ram disk; every other answer (remote, cd-rom, unknown) is refused
                return None, "remote"
        texts = [raw, canon]
        full_name = getattr(ntpath, "_getfullpathname", None)  # no I/O: the same collapse Win32 does
        if full_name is not None:
            try:
                texts.append(full_name(stripped))
            except (OSError, ValueError):
                return None, "remote"
        for text in texts:
            for spelling in _own_spellings(text):
                host = _remote_host(spelling)
                if host is not None and not _LOCAL_DEVICE_HOST_RE.fullmatch(host):
                    return None, "remote"
    return raw, None


def _base_shown(env, os_name: str) -> str:
    """The setting a base problem is about, for a message: its value, else the variable's name."""
    if os_name == "nt":
        return env.get("LOCALAPPDATA") or "LOCALAPPDATA"
    return env.get("XDG_CACHE_HOME") or env.get("HOME") or "XDG_CACHE_HOME or HOME"


def _create_parent(base: str, parent: str) -> str | None:
    """Create the Per-user session parent with mode 0700: one ``mkdir``, never ``makedirs``. Windows: the base must
    exist and is never created. POSIX: a missing base is created (one level, 0700) only when its own parent exists; a
    deeper missing chain is ``cannot-create``. Returns None or the problem."""
    try:
        os.mkdir(parent, 0o700)
        return None
    except FileExistsError:
        return None
    except FileNotFoundError:
        if os.name == "nt":
            return "cannot-create"  # the base is never created on Windows
    except OSError:
        return "cannot-create"
    try:
        os.mkdir(base, 0o700)  # POSIX only: one level; its own parent must exist
    except FileExistsError:
        pass
    except OSError:
        return "cannot-create"
    try:
        os.mkdir(parent, 0o700)
    except FileExistsError:
        pass
    except OSError:
        return "cannot-create"
    return None


def resolve_session_parent() -> tuple:
    """The Per-user session parent of THIS call, from the environment at call time (never at import, so an in-process
    test can redirect it): ``(parent, problem, detail)``. ``problem`` is None when the parent is usable. ``parent`` is
    its path, or for a base problem the setting that failed. ``detail`` is the exception text of ``check-failed``.
    The parent gets every check (not a link, a folder, the user's own and closed to others on POSIX, writable); the
    base only the existence, text and remote rules, because a base that is a junction is legitimate (a moved
    AppData). Never raises: any exception while computing the verdict is ``check-failed`` (file facts come from
    ``os.lstat``)."""
    parent = ""
    try:
        verdict = session_parent_base(os.environ, os.name)  # (base, problem) or (None, "check-failed", exception text)
        base, problem = verdict[0], verdict[1]
        if problem:
            return _base_shown(os.environ, os.name), problem, (verdict[2] if len(verdict) > 2 else "")
        parent = os.path.join(base, PARENT_NAME)
        try:
            st = os.lstat(parent)
        except FileNotFoundError:
            problem = _create_parent(base, parent)
            if problem:
                return parent, problem, ""
            st = os.lstat(parent)
        if _is_link_stat(st):
            return parent, "link", ""
        if not stat.S_ISDIR(st.st_mode):
            return parent, "not-a-folder", ""
        if hasattr(os, "getuid"):
            if st.st_uid != os.getuid():
                return parent, "foreign-owner", ""
            if st.st_mode & 0o077:
                return parent, "open-mode", ""
        if not os.access(parent, os.W_OK):
            return parent, "unwritable", ""
        return parent, None, ""
    except Exception as exc:  # noqa: BLE001 - a hostile folder must reach check-failed, never the catch-all that allows
        return parent, "check-failed", "%s: %s" % (type(exc).__name__, exc)


def session_folder_problem(folder: str) -> tuple:
    """``(problem, detail)`` of a Session folder inside a usable parent; ``(None, "")`` when usable. An absent folder is
    usable (it is created on the first write)."""
    try:
        st = os.lstat(folder)
    except FileNotFoundError:
        return None, ""
    except Exception as exc:  # noqa: BLE001
        return "session-check-failed", "%s: %s" % (type(exc).__name__, exc)
    try:
        if _is_link_stat(st):
            return "session-link", ""
        if not stat.S_ISDIR(st.st_mode):
            return "session-not-a-folder", ""
        if hasattr(os, "getuid") and st.st_uid != os.getuid():
            return "session-foreign-owner", ""
        if not os.access(folder, os.W_OK):
            return "session-unwritable", ""
    except Exception as exc:  # noqa: BLE001
        return "session-check-failed", "%s: %s" % (type(exc).__name__, exc)
    return None, ""


def session_key(payload: dict) -> str:
    """The session_id when it matches the grammar, else ``cwd-`` + 16 hex digits of SHA-256 of the normalised cwd (the
    process cwd when the payload has none)."""
    sid = payload.get("session_id")
    if isinstance(sid, str) and _SESSION_ID_RE.fullmatch(sid):
        return sid
    cwd = payload.get("cwd")
    cwd = cwd if isinstance(cwd, str) and cwd else os.getcwd()
    return "cwd-" + hashlib.sha256(os.path.normcase(os.path.normpath(cwd)).encode("utf-8", "replace")).hexdigest()[:16]


def usable_session_folder(payload: dict) -> tuple:
    """``(folder, None)`` for a usable Session folder (created when absent), else ``(where, line)``: ``line`` is the
    message of an unusable verdict (the problem and that the gate stays shut)."""
    parent, problem, detail = resolve_session_parent()
    folder = ""
    if problem is None:
        folder = os.path.join(parent, SESSION_PREFIX + session_key(payload))
        problem, detail = session_folder_problem(folder)
        if problem is None:
            try:
                os.mkdir(folder, 0o700)
            except FileExistsError:
                pass
            except Exception as exc:  # noqa: BLE001
                problem, detail = "session-check-failed", "%s: %s" % (type(exc).__name__, exc)
            else:
                problem, detail = session_folder_problem(folder)
    if problem is None:
        return folder, None
    where = folder or parent
    extra = f": {detail}" if detail else ""
    return where, f"the per-user session folder {where} cannot be used ({problem}{extra}); the gate stays shut"


def write_marker(payload: dict, tool_name: str, tool_input: dict) -> None:
    folder, unusable = usable_session_folder(payload)
    if unusable:
        log(unusable)
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
        # The stamp: it lets the guard tell this marker from a Foreign marker (it detects, it never decides).
        "writer": MARKER_WRITER,
        "session": session_key(payload),
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
