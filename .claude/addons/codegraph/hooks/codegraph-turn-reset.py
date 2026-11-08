#!/usr/bin/env python3
"""
codegraph-turn-reset.py -- UserPromptSubmit hook that resets the
CodeGraph-first investigation turn.

Each new user prompt starts a new "investigation turn." The first
mcp__codegraph__* call (or successful Counted ``codegraph`` command in the
Bash tool) within the turn opens the gate for Read / Grep /
Glob; subsequent prompts close the gate again. This hook deletes, in the
session's folder under the Per-user session parent
(``<Per-user session parent>/auto-improve-codegraph-<session key>/``):

    * the Turn marker ``turn.json``
    * every Retry escape ticket ``ticket-<64 hex>``

and the legacy ``<cwd>/.claude/.codegraph-used-this-turn`` file an earlier
release wrote, if one is present.

The Per-user session parent is the folder ``auto-improve-codegraph`` in
``%LOCALAPPDATA%`` on Windows, and in ``$XDG_CACHE_HOME`` (else ``~/.cache``,
mode 0700) on POSIX. The system temp folder is never listed, read or pruned
(issue #271). When the parent or the session folder cannot be used, this hook
deletes and prunes nothing under the parent, prints one line saying why and
that the gate stays shut, and still removes the legacy sentinel.

It also prunes the Per-user session parent ONCE PER SESSION (on the first prompt;
the ``pruned`` flag in the session's folder records it): a leftover
``auto-improve-codegraph-*`` folder of an old session is deleted, file by file,
when it is safe to (see ``prune_session_folders``). Delivery cleanup's rules
apply: a link is never followed, another user's folder is never touched, a
folder holding anything this hook does not know is kept whole, and the removal
never uses a recursive delete.

After the deletions it runs the CONNECTION NOTICE (``notice_section``): when the CodeGraph server is configured and the
index exists but no ``codegraph serve --mcp`` process belongs to this session, it prints one JSON object (a ``systemMessage``
for the user and the same text as ``additionalContext`` for the model). Silent on a healthy session, when it cannot decide,
for a subagent, and on any failure; it writes no file and never changes the exit code. There is no switch that turns it off.

Hook contract (Claude Code):
    stdin:  JSON with { session_id, cwd, prompt, ... }
    exit 0: always (this hook never blocks the prompt)
    stdout: nothing, or the one notice object

Fail-soft: any failure is silent.
"""

from __future__ import annotations

import hashlib
import json
import ntpath
import os
import posixpath
import re
import stat
import subprocess
import sys
import time
from pathlib import Path

SESSION_PREFIX = "auto-improve-codegraph-"
MARKER_NAME = "turn.json"
TICKET_RE = re.compile(r"ticket-[0-9a-f]{64}|\.tmp-[0-9a-f]{16}")
PRUNED_FLAG = "pruned"
LEGACY_SENTINEL_NAME = ".codegraph-used-this-turn"
#: The only file names a session folder may hold (the atomic-write ``.tmp-<16 hex>`` siblings included); a folder with any other entry is kept whole.
#: The shadow's Transcript cursor ``transcript-cursor.json`` and its temp file ``transcript-cursor.<pid>.tmp`` are known names (issue #261).
KNOWN_FILE_RE = re.compile(
    r"turn\.json|mcp-seen|availability\.json|pruned|logged-[a-z0-9-]+|ticket-[0-9a-f]{64}|\.tmp-[0-9a-f]{16}"
    r"|transcript-cursor\.json|transcript-cursor\.[0-9]+\.tmp")
#: A session folder younger than this (by its newest file) is never pruned.
MIN_AGE_SECONDS = 7 * 24 * 60 * 60
_SESSION_ID_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9_-])?")  # never ends in "." (Windows strips it)
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def log(msg: str) -> None:
    try:
        sys.stderr.reconfigure(errors="backslashreplace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    try:
        print(f"[codegraph-turn-reset] {msg}", file=sys.stderr)
    except Exception:  # noqa: BLE001 - a diagnostic line must never change the verdict
        pass


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


def prune_session_folders(root, before_remove=_no_op, now=None) -> list:
    """Delete the leftover ``auto-improve-codegraph-*`` folders of old sessions in ``root`` (the caller's own Per-user
    session parent, passed only after a usable parent verdict; never the system temp folder); return their names.

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
        entries = os.listdir(str(root))
    except OSError:
        return removed
    for entry in entries:
        if not entry.startswith(SESSION_PREFIX):
            continue
        folder = os.path.join(str(root), entry)
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


# ---------------------------------------------------------------------------
# Connection probe and notice (issue #295)
# ---------------------------------------------------------------------------
#: Images (lower case, ``.exe`` stripped) the walk up from the hook skips: Python interpreters, launchers and shells.
SKIP_IMAGES = frozenset({"python", "python3", "pythonw", "py", "bash", "sh", "dash", "zsh", "cmd", "powershell", "pwsh", "env"})
#: The Hook host process images recorded from a live trial (native ``claude``); any other image is not trusted.
HOST_IMAGES = frozenset({"claude"})
MAX_HOPS = 8
MAX_DEPTH = 4
NOTICE_BUDGET_S = 0.1
GUARD_FILE = "codegraph-first-guard.py"
_STRIP_SUFFIXES = (".exe", ".cmd", ".bat", ".js", ".mjs", ".cjs")
_QUOTE_RE = re.compile(r"[\^\"']")

NOTICE_TEXT = (
    "CodeGraph connection notice: no `codegraph serve --mcp` process belongs to this session, so the "
    "mcp__codegraph__* tools are likely gone. Run /mcp to reconnect them. Meanwhile a CodeGraph command in the Bash tool, "
    "run on its own (for example `codegraph explore \"SymbolName\"`; also query, context, node, callers, callees, impact, "
    "files), opens the gate for the turn. In a worktree the command line reads the main checkout's index unless one was "
    "built there. "
    "A project instruction or a skill's explicit gate that forbids shell commands wins over this notice; follow that rule instead."
)


def _image_key(image) -> str:
    key = str(image or "").lower()
    return key[:-4] if key.endswith(".exe") else key


def _walk_to_host(table, start_pid):
    """(host pid, the hook's ancestor pids up to the host) or (None, reason): ``host-untrusted`` when the start process is
    unknown, the walk runs out, passes 8 hops, or meets an image that is neither skipped nor a known host."""
    by_pid = {row[0]: row for row in table}
    chain = [start_pid]
    current = by_pid.get(start_pid)
    if current is None:
        return None, "host-untrusted"
    for _hop in range(MAX_HOPS):
        parent = by_pid.get(current[1])
        if parent is None or parent[0] in chain:
            return None, "host-untrusted"
        key = _image_key(parent[2])
        if key in HOST_IMAGES:
            return parent[0], chain
        if key not in SKIP_IMAGES:
            return None, "host-untrusted"
        chain.append(parent[0])
        current = parent
    return None, "host-untrusted"


def _candidate_pids(table, host_pid, chain):
    """Every descendant of the host within 4 levels, of any image, leaving out the hook's own ancestor chain."""
    children: dict = {}
    for pid, parent, _image, _cmd in table:
        children.setdefault(parent, []).append(pid)
    found, level, seen = [], [host_pid], {host_pid}
    for _depth in range(MAX_DEPTH):
        nxt = []
        for pid in level:
            for child in children.get(pid, ()):
                if child in seen or child in chain:
                    continue
                seen.add(child)
                nxt.append(child)
        found.extend(nxt)
        level = nxt
    return found


def _is_codegraph_token(token: str) -> bool:
    parts = [p for p in re.split(r"[\\/]", token) if p]
    if not parts:
        return False
    base = parts[-1].lower()
    for suffix in _STRIP_SUFFIXES:
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return base == "codegraph" or any(p.lower() == "codegraph" for p in parts[:-1])


def _judge(cmdline):
    """``match``, ``ambiguous`` (serve and --mcp without a CodeGraph token, or an unreadable line) or ``other``."""
    if cmdline is None:
        return "ambiguous"
    tokens = _QUOTE_RE.sub("", cmdline).split()
    if "serve" not in tokens or "--mcp" not in tokens:
        return "other"
    return "match" if any(_is_codegraph_token(t) for t in tokens) else "ambiguous"


def _probe(table, start_pid):
    host, chain = _walk_to_host(table, start_pid)
    if host is None:
        return "undecidable", chain
    by_pid = {row[0]: row for row in table}
    verdicts = [_judge(by_pid[pid][3]) for pid in _candidate_pids(table, host, set(chain))]
    if "match" in verdicts:
        return "present", ""
    if "ambiguous" in verdicts:
        return "undecidable", "undecidable"
    return "absent", ""


def connection_probe(table, start_pid):
    """``present`` / ``absent`` / ``undecidable`` over a list of (pid, parent pid, image, command line or None): is there a
    ``codegraph serve --mcp`` process under this session's Hook host process?"""
    return _probe(table, start_pid)[0]


def command_line(pid):
    """The exact command line of process ``pid`` on Windows (``NtQueryInformationProcess`` class 60), or None when it cannot
    be read."""
    import ctypes
    from ctypes import wintypes

    class UnicodeString(ctypes.Structure):
        _fields_ = [("Length", ctypes.c_ushort), ("MaximumLength", ctypes.c_ushort), ("Buffer", ctypes.c_void_p)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll")
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    ntdll.NtQueryInformationProcess.restype = ctypes.c_long
    ntdll.NtQueryInformationProcess.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong,
                                                ctypes.POINTER(ctypes.c_ulong)]
    handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        size = 1024
        for _try in range(3):
            buf = ctypes.create_string_buffer(size)
            needed = ctypes.c_ulong(0)
            status = ntdll.NtQueryInformationProcess(handle, 60, buf, size, ctypes.byref(needed))  # ProcessCommandLine
            if status == 0:
                text = UnicodeString.from_buffer(buf)
                return ctypes.wstring_at(text.Buffer, text.Length // 2) if text.Buffer else ""
            if (status & 0xFFFFFFFF) in (0xC0000004, 0xC0000023, 0x80000005) and needed.value > size:
                size = needed.value
                continue
            return None
        return None
    finally:
        k32.CloseHandle(handle)


def _read_table_windows(start_pid):
    import ctypes
    from ctypes import wintypes

    class ProcessEntry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", wintypes.WCHAR * 260)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ProcessEntry)]
    k32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ProcessEntry)]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    snapshot = k32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if snapshot is None or snapshot == ctypes.c_void_p(-1).value:
        raise OSError("CreateToolhelp32Snapshot failed")
    rows = []
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(ProcessEntry)
        ok = k32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            rows.append((int(entry.th32ProcessID), int(entry.th32ParentProcessID), entry.szExeFile))
            ok = k32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snapshot)

    bare = [(pid, parent, image, None) for pid, parent, image in rows]
    # Read command lines only where the probe will look: the descendants of the Hook host process.
    host, chain = _walk_to_host(bare, start_pid) if start_pid is not None else (None, [])
    wanted = set(_candidate_pids(bare, host, set(chain))) if host is not None else set()
    return [(pid, parent, image, command_line(pid) if pid in wanted else None) for pid, parent, image, _c in bare]


def _read_table_linux():
    rows = []
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open("/proc/%s/stat" % name, "rb") as fh:
                stat_text = fh.read().decode("utf-8", "replace")
            comm = stat_text[stat_text.index("(") + 1: stat_text.rindex(")")]
            parent = int(stat_text[stat_text.rindex(")") + 2:].split()[1])
            with open("/proc/%s/cmdline" % name, "rb") as fh:
                cmd = fh.read().decode("utf-8", "replace").replace("\0", " ").strip()
        except (OSError, ValueError):
            continue
        rows.append((int(name), parent, comm, cmd or None))
    return rows


def _read_table_ps(timeout):
    out = subprocess.run(["ps", "-axo", "pid=,ppid=,command="], capture_output=True, text=True, timeout=max(timeout, 0.01),
                         check=False).stdout
    rows = []
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3 or not parts[0].isdigit() or not parts[1].isdigit():
            continue
        first = parts[2].split()[0]
        rows.append((int(parts[0]), int(parts[1]), os.path.basename(first), parts[2]))
    return rows


def read_process_table(start_pid=None, timeout=NOTICE_BUDGET_S):
    """The process table as (pid, parent pid, image, command line or None). The ONLY platform code of the probe.
    Windows: Toolhelp32 and ``NtQueryInformationProcess`` (class 60) through ctypes; Linux: ``/proc``; macOS: ``ps``;
    any other platform: an empty table (the probe is then undecidable)."""
    if sys.platform == "win32":
        return _read_table_windows(start_pid)
    if sys.platform.startswith("linux"):
        return _read_table_linux()
    if sys.platform == "darwin":
        return _read_table_ps(timeout)
    return []


def _load_guard():
    """The sibling guard module, loaded by path with bytecode writing off. Raises when it is absent or fails to load."""
    path = Path(__file__).resolve().with_name(GUARD_FILE)
    from importlib import util
    spec = util.spec_from_file_location("_codegraph_first_guard_notice", str(path))
    if spec is None or spec.loader is None:
        raise ImportError("cannot load " + str(path))
    module = util.module_from_spec(spec)
    sys.modules[spec.name] = module  # a dataclass in the module reads itself back from sys.modules
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    return module


def notice_section(payload) -> str:
    """The Connection notice. Returns a closed-set outcome (``shown``, ``silent:probe-present``, ``silent:precondition``,
    ``silent:host-untrusted``, ``silent:undecidable``, ``silent:import-failed``, ``silent:budget``, ``silent:error``); prints
    the notice JSON itself only for ``shown``. Writes no file (no bytecode): ``sys.dont_write_bytecode`` is set throughout."""
    started = time.monotonic()
    saved_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        payload = payload if isinstance(payload, dict) else {}
        agent_id = payload.get("agent_id")
        if isinstance(agent_id, str) and agent_id:
            return "silent:precondition"
        try:
            guard = _load_guard()
        except Exception:  # noqa: BLE001
            return "silent:import-failed"
        if time.monotonic() - started > NOTICE_BUDGET_S:
            return "silent:budget"
        cwd = payload.get("cwd")
        cwd = cwd if isinstance(cwd, str) and cwd else os.getcwd()
        server, index, _body = guard.availability_plan(guard.Session(payload), cwd)
        if server != "configured" or index != "index-present" or not guard.server_starts_process(cwd):
            return "silent:precondition"
        if time.monotonic() - started > NOTICE_BUDGET_S:
            return "silent:budget"
        table = read_process_table(os.getpid(), max(NOTICE_BUDGET_S - (time.monotonic() - started), 0.01))
        if time.monotonic() - started > NOTICE_BUDGET_S:
            return "silent:budget"
        verdict, why = _probe(table, os.getpid())
        if verdict == "present":
            return "silent:probe-present"
        if verdict == "undecidable":
            return "silent:" + why
        print(json.dumps({"systemMessage": NOTICE_TEXT,
                          "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": NOTICE_TEXT}}))
        return "shown"
    except Exception:  # noqa: BLE001
        return "silent:error"
    finally:
        sys.dont_write_bytecode = saved_bytecode


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (ValueError, OSError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    parent, problem, detail = resolve_session_parent()
    folder = ""
    if problem is None:
        folder = os.path.join(parent, SESSION_PREFIX + session_key(payload))
        problem, detail = session_folder_problem(folder)
    if problem is not None:
        # Fail closed (I-8): delete and prune nothing under the parent. The legacy sentinel is outside it and still goes.
        where = folder or parent
        extra = f": {detail}" if detail else ""
        log(f"the per-user session folder {where} cannot be used ({problem}{extra}); the gate stays shut")
        _delete_legacy_sentinels(payload)
        sys.exit(0)
    _delete_marker_and_tickets(folder)
    _delete_legacy_sentinels(payload)
    if _first_prompt_of_session(folder):
        prune_session_folders(parent)
    try:
        notice_section(payload)  # prints the notice itself when it shows one; its outcome is for the bench and the tests
    except BaseException:  # noqa: BLE001 - nothing the notice raises (SystemExit included) may change the exit code or the deletions
        pass
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        log(f"internal error (failing open): {e}")
        sys.exit(0)
