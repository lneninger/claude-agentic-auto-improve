#!/usr/bin/env python3
"""
cleanup_delivered.py -- Delivery cleanup (contract 2026-10-15-auto-cleanup-delivered-worktrees, issue #50).

Once a contract is implemented on the default branch, the worktrees and the merged branches that belong to
its work item are only clutter. This script removes them, and only them, and only what is provably already
in ``origin/<default>``. It runs on EVERY ``/pr-merged`` and ``/advance`` call and is idempotent: until the
records pull request has merged it says "not delivered yet" and removes nothing.

Usage:
  py -3 cleanup_delivered.py --contract <slug> --from <starting dir> [--remove-remote] [--dry-run] [--json]
  py -3 cleanup_delivered.py --print-main-root

Exit codes: 0 cleaned or nothing-owned, 3 partial, 5 not-delivered (normal), 10 unverifiable, 2 usage.
``--json`` prints one Cleanup Report object; otherwise only its one-line ``line`` is printed.

Rules this module keeps (INV-1 to INV-9 of the contract):
  * Nothing is changed unless the contract reads ``Status: implemented`` at ``origin/<default>`` and every
    sub-task has a GitHub-verified record there (read AT the ref, never from the working tree).
  * Only the Owned set is examined: the brief's branch, ``task/<slug>/<id>``, ``docs/<slug>-records`` and the
    worktrees that hold them (or sit at the brief's path, or are this slug's advance worktree). Never the
    main checkout, never a landing worktree, never the default branch.
  * A worktree goes only when it is clean, its HEAD is in ``origin/<default>``, it is not locked, no ignored
    folder in it is itself a worktree, and nobody stands in it. A branch goes only after an ancestor check.
  * Directory links (junctions, symlinks) are removed as the link entry alone, last, right before the removal.
  * Landed untracked files (contract 2026-10-17): when every change in a tree is an untracked file that git
    would store as exactly the blob ``origin/<default>`` holds at that path (``git hash-object``, filters on),
    each such file is deleted alone, last, after a fresh re-hash, and the tree is then removed WITHOUT force.
    Anything git cannot prove identical keeps the tree; a failed comparison is ``unverifiable``.
  * Never a forced removal, never a global tidy of stale entries, never a recursive delete of a worktree,
    never a switch or checkout in any tree.
  * A tree somebody stands in is deferred and left untouched; the next call from elsewhere clears it.
  * Holder reading (contract 2026-10-18, HN-1 to HN-11): when a tree is deferred as ``standing-tree`` or ``in-use``,
    the script reads Claude Code's own session list once (``claude agents --json --all``) AFTER every decision is
    made, names each Claude Code session whose working folder is inside the tree (the same ``_inside`` the
    deferral uses), and prints ``claude stop <id>`` for every holder except the running session. The reading
    explains the deferral; it never changes an action, a reason, the outcome, the exit code or the finish command.
    A list that cannot be read says ``cannot-tell`` with a fixed reason, never ``none-found``.
  * Read only, with one stated exception: the script never stops, signals or changes another session or process.
    The one exception is its own ``claude agents`` child, ended only after the time ceiling passes, with a plain
    ``kill`` of that one child (``_end_own_child``, called from the timeout branch of ``_run_holder_list`` and
    nowhere else). No descendant, process group or process tree is ended: a background supervisor may be one.
    Only three process calls exist: ``subprocess.run`` inside ``_exec``, ``Popen`` inside ``_run_holder_list`` and
    ``kill`` inside ``_end_own_child``.
  * The ``claude`` command is accepted only as an absolute path whose folder is neither the current folder nor the
    main checkout root; when the first hit is unsafe the other PATH folders are searched, and when none is safe the
    reading says "the claude command was not found". At most ``HOLDER_OUTPUT_LIMIT_BYTES`` of output are read.
  * A record's working folder is accepted only as a drive path (``X:\\`` or ``X:/``) or the Git Bash form ``/x/...``
    on Windows (any absolute path elsewhere). A UNC or device form is unreadable and never given to
    ``os.path.realpath``; a folder holding NUL, any control character or U+FFFD is unreadable on every platform.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
from typing import Any, Dict, Iterator, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# Every module is imported BEFORE any removal: a tree removed under the running script must not break an import.
import flat_worktree  # noqa: E402
import land_contract  # noqa: E402
import pr_merged  # noqa: E402

EXIT_OK, EXIT_USAGE, EXIT_PARTIAL, EXIT_NOT_DELIVERED, EXIT_UNVERIFIABLE = 0, 2, 3, 5, 10
LINE_LIMIT = 600
PROTECTED = ("master", "main")
UNSET_VALUES = ("", "none", "unknown", "null")
IS_WINDOWS = os.name == "nt"
RERUN_HINT = "runs again on the next /pr-merged or /advance"
HOLDER_TIMEOUT_SECONDS = 15  # how long `claude agents` may take before the answer is "cannot tell" (HN-2)
HOLDER_END_GRACE_SECONDS = 5  # how long to wait for that one child to go after the ceiling passed (HN-2)
HOLDER_OUTPUT_LIMIT_BYTES = 4 * 1024 * 1024  # the most output read from `claude agents` (HN-2, A4)
HOLDER_TEXT_LIMIT = 60
HOLDER_NOTE = ("; note: the session list shows background sessions only; a session typed into a terminal, "
               "an editor or another program may also hold this folder")
HOLDER_WARNING = "; warning: the running session was not recognised, so one stop command may be its own"


class Halt(Exception):
    """A probe could not rename a folder back: every further mutation stops (INV-9)."""

    def __init__(self, path: str, sibling: str, exc: BaseException) -> None:
        super().__init__("%s: %s" % (path, exc))
        self.path, self.sibling, self.exc = path, sibling, exc


# ---------------------------------------------------------------------------
# Processes (git and gh are found by bare name through PATH)
# ---------------------------------------------------------------------------
def _exec(cmd: List[str]) -> Tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", "%s: %s" % (type(exc).__name__, exc)


def _git(*args: str) -> Tuple[int, str, str]:
    return _exec(["git", *args])


def _gh(*args: str) -> Tuple[int, str, str]:
    return _exec(["gh", *args])


# ---------------------------------------------------------------------------
# Text and path helpers
# ---------------------------------------------------------------------------
def _clean(text: Any) -> str:
    """Control characters removed (INV-8): a name echoed into a skill must not carry escape codes."""
    return re.sub(r"[\x00-\x1f\x7f]", "", str(text))


def _quote(text: str) -> str:
    """Single-quoted for a POSIX shell; a ``'`` inside is written ``'\\''`` (INV-6)."""
    return "'" + str(text).replace("'", "'\\''") + "'"


def _norm(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _inside(inner: str, outer: str) -> bool:
    i, o = _norm(inner), _norm(outer).rstrip("\\/")
    return i == o or i.startswith(o + os.sep)


def _real_target(path: str) -> str:
    try:
        target = os.readlink(path)
    except (OSError, ValueError):
        return ""
    target = target[4:] if target.startswith("\\\\?\\") else target
    if target and not os.path.isabs(target):
        target = os.path.join(os.path.dirname(path), target)  # a relative target is relative to the link's folder
    return os.path.normpath(target) if target else ""


@contextlib.contextmanager
def _in_dir(path: str) -> Iterator[None]:
    saved = os.getcwd()
    try:
        if os.path.isdir(path):
            os.chdir(path)
        yield
    finally:
        os.chdir(saved)


# ---------------------------------------------------------------------------
# Holder reading (contract 2026-10-18-cleanup-names-worktree-holder.md)
# ---------------------------------------------------------------------------
def _end_own_child(proc: Any) -> None:
    """HN-9, the one exception: end the ``claude agents`` child this script started, and only that child."""
    try:
        proc.kill()
    except OSError:
        pass


def _find_claude(main_root: str) -> Optional[str]:
    """HN-2 / A2: an absolute ``claude`` path whose folder is neither the current folder nor the main checkout root."""
    unsafe = {_norm(os.getcwd()), _norm(main_root)}

    def safe(found: Optional[str]) -> bool:
        return bool(found) and os.path.isabs(found) and _norm(os.path.dirname(found)) not in unsafe

    found = shutil.which("claude")
    if safe(found):
        return found
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        entry = entry.strip().strip('"')
        if not entry or not os.path.isabs(entry):  # D4: a PATH folder is never resolved unless it is a hit
            continue
        found = shutil.which(os.path.join(entry, "claude"))  # a full name: no search, so no current-folder hit
        if safe(found):
            return found
    return None


def _run_holder_list(exe: str, cwd: str) -> Tuple[str, str]:
    """HN-2: run ``claude agents --json --all`` once. Returns ``(result, stdout)``; the result is one of
    ``answer``, ``too-big``, ``timeout``, ``launch-failed`` or ``exit <n>``. The output goes to a temporary file, not
    a pipe, so a program that keeps its output open can never make this wait."""
    with tempfile.TemporaryFile() as sink:
        try:
            proc = subprocess.Popen([exe, "agents", "--json", "--all"], stdin=subprocess.DEVNULL, stdout=sink,
                                    stderr=subprocess.DEVNULL, cwd=cwd)
        except OSError:
            return "launch-failed", ""
        try:
            proc.wait(timeout=HOLDER_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            _end_own_child(proc)
            try:
                proc.wait(timeout=HOLDER_END_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                pass
            return "timeout", ""
        if proc.returncode != 0:
            return "exit %d" % proc.returncode, ""
        sink.seek(0)
        data = sink.read(HOLDER_OUTPUT_LIMIT_BYTES + 1)
        if len(data) > HOLDER_OUTPUT_LIMIT_BYTES:
            return "too-big", ""
        return "answer", data.decode("utf-8", errors="replace")


_UNSAFE_CATEGORIES = ("Cc", "Cf", "Zl", "Zp")


def _strip_unsafe(text: Any) -> str:
    """HN-6 / D2: NFKC normalisation, then every control, format, line-separator and paragraph-separator character
    removed. Text that is not a string is empty (D3)."""
    if not isinstance(text, str):
        return ""
    folded = unicodedata.normalize("NFKC", text)
    return "".join(c for c in folded if unicodedata.category(c) not in _UNSAFE_CATEGORIES)


def _list_text(text: Any) -> str:
    """HN-6: text from the session list made safe to show in one line, then cut after the removal."""
    cleaned = _strip_unsafe(text).replace(";", ",").replace('"', "'").replace("[", "(").replace("]", ")")
    return cleaned[:HOLDER_TEXT_LIMIT]


def _short_id(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{8}", value) else None


def _long_id(value: Any) -> Optional[str]:
    ok = isinstance(value, str) and re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", value)
    return value if ok else None


_UNREADABLE_PATH = re.compile("[\x00-\x1f\x7f-\x9f�]")


def _holder_path(cwd: Any) -> Optional[str]:
    """HN-5: the accepted forms of a record's working folder, or None (an unreadable record). A UNC or device form
    is never accepted, so it never reaches ``os.path.realpath``."""
    if not isinstance(cwd, str) or not cwd.strip() or _UNREADABLE_PATH.search(cwd):
        return None
    if not IS_WINDOWS:
        return cwd if cwd.startswith("/") else None
    bash = re.fullmatch(r"/([A-Za-z])(/.*)?", cwd)
    if bash:
        return bash.group(1).upper() + ":" + (bash.group(2) or "/")
    return cwd if re.match(r"[A-Za-z]:[\\/]", cwd) else None


def _cannot_tell(reason: str) -> Dict[str, Any]:
    return {"verdict": "cannot-tell", "reason": reason}


def _read_session_list(main_root: str) -> Dict[str, Any]:
    """The Session List Reading (HN-3, HN-4, HN-7). Never raises: every failure is ``cannot-tell`` with a reason."""
    try:
        exe = _find_claude(main_root)
        if not exe:
            return _cannot_tell("the claude command was not found")
        # B1: start the child in the folder that holds the resolved claude program, never in the main checkout.
        result, text = _run_holder_list(exe, os.path.dirname(exe))
        if result == "launch-failed":
            return _cannot_tell("the claude command could not be started")
        if result == "too-big":
            return _cannot_tell("the session list was not in the expected form")
        if result == "timeout":
            return _cannot_tell("claude agents gave no answer within %d seconds" % HOLDER_TIMEOUT_SECONDS)
        if result != "answer":
            return _cannot_tell("claude agents exited with code %s" % result.split(" ", 1)[-1])
        form = _cannot_tell("the session list was not in the expected form")
        try:
            listed = json.loads(text)
        except ValueError:
            return form
        if not isinstance(listed, list) or not all(isinstance(r, dict) for r in listed):
            return form
        records: List[Dict[str, Any]] = []
        unreadable = 0
        for raw in listed:
            path = _holder_path(raw.get("cwd"))
            try:
                if path is not None:
                    _norm(path)  # the comparison below uses it; a path it cannot resolve is unreadable
            except (ValueError, OSError):
                path = None
            if path is None:
                unreadable += 1
                continue
            started = raw.get("startedAt")
            records.append({"id": _short_id(raw.get("id")), "session_id": _long_id(raw.get("sessionId")),
                            "name": _list_text(raw.get("name")), "state": _list_text(raw.get("state")),
                            "kind": _list_text(raw.get("kind")),
                            "started_at": started if isinstance(started, int) and not isinstance(started, bool) else None,
                            "cwd": _strip_unsafe(raw.get("cwd")), "path": path})
        mine = os.environ.get("CLAUDE_CODE_SESSION_ID") or ""
        matching = [r for r in records if mine and r["session_id"] == mine]
        this_session = matching[0]["session_id"] if len(matching) == 1 else None
        return {"verdict": "read", "records": records, "unreadable": unreadable, "this_session": this_session}
    except Exception as exc:  # HN-3: nothing in the lookup may end the run
        return _cannot_tell("the session list could not be read (%s)" % type(exc).__name__)


def _holders_for(reading: Dict[str, Any], tree: str) -> Dict[str, Any]:
    """The Holder Reading of one deferred tree, from the one Session List Reading."""
    if reading["verdict"] != "read":
        return {"verdict": "cannot-tell", "reason": reading["reason"], "sessions": [], "this_session_recognised": False}
    recognised = reading["this_session"] is not None
    sessions: List[Dict[str, Any]] = []
    try:
        for rec in reading["records"]:
            if not _inside(rec["path"], tree):  # HN-5: the deferral's own comparison
                continue
            this = recognised and rec["session_id"] == reading["this_session"]
            sessions.append({"id": rec["id"], "session_id": rec["session_id"], "name": rec["name"],
                             "state": rec["state"], "kind": rec["kind"], "started_at": rec["started_at"],
                             "cwd": rec["cwd"], "this_session": this,
                             "stop_command": ("claude stop %s" % rec["id"]) if rec["id"] and not this else None})
    except Exception as exc:
        return {"verdict": "cannot-tell", "reason": "the session list could not be read (%s)" % type(exc).__name__,
                "sessions": [], "this_session_recognised": False}
    result: Dict[str, Any] = {"sessions": sessions, "this_session_recognised": recognised}
    if sessions:
        result["verdict"] = "found"
    elif reading["unreadable"]:
        result.update(verdict="cannot-tell", reason="%d session records had no readable working folder" % reading["unreadable"])
    else:
        result["verdict"] = "none-found"
    return result


def attach_holders(run: "Run") -> Optional[Dict[str, Any]]:
    """HN-1: after every decision is made, give each tree deferred as standing-tree or in-use its Holder Reading.
    Writes only ``holders``. Returns the ``holder_lookup`` for the report, or None when no lookup was needed."""
    deferred = [i for i in run.items if i.get("kind") == "worktree" and i.get("action") == "deferred"
                and i.get("reason") in ("standing-tree", "in-use")]
    if not deferred:
        return None
    reading = _read_session_list(run.main_root)
    for item in deferred:
        item["holders"] = _holders_for(reading, item["path"])
    lookup: Dict[str, Any] = {"verdict": reading["verdict"], "this_session": reading.get("this_session")}
    if reading["verdict"] != "read":
        lookup["reason"] = reading["reason"]
    return lookup


def _stop_commands(items: List[Dict[str, Any]]) -> List[str]:
    """HN-8: one ``claude stop <id>`` per distinct session, first seen first, never for this session. The id is
    checked here again, so a stop command is only ever built from eight lower-case hex characters."""
    commands: List[str] = []
    for item in items:
        for holder in (item.get("holders") or {}).get("sessions") or []:
            sid = _short_id(holder.get("id"))
            command = "claude stop %s" % sid
            if sid and not holder.get("this_session") and command not in commands:
                commands.append(command)
    return commands


def _holder_text(holder: Dict[str, Any]) -> str:
    sid = _short_id(holder.get("id"))
    if holder.get("this_session"):
        return "%s (this session)" % (sid or "a session with an unreadable id")
    parts = [sid or "a session with an unreadable id"]
    name, state = _list_text(holder.get("name")), _list_text(holder.get("state"))
    if name:
        parts.append('"%s"' % name)
    if state:
        parts.append(state)
    return " ".join(parts)


def _holder_bracket(holders: Optional[Dict[str, Any]], cap: int) -> str:
    if not holders:
        return ""
    verdict = holders.get("verdict")
    if verdict == "found":
        return "[held by %s]" % _listing([_holder_text(h) for h in holders.get("sessions") or []], cap, ", ")
    if verdict == "none-found":
        return "[no background session in the list is in it]"
    if verdict == "cannot-tell":
        return "[cannot tell which session holds it: %s]" % _clean(holders.get("reason") or "no reason given")
    return ""


# ---------------------------------------------------------------------------
# Directory links (INV-4): found with os.lstat, never with the DirEntry helpers that differ before 3.12
# ---------------------------------------------------------------------------
def _is_link(path: str) -> bool:
    """A junction or symlink entry: the reparse-point flag on Windows, S_ISLNK elsewhere."""
    st = os.lstat(path)
    if IS_WINDOWS:
        return bool(getattr(st, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    return stat.S_ISLNK(st.st_mode)


def _is_dir_link(path: str) -> bool:
    """Whether removing the link takes ``os.rmdir`` (a directory link on Windows) rather than ``os.unlink``."""
    if not IS_WINDOWS:
        return False
    return bool(getattr(os.lstat(path), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_DIRECTORY)


def _walk(top: str) -> Iterator[Tuple[str, List[str], List[str]]]:
    """``(dir, subdirs, links)`` for every real directory under ``top``; a link is reported, never entered."""
    stack = [top]
    while stack:
        here = stack.pop()
        subdirs: List[str] = []
        links: List[str] = []
        try:
            with os.scandir(here) as it:
                names = sorted(e.name for e in it)
        except OSError:
            continue
        for name in names:
            full = os.path.join(here, name)
            try:
                if _is_link(full):
                    links.append(full)
                elif stat.S_ISDIR(os.lstat(full).st_mode):
                    subdirs.append(full)
            except OSError:
                continue
        yield here, subdirs, links
        stack.extend(d for d in subdirs if os.path.basename(d) != ".git")


def find_links(root: str, tracked: set) -> List[str]:
    """Every untracked directory or file link anywhere in the tree (a tracked link stays: git owns it)."""
    found: List[str] = []
    for _here, _subdirs, links in _walk(root):
        for link in links:
            rel = os.path.relpath(link, root).replace("\\", "/")
            if rel not in tracked:
                found.append(link)
    return found


def find_nested(root: str, ignored: List[str]) -> List[str]:
    """Ignored folders that hold a ``.git`` entry, i.e. a nested worktree git would delete with the tree."""
    nested: List[str] = []
    for rel in ignored:
        top = os.path.join(root, rel.rstrip("/"))
        try:
            if _is_link(top) or not stat.S_ISDIR(os.lstat(top).st_mode):
                continue
        except OSError:
            continue
        stack = [top]
        while stack:
            here = stack.pop()
            if os.path.lexists(os.path.join(here, ".git")):
                nested.append(os.path.relpath(here, root).replace("\\", "/"))
                continue
            stack.extend(_subdirs(here))
    return nested


def _subdirs(here: str) -> List[str]:
    """The real (non-link) sub-directories of ``here``."""
    subdirs: List[str] = []
    try:
        with os.scandir(here) as it:
            names = sorted(e.name for e in it)
    except OSError:
        names = []
    for name in names:
        full = os.path.join(here, name)
        try:
            if not _is_link(full) and stat.S_ISDIR(os.lstat(full).st_mode):
                subdirs.append(full)
        except OSError:
            continue
    return subdirs


def remove_link(path: str) -> Dict[str, Any]:
    """Remove ONE link as the entry itself, then re-check its target. Returns the Directory Link."""
    target = _real_target(path)
    kind = "junction" if IS_WINDOWS and _is_dir_link(path) else "symlink"
    link: Dict[str, Any] = {"path": path.replace("\\", "/"), "target": target.replace("\\", "/"), "kind": kind,
                            "removed": False, "target_survived": None}
    if IS_WINDOWS and _is_dir_link(path):
        os.rmdir(path)
    else:
        os.unlink(path)
    link["removed"] = True
    link["target_survived"] = os.path.exists(target) if target else None
    return link


# ---------------------------------------------------------------------------
# Delivery Reading (INV-1)
# ---------------------------------------------------------------------------
def read_delivery(slug: str) -> Dict[str, Any]:
    """The gate: fetch, then read the contract and the records AT ``origin/<default>`` and decide."""
    reading: Dict[str, Any] = {"slug": slug, "default_branch": None, "contract_status": None, "sub_tasks": [],
                               "delivered": False, "records_pull_request": None, "verdict": "not-delivered",
                               "reasons": []}
    default = pr_merged.default_branch_or_none()
    if not default:
        reading.update(verdict="unverifiable", reasons=["the default branch (origin/HEAD) cannot be read"])
        return reading
    reading["default_branch"] = default
    code, _out, err = _git("fetch", "origin", default)
    if code != 0:
        reading.update(verdict="unverifiable",
                       reasons=["git fetch origin %s failed: %s" % (default, _clean(err.strip())[:200])])
        return reading
    ref = "origin/%s" % default
    concept = "%s/%s.md" % (pr_merged.CONCEPTS_DIR.as_posix(), slug)
    text = pr_merged.file_at_commit(ref, concept)
    if text is None:
        reading["reasons"] = ["%s is not on %s" % (concept, ref)]
        return reading
    status = pr_merged.read_contract_status(text)
    classified = pr_merged.classify_handoff(text)
    records = pr_merged.load_records_at(ref, slug)
    delivery = pr_merged.load_delivery_at(ref, slug)
    ok, why = pr_merged.is_delivered(classified.sub_tasks, records, delivery, classified.defects)
    reading.update(contract_status=status, sub_tasks=[t.id for t in classified.sub_tasks], delivered=ok)
    reasons: List[str] = []
    if status != "implemented":
        open_prs = pr_merged.open_records_pull_requests(slug)
        if open_prs:
            reading["records_pull_request"] = open_prs[0].get("url") or open_prs[0].get("headRefName")
            reasons.append("records pull request %s not merged yet" % reading["records_pull_request"])
        reasons.append("the contract reads Status: %s at %s, not implemented" % (status or "none", ref))
    if not ok:
        reasons.extend(r.get("item", "") for r in why)
    reading["reasons"] = reasons
    reading["verdict"] = "delivered" if (status == "implemented" and ok) else "not-delivered"
    if reading["verdict"] == "delivered":
        reading["reasons"] = []
    return reading


# ---------------------------------------------------------------------------
# The Owned set (INV-2)
# ---------------------------------------------------------------------------
def _value(fields: Dict[str, str], key: str) -> Optional[str]:
    raw = (fields.get(key) or "").strip().strip("'\"")
    return None if raw.lower() in UNSET_VALUES else raw


def find_brief(slug: str, contract_text: str, ref: str, from_dir: str, default: str,
               records: Dict[str, Any], delivery: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """The linked brief's fields (``branch``, ``worktree``) or ``{}``: rule I-17 first, then the ``branch:`` fallback."""
    code, top, _err = _git("-C", from_dir, "rev-parse", "--show-toplevel")
    root = top.strip() if code == 0 and top.strip() else from_dir  # the tree's root, even when started in a sub-folder
    with _in_dir(root):
        path = pr_merged.find_linked_brief(contract_text, slug)
    if path is None:
        header = pr_merged.brief_header_path(contract_text)  # a brief that only exists at the ref
        path = header if header is not None and pr_merged.file_at_commit(ref, header.as_posix()) is not None else None
    if path is not None:
        text = pr_merged.file_at_commit(ref, path.as_posix())
        if text is not None:
            return pr_merged.parse_brief_frontmatter(text)
        return pr_merged.read_brief_frontmatter(path) or {}
    heads: List[Tuple[str, bool]] = []  # (branch, from the starting tree: adopted only if its brief names this slug)
    for record in [delivery] + list(records.values()):
        url = (record or {}).get("pull_request") or (record or {}).get("pr")
        if url:
            pr = pr_merged.gh_pr(url)
            if pr and pr.get("headRefName"):
                heads.append((pr["headRefName"], False))
    code, out, _err = _git("-C", from_dir, "symbolic-ref", "--short", "-q", "HEAD")
    if code == 0 and out.strip():
        heads.append((out.strip(), True))
    for head, strict in heads:
        if head in PROTECTED or head == default:
            continue
        try:
            brief = pr_merged.brief_for_branch(head, ref)
        except pr_merged.AmbiguousBrief:
            continue
        if not brief:
            continue
        named = _value(brief, "contract")
        if named and not pr_merged._names_contract(named, slug):
            continue  # that brief belongs to another contract's work item
        if strict and not named:
            continue  # the starting branch proves nothing without a brief that names this contract
        return brief
    return {}


def owned_branches(slug: str, tasks: List[str], brief: Dict[str, str]) -> Dict[str, str]:
    """Owned Branch name -> source. Order: brief, sub-tasks, records."""
    owned: Dict[str, str] = {}
    branch = _value(brief, "branch")
    if branch:
        owned[branch] = "brief-branch"
    for task_id in tasks:
        owned.setdefault(pr_merged.branch_for(slug, task_id), "sub-task")
    owned.setdefault(pr_merged.records_branch_prefix(slug), "records")
    return owned


def other_slugs(ref: str, slug: str) -> Optional[List[str]]:
    """The other contracts at the ref, or None when they cannot be listed (never an empty list on failure)."""
    code, out, _err = _git("ls-tree", "--name-only", "%s:%s" % (ref, pr_merged.CONCEPTS_DIR.as_posix()))
    if code != 0:
        return None
    return [n[:-3] for n in out.splitlines() if n.endswith(".md") and n[:-3] != slug]


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------
class Run:
    """State of one cleanup run."""

    def __init__(self, slug: str, main_root: str, ref: str, default: str, remove_remote: bool, dry_run: bool,
                 standing: List[str]) -> None:
        self.slug, self.main_root, self.ref, self.default = slug, main_root, ref, default
        self.remove_remote, self.dry_run, self.standing = remove_remote, dry_run, standing
        self.items: List[Dict[str, Any]] = []
        self.removed_paths: List[str] = []
        self.finish_needed = False
        self.repair: List[str] = []
        self.halted = False

    def add(self, item: Dict[str, Any]) -> Dict[str, Any]:
        self.items.append(item)
        return item

    def is_standing(self, tree: str) -> bool:
        return any(_inside(p, tree) for p in self.standing)


def _wt_item(w: Dict[str, Any], source: str) -> Dict[str, Any]:
    return {"kind": "worktree", "path": w["path"], "branch": w.get("branch"), "head": w.get("head"),
            "source": source, "locked": bool(w.get("locked")), "action": "left", "reason": None, "files": [],
            "detail": None, "links": [], "identical": []}


def _left(item: Dict[str, Any], reason: str, files: Optional[List[str]] = None, detail: Optional[str] = None,
          action: str = "left") -> Dict[str, Any]:
    item.update(action=action, reason=reason, files=files or [], detail=detail)
    return item


def _status_entries(path: str) -> Tuple[Optional[List[Tuple[str, str]]], str]:
    """``(status code, path)`` of every changed and untracked entry of a worktree, or ``(None, error)``."""
    code, out, err = _git("-C", path, "status", "--porcelain", "-z", "--untracked-files=all")
    if code != 0:
        return None, err.strip()
    entries: List[Tuple[str, str]] = []
    parts = out.split("\0")
    i = 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if len(entry) < 4:
            continue
        entries.append((entry[:2], entry[3:]))
        if entry[0] in "RC" or entry[1] in "RC":
            i += 1  # the original name of a rename or copy
    return sorted(entries, key=lambda e: e[1]), ""


def _status_files(path: str) -> Tuple[Optional[List[str]], str]:
    """Changed and untracked paths of a worktree, or ``(None, error)``."""
    entries, err = _status_entries(path)
    if entries is None:
        return None, err
    return [p for _c, p in entries], ""


# ---------------------------------------------------------------------------
# Landed untracked files (contract 2026-10-17, CL-1 to CL-6)
# ---------------------------------------------------------------------------
HASH_CHUNK_CHARS = 7000  # a command line stays under 8000 characters


def _plain_file_inside(tree: str, rel: str) -> bool:
    """CL-1: a regular file (not a link), no linked folder between the tree root and it, real path inside the tree."""
    full = os.path.join(tree, *rel.split("/"))
    try:
        here = tree
        for part in rel.split("/")[:-1]:
            here = os.path.join(here, part)
            if _is_link(here):
                return False
        if _is_link(full) or not stat.S_ISREG(os.lstat(full).st_mode):
            return False
    except (OSError, ValueError):
        return False
    return _inside(full, tree)


def _hash_files(tree: str, rels: List[str]) -> Tuple[Optional[Dict[str, str]], str]:
    """Blob ids git would store for each path (clean filters and line-ending conversion ON), or ``(None, cause)``."""
    ids: Dict[str, str] = {}
    batches: List[List[str]] = []
    chunk: List[str] = []
    size = 0
    for rel in rels:
        if chunk and size + len(rel) + 1 > HASH_CHUNK_CHARS:
            batches.append(chunk)
            chunk, size = [], 0
        chunk.append(rel)
        size += len(rel) + 1
    if chunk:
        batches.append(chunk)
    for batch in batches:
        code, out, err = _git("-C", tree, "hash-object", "--", *batch)
        if code != 0:
            return None, "git hash-object failed: %s" % _clean(err.strip())[:200]
        lines = out.split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        if len(lines) != len(batch):
            return None, "git hash-object returned %d ids for %d paths" % (len(lines), len(batch))
        for rel, line in zip(batch, lines):
            ids[rel] = line.strip()
    return ids, ""


def compare_untracked(tree: str, ref: str, untracked: List[str]) -> Dict[str, Any]:
    """The Untracked Comparison of one tree whose every status entry is untracked."""
    result: Dict[str, Any] = {"ref": ref, "identical": [], "differing": [], "blobs": {}, "verdict": "all-identical",
                              "cause": ""}
    candidates = [rel for rel in untracked if _plain_file_inside(tree, rel)]
    differing = {rel for rel in untracked if rel not in candidates}
    wanted = set(candidates)
    code, out, err = _git("-C", tree, "ls-tree", "-r", "-z", "--full-tree", ref)
    if code != 0:
        result.update(verdict="unverifiable", cause="git ls-tree of %s failed: %s" % (ref, _clean(err.strip())[:200]))
        return result
    blobs: Dict[str, str] = {}
    for record in out.split("\0"):
        meta, tab, name = record.partition("\t")
        if not tab or name not in wanted:
            continue
        fields = meta.split()
        if len(fields) == 3 and fields[1] == "blob" and fields[0] in ("100644", "100755"):
            blobs[name] = fields[2].lower()
    differing.update(rel for rel in candidates if rel not in blobs)
    ids, cause = _hash_files(tree, sorted(blobs))
    if ids is None:
        result.update(verdict="unverifiable", cause=cause)
        return result
    for rel in sorted(blobs):
        if ids[rel].lower() == blobs[rel]:
            result["identical"].append(rel)
            result["blobs"][rel] = blobs[rel]
        else:
            differing.add(rel)
    result["differing"] = sorted(differing)
    if differing:
        result["verdict"] = "some-differ"
    return result


def _ignored_dirs(path: str) -> Optional[List[str]]:
    """Ignored top-level entries, or None when git cannot list them (never an empty list on failure)."""
    code, out, _err = _git("-C", path, "ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--directory")
    return [n for n in out.split("\0") if n] if code == 0 else None


def _tracked(path: str) -> Optional[set]:
    """Tracked paths, or None when git cannot list them (never an empty set on failure)."""
    code, out, _err = _git("-C", path, "ls-files", "-z")
    return {n for n in out.split("\0") if n} if code == 0 else None


def _probe(path: str) -> Optional[OSError]:
    """INV-6 (Windows): rename the folder to a sibling name and straight back. ``None`` when nobody holds it."""
    sibling = path.rstrip("/\\") + ".probe"
    count = 1
    while os.path.lexists(sibling):
        count += 1
        sibling = "%s.probe%d" % (path.rstrip("/\\"), count)
    try:
        os.rename(path, sibling)
    except OSError as exc:
        return exc
    try:
        os.rename(sibling, path)
    except OSError as exc:
        raise Halt(path, sibling, exc)
    return None


def clean_worktree(run: Run, item: Dict[str, Any]) -> None:
    """INV-3, INV-4, INV-6 for one owned worktree: every check first, links last, then the removal."""
    path = item["path"]
    if item["locked"]:
        _left(item, "locked")
        return
    if not os.path.isdir(path):
        _left(item, "remove-failed", detail="the folder is missing; git still lists it")
        return
    entries, err = _status_entries(path)
    if entries is None:
        _left(item, "unverifiable", detail=err)
        return
    landed: Dict[str, str] = {}  # Landed untracked file -> the blob id it matched
    untracked = [p for _c, p in entries]
    if entries and all(code == "??" for code, _p in entries):
        compared = compare_untracked(path, run.ref, untracked)
        if compared["verdict"] == "unverifiable":
            _left(item, "unverifiable", detail=compared["cause"])
            return
        item["identical"] = list(compared["identical"])
        if compared["verdict"] == "some-differ":
            _left(item, "uncommitted-changes", files=compared["differing"])
            return
        landed = dict(compared["blobs"])
    elif entries:
        _left(item, "uncommitted-changes", files=untracked)
        return
    head = item["head"]
    if not head:  # read the tree's own HEAD; never fall back to the main checkout's
        code, out, _err = _git("-C", path, "rev-parse", "HEAD")
        head = out.strip() if code == 0 and out.strip() else None
    if not head:
        _left(item, "unverifiable", detail="the HEAD of this tree cannot be read")
        return
    item["head"] = head
    code, _out, _err = _git("merge-base", "--is-ancestor", head, run.ref)
    if code != 0:
        if code != 1:
            _left(item, "unverifiable", detail="merge-base answered %d" % code)
            return
        _c, diff, _e = _git("diff", "--name-only", "%s...%s" % (run.ref, head))
        _left(item, "unpushed-commits", files=[n for n in diff.splitlines() if n.strip()])
        return
    ignored = _ignored_dirs(path)
    tracked = _tracked(path)
    if ignored is None or tracked is None:
        _left(item, "unverifiable", detail="git could not list the ignored or tracked files of this tree")
        return
    nested = find_nested(path, ignored)
    if nested:
        _left(item, "nested-worktree", files=sorted(nested))
        return
    if run.is_standing(path):
        _left(item, "standing-tree", action="deferred")
        run.finish_needed = True
        return
    if run.dry_run:
        links = [{"path": l.replace("\\", "/"), "target": _real_target(l).replace("\\", "/"), "removed": False}
                 for l in find_links(path, tracked)]
        item.update(action="removed", links=links, detail="dry run: would be removed")
        run.removed_paths.append(path)
        return
    found_links = find_links(path, tracked)
    # One halt rule (INV-9): a link that sits outside every ignored folder (a node_modules link in the tree's own
    # folders) and lost its target. Dangling links inside an ignored folder such as .venv are ordinary: no halt.
    def is_inside_ignored(link: str) -> bool:
        parent = os.path.relpath(os.path.dirname(link), path).replace("\\", "/")
        if parent == ".":
            return False
        code, _o, _e = _git("-C", path, "check-ignore", "-q", "--", parent)
        return code == 0  # an error or "not ignored" keeps the halt: the safe direction

    vanished = [(l, _real_target(l)) for l in found_links if _real_target(l) and not os.path.exists(_real_target(l))
                and not is_inside_ignored(l)]
    if vanished:
        run.halted = True  # like a failed rename-back: nothing else is removed after it
        _left(item, "remove-failed", detail="a link lost its target folder, nothing was removed: " + "; ".join(
            "%s -> %s" % (l.replace("\\", "/"), t.replace("\\", "/")) for l, t in vanished))
        return
    if IS_WINDOWS:
        try:
            failure = _probe(path)
        except Halt as halt:
            run.halted = True
            run.repair.append(halt.path)
            item["repair"] = halt.path
            _left(item, "remove-failed", detail="the folder could not be renamed back and now sits at '%s'; "
                  "rename it to '%s', then run: git worktree repair '%s'" % (halt.sibling, halt.path, halt.path))
            return
        if failure is not None:
            _left(item, "in-use", action="deferred", detail=_clean(failure))
            run.finish_needed = True
            return
    deleted: List[str] = []
    if landed:
        again, err = _status_entries(path)
        if again is None:
            _left(item, "unverifiable", detail="status could not be read again: " + err)
            return
        if [p for _c, p in again] != untracked or any(c != "??" for c, _p in again):
            _left(item, "uncommitted-changes", files=[p for _c, p in again])
            return
        for rel in sorted(landed):
            gone = ("; already deleted (each verified a moment before): " + ", ".join(deleted)) if deleted else ""
            if not _plain_file_inside(path, rel):
                _left(item, "uncommitted-changes", files=[rel],
                      detail="the file is no longer a plain file in the tree" + gone)
                return
            ids, cause = _hash_files(path, [rel])
            if ids is None:
                _left(item, "unverifiable", detail=cause + gone)
                return
            if ids[rel].lower() != landed[rel]:
                _left(item, "uncommitted-changes", files=[rel], detail="the file changed since the comparison" + gone)
                return
            if not _plain_file_inside(path, rel):  # again, right before the delete: git lists files beneath a junction
                _left(item, "uncommitted-changes", files=[rel],
                      detail="the file is no longer a plain file in the tree" + gone)
                return
            try:
                os.remove(os.path.join(path, *rel.split("/")))
            except OSError as exc:
                _left(item, "remove-failed", detail="%s could not be deleted: %s%s" % (rel, _clean(exc), gone))
                return
            deleted.append(rel)
    links: List[Dict[str, Any]] = []
    for link in found_links:
        try:
            links.append(remove_link(link))
        except OSError as exc:
            links.append({"path": link.replace("\\", "/"), "target": _real_target(link).replace("\\", "/"),
                          "removed": False, "target_survived": None})
            item["links"] = links
            _left(item, "link-not-removed", detail="%s: %s" % (link.replace("\\", "/"), _clean(exc)))
            return
    item["links"] = links
    code, _out, err = _git("worktree", "remove", path)
    if code != 0 or os.path.exists(path):
        recreate = "; ".join("%s -> %s" % (l["path"], l["target"]) for l in links)
        detail = (err.strip() or "the folder is still present after git worktree remove")
        if deleted:
            detail += "; deleted identical files: " + ", ".join(deleted)
        if recreate:
            detail += "; removed links: " + recreate
        _left(item, "remove-failed", detail=detail)
        return
    item.update(action="removed", reason=None)
    run.removed_paths.append(path)


def plan_worktrees(run: Run, owned: Dict[str, str], brief: Dict[str, str]) -> List[Dict[str, Any]]:
    """Owned Worktrees as items, decided by checked-out branch or exact brief path, never by folder name alone."""
    entries = flat_worktree.worktree_entries(run.main_root)
    brief_wt = _value(brief, "worktree")
    brief_path = _norm(brief_wt if os.path.isabs(brief_wt) else os.path.join(run.main_root, brief_wt)) if brief_wt else None
    others = other_slugs(run.ref, run.slug)
    planned: List[Dict[str, Any]] = []
    for entry in entries[1:]:
        path = entry["path"]
        if _norm(path) == _norm(run.main_root) or land_contract.is_landing_worktree(path, run.main_root):
            continue
        branch = entry.get("branch")
        item = None
        if branch in owned:
            item = _wt_item(entry, "owned-branch")
        elif brief_path and _norm(path) == brief_path:
            item = _wt_item(entry, "brief-worktree")
            if branch is not None:
                item["pre"] = "holds-foreign-branch"
        elif branch is None and _advance_name_matches(path, run.slug):
            item = _wt_item(entry, "advance-name")
            if others is None:
                item["pre"] = "unverifiable"  # the other contracts cannot be read: no advance name is provably ours
            elif _advance_name_matches(path, run.slug) == "cut" or any(_advance_name_matches(path, s) for s in others):
                item["pre"] = "ambiguous-name"
        if item is None:
            continue
        if branch is not None and (branch in PROTECTED or branch == run.default):
            item["pre"] = "protected-name"
        if not flat_worktree.is_flat(run.main_root, path):
            item["pre"] = "outside-worktrees-folder"
        planned.append(item)
    return sorted(planned, key=lambda i: i["path"])


def _advance_name_matches(path: str, slug: str) -> str:
    """``"exact"`` when the folder is this slug's whole advance worktree name (``-2`` to ``-9`` allowed), ``"cut"``
    when it is that name cut at the 60-character limit (a longer or a shorter slug may own it too), else ``""``."""
    name = os.path.basename(os.path.normpath(path))
    date = name[:8]
    if not re.fullmatch(r"\d{8}", date):
        return ""
    for n in range(1, flat_worktree.MAX_SUFFIX + 1):
        if name == flat_worktree.flat_name("advance", slug, date, n):
            whole = "%s-advance-%s" % (date, slug) + ("-%d" % n if n > 1 else "")
            return "exact" if name == whole else "cut"
    return ""


def orphan_folders(run: Run, brief: Dict[str, str], listed: List[str]) -> None:
    """A folder where an owned worktree used to be, which git no longer lists (a failed removal can leave one)."""
    folder = flat_worktree.worktrees_dir(run.main_root)
    try:
        names = sorted(os.listdir(folder)) if os.path.isdir(folder) else []
    except OSError:
        return  # a report that cannot be made must not crash a run that already changed things
    brief_wt = _value(brief, "worktree")
    brief_path = _norm(brief_wt if os.path.isabs(brief_wt) else os.path.join(run.main_root, brief_wt)) if brief_wt else None
    known = {_norm(p) for p in listed} | {_norm(i["path"]) for i in run.items if i.get("kind") == "worktree"}
    for name in names:
        path = os.path.join(folder, name)
        try:
            if _norm(path) in known or not os.path.isdir(path) or _is_link(path):
                continue
            if not ((brief_path and _norm(path) == brief_path) or _advance_name_matches(path, run.slug) == "exact"):
                continue
            try:
                count = "%d entries" % len(os.listdir(path))
            except OSError:
                count = "entries unreadable"
        except OSError:
            continue
        item = {"kind": "worktree", "path": path.replace("\\", "/"), "branch": None, "head": None,
                "source": "orphan-folder", "locked": False, "links": []}
        run.add(_left(item, "remove-failed", detail="git no longer lists this folder and never checked it (%s): it may "
                                                     "hold the only copy of someone's work, so inspect it before "
                                                     "deleting anything" % count))


def clean_branches(run: Run, owned: Dict[str, str]) -> Dict[str, bool]:
    """Local branches, after the worktrees (INV-3, INV-9). Returns which owned branches existed locally."""
    code, out, _err = _git("for-each-ref", "--format=%(refname) %(objectname)", "refs/heads")
    tips: Dict[str, str] = {}
    for line in out.splitlines():
        name, _, sha = line.partition(" ")
        if name.startswith("refs/heads/"):
            tips[name[len("refs/heads/"):]] = sha.strip()
    existed = {b: b in tips for b in owned}
    held: Dict[str, str] = {}
    gone = {_norm(p) for p in run.removed_paths}
    for entry in flat_worktree.worktree_entries(run.main_root):
        if entry.get("branch") and _norm(entry["path"]) not in gone:
            held[entry["branch"]] = entry["path"]
    for branch, source in owned.items():
        if branch not in tips:
            continue
        item = {"kind": "local-branch", "name": branch, "source": source, "action": "left", "reason": None,
                "files": [], "detail": None}
        run.add(item)
        if branch in PROTECTED or branch == run.default:
            _left(item, "protected-name")
        elif branch in held:
            _left(item, "checked-out", detail="held by %s" % held[branch].replace("\\", "/"))
        else:
            code, _o, _e = _git("merge-base", "--is-ancestor", tips[branch], run.ref)
            if code != 0:
                _left(item, "not-in-default", detail="%s is not in %s" % (tips[branch][:10], run.ref))
            elif run.dry_run:
                item.update(action="removed", detail="dry run: would be deleted")
            else:
                code, _o, err = _git("branch", "-D", branch)
                if code != 0:
                    _left(item, "delete-failed", detail=err.strip())
                else:
                    item["action"] = "removed"
    return existed


def clean_remote(run: Run, owned: Dict[str, str], existed: Dict[str, bool]) -> None:
    """Remote branches, last (INV-7). Without ``remove-remote`` nothing is changed."""
    for branch, source in owned.items():
        item = {"kind": "remote-branch", "name": "origin/%s" % branch, "source": source, "action": "left",
                "reason": None, "files": [], "detail": None}
        code, out, err = _git("ls-remote", "--heads", "origin", "refs/heads/%s" % branch)
        if code != 0:
            run.add(_left(item, "unverifiable", detail=err.strip()))
            continue
        tip = ""
        for line in out.splitlines():
            sha, _, name = line.partition("\t")
            if name.strip() == "refs/heads/%s" % branch:
                tip = sha.strip()
        if not tip:
            if run.remove_remote and existed.get(branch):
                run.add(dict(item, action="already-gone"))
            continue
        run.add(item)
        if branch in PROTECTED or branch == run.default:
            _left(item, "protected-name")
        elif not run.remove_remote:
            _left(item, "remote-kept")
        else:
            code, _o, _e = _git("merge-base", "--is-ancestor", tip, run.ref)
            if code != 0:
                _left(item, "not-in-default", detail="%s is not in %s" % (tip[:10], run.ref))
                continue
            code, out, err = _gh("pr", "list", "--head", branch, "--state", "open", "--json", "number,url")
            try:
                open_prs = json.loads(out) if code == 0 else None
            except ValueError:
                open_prs = None
            if not isinstance(open_prs, list):
                _left(item, "unverifiable", detail="gh could not list the open pull requests")
            elif open_prs:
                _left(item, "open-pull-request", detail=str(open_prs[0].get("url") or ""))
            elif run.dry_run:
                item.update(action="removed", detail="dry run: would be deleted")
            else:
                lease = "--force-with-lease=refs/heads/%s:%s" % (branch, tip)  # fails if the branch moved since the check
                code, _o, err = _git("push", lease, "origin", "--delete", branch)
                if code != 0:
                    _left(item, "delete-failed", detail=err.strip())
                else:
                    item["action"] = "removed"


# ---------------------------------------------------------------------------
# The report (INV-8)
# ---------------------------------------------------------------------------
def _name(item: Dict[str, Any]) -> str:
    if item["kind"] == "worktree":
        return _clean(item["path"].replace("\\", "/").rstrip("/").rsplit("/", 1)[-1])
    return _clean(item["name"])


def _listing(entries: List[str], cap: int, sep: str) -> str:
    shown = entries[:cap]
    parts = list(shown)
    if len(entries) > len(shown):
        parts.append("+%d more" % (len(entries) - len(shown)))
    return sep.join(parts)


def _left_entry(item: Dict[str, Any], file_cap: int) -> str:
    text = "%s: %s" % (_name(item), item["reason"])
    files = [_clean(f.replace("\\", "/")) for f in item.get("files") or []]
    if files:
        text += " [%s]" % _listing(files, file_cap, ", ")
    bracket = _holder_bracket(item.get("holders"), file_cap)
    if bracket:
        text += " " + bracket
    return text


def _removed_entry(item: Dict[str, Any], file_cap: int, ref: Optional[str]) -> str:
    text = _name(item)
    files = [_clean(f.replace("\\", "/")) for f in item.get("identical") or []]
    if item["kind"] == "worktree" and files:
        text += " [identical to %s: %s]" % (_clean(ref or "the default branch"), _listing(files, file_cap, ", "))
    return text


def build_line(slug: str, items: List[Dict[str, Any]], finish: Optional[str], ref: Optional[str] = None) -> str:
    removed = [i for i in items if i["action"] == "removed"]
    left = [i for i in items if i["action"] in ("left", "deferred")]
    repairs = [i["repair"] for i in items if i.get("repair")]
    tail = "".join("; repair: git worktree repair %s" % _quote(_clean(p)) for p in repairs)
    if any(i.get("holders") for i in items):  # HN-8: the uncut part, in order: note, warning, stops, finish
        tail += HOLDER_NOTE
    stops = _stop_commands(items)
    if stops:
        if not any((i.get("holders") or {}).get("this_session_recognised") for i in items):
            tail += HOLDER_WARNING
        tail += "".join("; stop: " + command for command in stops)
    if finish:
        tail += "; finish: " + finish  # never cut: a cut command is useless
    line = ""
    for cap, file_cap in ((8, 3), (6, 3), (4, 2), (3, 2), (2, 1), (1, 1), (0, 0), (-1, 0)):
        if cap >= 0:
            line = "CLEANUP %s: removed %d (%s); left %d (%s)" % (
                _clean(slug), len(removed), _listing([_removed_entry(i, file_cap, ref) for i in removed], cap, ", "), len(left),
                _listing([_left_entry(i, file_cap) for i in left], cap, "; "))
        else:  # last resort: the parenthesised lists go, the counts and the tail stay
            line = "CLEANUP %s: removed %d; left %d" % (_clean(slug), len(removed), len(left))
        line += tail
        if len(line) <= LINE_LIMIT:
            return line
    return line if tail else line[:LINE_LIMIT]


def not_delivered_line(slug: str, reading: Dict[str, Any]) -> str:
    first = _clean((reading.get("reasons") or ["no reason given"])[0])
    if reading["verdict"] == "unverifiable":
        return "CLEANUP %s: unverifiable (%s); nothing removed" % (_clean(slug), first)
    return "CLEANUP %s: not delivered yet (%s); nothing removed; %s" % (_clean(slug), first, RERUN_HINT)


def finish_command(slug: str, main_root: str, remove_remote: bool) -> str:
    script = os.path.abspath(__file__)
    cmd = "py -3 %s --contract %s --from %s" % (_quote(script), _quote(slug), _quote(main_root))
    return cmd + " --remove-remote" if remove_remote else cmd


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def cleanup(slug: str, start: str, start_cwd: str, remove_remote: bool, dry_run: bool) -> Tuple[Dict[str, Any], int]:
    info = flat_worktree.describe(start if os.path.isdir(start) else start_cwd)
    main_root = info.get("main_root")
    base: Dict[str, Any] = {"contract": slug, "main_root": main_root, "remove_remote": remove_remote,
                            "dry_run": dry_run, "items": []}
    if not main_root:
        reading = {"verdict": "unverifiable", "reasons": ["the main checkout cannot be found from %s" % start]}
        base.update(outcome="unverifiable", delivery=reading, line=not_delivered_line(slug, reading))
        return base, EXIT_UNVERIFIABLE
    os.chdir(main_root)  # the main checkout is never an owned tree; nothing below runs from a tree it removes
    reading = read_delivery(slug)
    base["delivery"] = reading
    if reading["verdict"] != "delivered":
        base.update(outcome=reading["verdict"], line=not_delivered_line(slug, reading))
        return base, EXIT_UNVERIFIABLE if reading["verdict"] == "unverifiable" else EXIT_NOT_DELIVERED

    default = reading["default_branch"]
    ref = "origin/%s" % default
    text = pr_merged.file_at_commit(ref, "%s/%s.md" % (pr_merged.CONCEPTS_DIR.as_posix(), slug)) or ""
    records = pr_merged.load_records_at(ref, slug)
    delivery = pr_merged.load_delivery_at(ref, slug)
    brief = find_brief(slug, text, ref, start, default, records, delivery)
    owned = owned_branches(slug, reading["sub_tasks"], brief)
    standing = [start_cwd, start]
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        standing.append(os.environ["CLAUDE_PROJECT_DIR"])
    run = Run(slug, main_root, ref, default, remove_remote, dry_run, standing)

    for item in plan_worktrees(run, owned, brief):
        if run.halted:
            break
        run.add(item)
        pre = item.pop("pre", None)
        if pre:
            _left(item, pre)
        else:
            clean_worktree(run, item)
    if not run.halted:
        try:
            orphan_folders(run, brief, [e["path"] for e in flat_worktree.worktree_entries(main_root)])
        except OSError:
            pass  # the orphan report is best effort; the branch steps and the line must still follow
        existed = clean_branches(run, owned)
        clean_remote(run, owned, existed)

    lookup = attach_holders(run)  # HN-1: after every decision, halted runs included; it changes none of them
    items = run.items
    finish = finish_command(slug, main_root, remove_remote) if run.finish_needed else None
    actionable = [i for i in items if i["action"] != "already-gone" and i.get("reason") != "remote-kept"]
    problems = [i for i in actionable if i["action"] in ("left", "deferred")]
    if run.halted or problems:
        outcome, code = "partial", EXIT_PARTIAL
    elif actionable:
        outcome, code = "cleaned", EXIT_OK
    else:
        outcome, code = "nothing-owned", EXIT_OK
    base.update(outcome=outcome, items=items, line=build_line(slug, items, finish, ref))
    if lookup:
        base["holder_lookup"] = lookup
        stops = _stop_commands(items)
        if stops:
            base["stop_commands"] = stops
    if finish:
        base["finish_command"] = finish
    if run.repair:
        base["repair"] = ["git worktree repair %s" % _quote(p) for p in run.repair]
    return base, code


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Remove the worktrees and merged branches of a delivered work item.")
    ap.add_argument("--contract", help="the contract slug")
    ap.add_argument("--from", dest="start", help="the folder the session stands in")
    ap.add_argument("--remove-remote", action="store_true", help="also delete the remote branches (off by default)")
    ap.add_argument("--dry-run", action="store_true", help="report what would be done and change nothing")
    ap.add_argument("--json", action="store_true", help="print the whole Cleanup Report as JSON")
    ap.add_argument("--print-main-root", action="store_true", help="print the main checkout root and exit")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if args.print_main_root:
        root = flat_worktree.describe().get("main_root")
        if not root:
            sys.stderr.write("not inside a git repository\n")
            return 1
        print(root)
        return EXIT_OK
    if not args.contract or not args.start:
        ap.error("--contract and --from are required")
    slug = re.sub(r"\.md$", "", os.path.basename(args.contract.replace("\\", "/")))
    start_cwd = os.path.realpath(os.getcwd())
    report, code = cleanup(slug, os.path.realpath(args.start), start_cwd, args.remove_remote, args.dry_run)
    print(json.dumps(report) if args.json else report["line"])
    return code


if __name__ == "__main__":
    sys.exit(main())
