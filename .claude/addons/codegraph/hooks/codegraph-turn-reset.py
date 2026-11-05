#!/usr/bin/env python3
"""
codegraph-turn-reset.py -- UserPromptSubmit hook that resets the
CodeGraph-first investigation turn.

Each new user prompt starts a new "investigation turn." The first
mcp__codegraph__* call within the turn opens the gate for Read / Grep /
Glob; subsequent prompts close the gate again. This hook deletes, in the
session's folder under the system temp folder
(``<system temp>/auto-improve-codegraph-<session key>/``):

    * the Turn marker ``turn.json``
    * every Retry escape ticket ``ticket-<64 hex>``

and the legacy ``<cwd>/.claude/.codegraph-used-this-turn`` file an earlier
release wrote, if one is present.

It also prunes the system temp folder ONCE PER SESSION (on the first prompt;
the ``pruned`` flag in the session's folder records it): a leftover
``auto-improve-codegraph-*`` folder of an old session is deleted, file by file,
when it is safe to (see ``prune_session_folders``). Delivery cleanup's rules
apply: a link is never followed, another user's folder is never touched, a
folder holding anything this hook does not know is kept whole, and the removal
never uses a recursive delete.

Hook contract (Claude Code):
    stdin:  JSON with { session_id, cwd, prompt, ... }
    exit 0: always (this hook never blocks the prompt)

Fail-soft: any failure is silent.
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
TICKET_RE = re.compile(r"ticket-[0-9a-f]{64}|\.tmp-[0-9a-f]{16}")
PRUNED_FLAG = "pruned"
LEGACY_SENTINEL_NAME = ".codegraph-used-this-turn"
#: The only file names a session folder may hold (the atomic-write ``.tmp-<16 hex>`` siblings included); a folder with any other entry is kept whole.
#: The shadow's Transcript cursor ``transcript-cursor.json`` and its temp file ``transcript-cursor.<pid>.tmp`` are known names (issue #261).
KNOWN_FILE_RE = re.compile(
    r"turn\.json|availability\.json|pruned|logged-[a-z0-9-]+|ticket-[0-9a-f]{64}|\.tmp-[0-9a-f]{16}"
    r"|transcript-cursor\.json|transcript-cursor\.[0-9]+\.tmp")
#: A session folder younger than this (by its newest file) is never pruned.
MIN_AGE_SECONDS = 7 * 24 * 60 * 60
_SESSION_ID_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9_-])?")  # never ends in "." (Windows strips it)
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def log(msg: str) -> None:
    print(f"[codegraph-turn-reset] {msg}", file=sys.stderr)


def _is_link_stat(st: os.stat_result) -> bool:
    """Delivery cleanup's link test: a symlink, or on Windows a reparse point. Never a Python 3.12-only helper."""
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & _REPARSE_POINT)


def _plain_file(path: str) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISREG(st.st_mode) and not _is_link_stat(st)


def _usable_folder(folder: str) -> bool:
    """An existing folder that is not a link, is ours (POSIX) and is writable."""
    try:
        st = os.lstat(folder)
    except OSError:
        return False
    if _is_link_stat(st) or not stat.S_ISDIR(st.st_mode):
        return False
    if hasattr(os, "getuid") and st.st_uid != os.getuid():
        return False
    return os.access(folder, os.W_OK)


def session_folder(payload: dict) -> str:
    sid = payload.get("session_id")
    if isinstance(sid, str) and _SESSION_ID_RE.fullmatch(sid):
        key = sid
    else:
        cwd = payload.get("cwd")
        cwd = cwd if isinstance(cwd, str) and cwd else os.getcwd()
        key = "cwd-" + hashlib.sha256(os.path.normcase(os.path.normpath(cwd)).encode("utf-8", "replace")).hexdigest()[:16]
    return os.path.join(tempfile.gettempdir(), SESSION_PREFIX + key)


def _delete_marker_and_tickets(folder: str) -> None:
    if not _usable_folder(folder):
        return
    try:
        names = os.listdir(folder)
    except OSError as e:
        log(f"could not list {folder}: {e}")
        return
    for name in names:
        if name == MARKER_NAME or TICKET_RE.fullmatch(name):
            path = os.path.join(folder, name)
            if not _plain_file(path):
                continue
            try:
                os.remove(path)
            except OSError as e:
                log(f"could not delete {path}: {e}")


def _delete_legacy_sentinels(payload: dict) -> None:
    cwds = []
    value = payload.get("cwd")
    if isinstance(value, str) and value:
        cwds.append(value)
    cwds.append(os.getcwd())
    seen = set()
    for cwd in cwds:
        path = os.path.join(cwd, ".claude", LEGACY_SENTINEL_NAME)
        if path in seen:
            continue
        seen.add(path)
        if _plain_file(path):
            try:
                os.remove(path)
            except OSError as e:
                log(f"could not delete the legacy sentinel {path}: {e}")


def _no_op(_path: str) -> None:
    return None


def _eligible_files(folder: str, now: float):
    """The file names to delete in ``folder``, or None when the folder must be kept (the Folder test)."""
    try:
        st = os.lstat(folder)
    except OSError:
        return None
    if _is_link_stat(st) or not stat.S_ISDIR(st.st_mode):
        return None
    if hasattr(os, "getuid") and st.st_uid != os.getuid():
        return None
    try:
        names = os.listdir(folder)
    except OSError:
        return None
    newest = st.st_mtime if not names else 0.0
    for name in names:
        if not KNOWN_FILE_RE.fullmatch(name):
            return None
        try:
            fst = os.lstat(os.path.join(folder, name))
        except OSError:
            return None
        if not stat.S_ISREG(fst.st_mode) or _is_link_stat(fst):
            return None
        newest = max(newest, fst.st_mtime)
    if now - newest < MIN_AGE_SECONDS:
        return None
    return names


def _remove_folder(folder: str, names: list, before_remove) -> bool:
    """Delete the known files one at a time, re-checking each immediately before its removal, then the empty
    folder with ``os.rmdir``. Any mismatch stops and keeps the rest."""
    real_folder = os.path.normcase(os.path.realpath(folder))
    for name in names:
        path = os.path.join(folder, name)
        try:
            before_remove(path)
        except Exception:  # noqa: BLE001 - a failing seam keeps the folder
            return False
        try:
            fst = os.lstat(folder)
            st = os.lstat(path)
        except OSError:
            return False
        if _is_link_stat(fst) or not stat.S_ISDIR(fst.st_mode):
            return False
        if not stat.S_ISREG(st.st_mode) or _is_link_stat(st) or not KNOWN_FILE_RE.fullmatch(name):
            return False
        if os.path.normcase(os.path.realpath(os.path.dirname(path))) != real_folder:
            return False
        try:
            os.remove(path)
        except OSError:
            return False
    try:
        fst = os.lstat(folder)
        if _is_link_stat(fst) or not stat.S_ISDIR(fst.st_mode):
            return False
        os.rmdir(folder)
    except OSError:
        return False
    return True


def prune_session_folders(temp_root, before_remove=_no_op, now=None) -> list:
    """Delete the leftover ``auto-improve-codegraph-*`` folders of old sessions in ``temp_root``; return their names.

    A folder is skipped (never deleted) when it is a link or not a folder, when on POSIX it is owned by another
    user, when it holds anything other than plain, non-link files named ``turn.json``, ``availability.json``,
    ``pruned``, ``logged-<reason>``, ``ticket-<64 hex>``, ``transcript-cursor.json`` or ``transcript-cursor.<digits>.tmp``,
    or when its newest file is younger than 7 days.
    Immediately before each ``os.remove`` the file and the folder are checked again (still plain, still known,
    the folder still not a link, the file's real parent still the folder's real path); any mismatch stops and keeps
    the rest. The folder goes with ``os.rmdir`` (never a recursive delete).

    ``before_remove(path)`` is a test seam, called after the folder test and immediately before each per-file
    re-check; the default does nothing.
    """
    removed: list = []
    moment = time.time() if now is None else now
    try:
        entries = os.listdir(str(temp_root))
    except OSError:
        return removed
    for entry in entries:
        if not entry.startswith(SESSION_PREFIX):
            continue
        folder = os.path.join(str(temp_root), entry)
        names = _eligible_files(folder, moment)
        if names is None:
            continue
        if _remove_folder(folder, names, before_remove):
            removed.append(entry)
    return removed


def _first_prompt_of_session(folder: str) -> bool:
    """True only on the first call of a session: creates the ``pruned`` flag in the session's folder."""
    try:
        os.mkdir(folder, 0o700)
    except FileExistsError:
        pass
    except OSError:
        return False
    if not _usable_folder(folder):
        return False
    try:
        fd = os.open(os.path.join(folder, PRUNED_FLAG), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        return False
    os.close(fd)
    return True


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (ValueError, OSError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    folder = session_folder(payload)
    _delete_marker_and_tickets(folder)
    _delete_legacy_sentinels(payload)
    if _first_prompt_of_session(folder):
        prune_session_folders(tempfile.gettempdir())
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        log(f"internal error (failing open): {e}")
        sys.exit(0)
