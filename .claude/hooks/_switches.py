#!/usr/bin/env python3
"""
_switches.py -- the one place every plugin switch is read, and the Database override arm.

Contract: .claude/concepts/2026-11-16-file-based-switches.md (Data Shapes, "Switch rules" and
"Override rules"). Nothing here reads the process environment: a switch lives in a visible file.

THE FILES
---------
  <project>/.claude/switches.json        committed; one JSON object, one key per switch
  <project>/.claude/switches.local.json  never committed; one person's overrides, wins key by key

The project is the one the caller names (``project=``); with none named it comes from
``_project_paths.project_dir()``. Files are read only from ``<project>/.claude/``. With no project
known every key is at its default. Every lookup happens at CALL time: no path and no value is kept
from import (Two-layer path resolution).

THE RULES (each one a test row in tests/test_switches.py)
  * No-file: a missing, empty or whitespace-only file means "no settings".
  * Broken-file: a file that cannot be read, cannot be decoded, is not JSON or is not a JSON object
    makes the helper ignore EVERY switch file: all keys at their defaults. Anything but a regular file at the
    path (a named pipe, a device, a link to a network path on Windows) is unreadable and is never waited on.
  * Encoding: a UTF-8 byte order mark is dropped; UTF-16 is decoded when it starts with its mark.
  * Bad-entry: an unknown key is ignored; a value outside its set leaves that key at its default
    (``contract_index`` reads an unknown value as ``off``); ``pinned_contract`` in the committed file is
    ignored as misplaced.
  * Personal-wins: the Local switch file wins, key by key.
  * Worktree: a linked worktree with NOTHING at its own local path reads its main checkout's local file.
  * Report-once: each problem is logged through ``_error_log.log_event`` once per distinct file state;
    the marker is written only AFTER the log write succeeded.
  * Visible-off: ``off_notice`` writes one standard error line, and for a guard returns the
    ``systemMessage`` JSON field once per session.

THE DATABASE OVERRIDE ARM
-------------------------
``claim_database_override(project, tool_call_id)`` claims ``<project>/.claude/database-override.once`` by
an atomic rename and returns an Override outcome. The arm allows nothing: the guards turn it into a
permission prompt, once. ``names_override_file(text)`` is the name test the Arm-write rule uses.
"""
from __future__ import annotations

import codecs
import hashlib
import json
import os
import re
import stat
import sys
import time
import uuid
from pathlib import Path
from typing import Any, NamedTuple

try:  # call-time path functions; a missing helper means "no project known" (every default)
    import _project_paths as _pp
except Exception:  # pragma: no cover - fail-soft
    _pp = None

try:  # passive error log; fail-soft
    from _error_log import log_event
except Exception:  # pragma: no cover - fail-soft
    def log_event(*args, **kwargs):  # type: ignore[no-redef]
        return False


SWITCH_FILE_NAME = "switches.json"
LOCAL_SWITCH_FILE_NAME = "switches.local.json"
MAIN_CHECKOUT_LABEL = "main checkout switches.local.json"
DEFAULT_LABEL = "default"
MAX_SWITCH_FILE_BYTES = 1 << 20

ARM_FILE_NAME = "database-override.once"
CLAIM_PREFIX = "database-override.claimed-"
ARM_NAME_PREFIX = "database-override."
ARM_FRESH_SECONDS = 15 * 60
ARM_FUTURE_SKEW_SECONDS = 60

OFF_TEXTS = frozenset({"off", "0", "false", "no"})
ON_TEXTS = frozenset({"on", "1", "true", "yes"})

_NAME_TEST_RE = re.compile(re.escape(ARM_NAME_PREFIX), re.IGNORECASE)
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_-]")


class SwitchSpec(NamedTuple):
    """One Switch catalog entry."""

    key: str
    kind: str                       # "onoff", "pin" or "index"
    default: str
    local_only: bool                # True: allowed in the Local switch file only
    honoured_by: tuple[str, ...]
    replaces: str                   # the retired variable name, for documents only


class SwitchReading(NamedTuple):
    """The answer for one key: the value in force, where it came from, and the problems found."""

    key: str
    value: str
    source: str
    problems: tuple[str, ...]


#: The Switch catalog: the nine keys of the Inventory, in one place.
CATALOG: dict[str, SwitchSpec] = {
    spec.key: spec
    for spec in (
        SwitchSpec("concept_gate", "onoff", "on", False,
                   ("concept-gate", "concept_changed_check"), "CLAUDE_CONCEPT_GATE"),
        SwitchSpec("pinned_contract", "pin", "", True,
                   ("concept-gate", "concept_changed_check"), "CLAUDE_ACTIVE_CONTRACT"),
        SwitchSpec("architecture_guard", "onoff", "on", False,
                   ("architecture-guard",), "CLAUDE_ARCH_GUARD"),
        SwitchSpec("accuracy_tracker", "onoff", "on", False,
                   ("critic-verdict-tracker", "contract-status-watcher", "journal-post-approval-tracker"),
                   "CLAUDE_ACCURACY_TRACKER"),
        SwitchSpec("integration_check", "onoff", "on", False,
                   ("integration-check",), "CLAUDE_INTEGRATION_CHECK"),
        SwitchSpec("memory_pager", "onoff", "on", False,
                   ("memory-pager",), "CLAUDE_MEMORY_PAGER"),
        SwitchSpec("working_agreements", "onoff", "on", False,
                   ("working-agreements",), "CLAUDE_WORKING_AGREEMENTS"),
        SwitchSpec("plan_question_advisor", "onoff", "on", False,
                   ("plan-question-advisor",), "CLAUDE_PLAN_QUESTION_ADVISOR"),
        SwitchSpec("contract_index", "index", "on", False,
                   ("concept-gate", "bash-gate"), "CLAUDE_CONTRACT_INDEX"),
    )
}

#: Marks an entry that is present but holds a value outside its set (the key stays at its default).
_BAD = object()


# ---------------------------------------------------------------------------
# Value sets
# ---------------------------------------------------------------------------
def _onoff_value(raw: Any) -> str | None:
    """``"on"`` or ``"off"`` for a JSON boolean or one of the old variables' texts; ``None`` otherwise."""
    if isinstance(raw, bool):
        return "on" if raw else "off"
    if isinstance(raw, str):
        text = raw.strip().lower()
        if text in OFF_TEXTS:
            return "off"
        if text in ON_TEXTS:
            return "on"
    return None


def _entry_value(spec: SwitchSpec, raw: Any) -> Any:
    """The normalised value of one entry, or ``_BAD``. ``contract_index`` reads an unknown value as off."""
    if spec.kind == "onoff":
        value = _onoff_value(raw)
        return _BAD if value is None else value
    if spec.kind == "pin":
        return raw.strip() if isinstance(raw, str) else _BAD
    # "index": on, off, trace; an unknown value is off, as the old variable read it
    if isinstance(raw, str) and raw.strip().lower() == "trace":
        return "trace"
    value = _onoff_value(raw)
    return value if value is not None else _BAD


# ---------------------------------------------------------------------------
# Reading one file
# ---------------------------------------------------------------------------
class _FileRead(NamedTuple):
    path: Path
    label: str
    status: str            # "missing", "empty", "ok" or "broken"
    data: dict
    state: str             # the file state the Report-once rule keys on
    kind: str              # the problem kind when broken
    detail: str


def _mtime_text(path: Path) -> str:
    try:
        return str(os.lstat(path).st_mtime_ns)
    except OSError:
        return "0"


def _broken(path: Path, label: str, kind: str, state: str, detail: str = "") -> _FileRead:
    return _FileRead(path, label, "broken", {}, state, kind, detail)


class _NotReadableKind(Exception):
    """The path holds something the reader will not open or read: not a regular file, or a link to a
    network path. The Broken-file rule treats it as unreadable."""


#: Windows drive kinds that are local: removable, fixed, CD-ROM, RAM disk. Anything else (a network
#: drive, an unknown or missing root) is not read.
_LOCAL_DRIVE_KINDS = frozenset({2, 3, 5, 6})
_MAX_LINK_HOPS = 8


def _network_link_reason(path: Path) -> str:
    """Windows only: when ``path`` is a link, the reason its target (or a later link in the chain) is on a
    network drive, is a ``\\\\server\\share`` path or is in the device namespace (``\\\\.\\...``, or
    ``\\\\?\\...`` not followed by a drive letter: a named pipe, a device); ``""`` otherwise. Judged from
    the link text and the LOCAL drive table only: nothing here touches the network, and a target that is
    judged remote or a device is never opened. (A named pipe CAN sit at the end of a link on Windows.)"""
    if os.name != "nt":
        return ""
    current = os.fspath(path)
    for _hop in range(_MAX_LINK_HOPS):
        try:
            if not os.path.islink(current):
                return ""
            target = os.readlink(current)
        except OSError as exc:
            return "the link at %s could not be read (%s)" % (current, type(exc).__name__)
        text = target.replace("/", "\\")  # a forward-slash spelling is the same path
        upper = text.upper()
        if upper.startswith(("\\\\?\\UNC\\", "\\\\.\\UNC\\", "\\??\\UNC\\")):
            return "the link points to a network path: %s" % target
        if text.startswith("\\\\."):
            return "the link points into the device namespace: %s" % target
        if text.startswith(("\\\\?\\", "\\??\\")):
            rest = text[4:]
            if not (len(rest) >= 2 and rest[0].isalpha() and rest[1] == ":"):
                return "the link points into the device namespace: %s" % target
            text = rest
        if text.startswith("\\\\"):
            return "the link points to a network path: %s" % target
        absolute = os.path.join(os.path.dirname(current), text)
        drive = os.path.splitdrive(absolute)[0] or os.path.splitdrive(os.path.abspath(current))[0]
        if drive.startswith("\\\\"):
            return "the link points to a network path: %s" % target
        try:
            import ctypes

            kind = int(ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(drive + "\\")))  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 -- drive kind unknown: not read
            return "the drive of the link target could not be judged: %s" % target
        if kind not in _LOCAL_DRIVE_KINDS:
            return "the link points to a drive that is not local (type %d): %s" % (kind, target)
        current = absolute
    return "the link chain is longer than %d links" % _MAX_LINK_HOPS


def read_regular_file_bytes(path: Path) -> bytes:
    """Read up to ``MAX_SWITCH_FILE_BYTES + 1`` bytes of a REGULAR file, or raise (Commands: "Read regular
    file"). The database guards read their rules file through this too, each mapping a raise to its own
    strict default.

    On every platform: a link to a network path or into the device namespace is refused BEFORE any open
    (Windows; nothing is opened, nothing touches the network); the file is then opened read-only (binary,
    and non-blocking where ``O_NONBLOCK`` exists), its kind is checked on the open descriptor
    (``fstat``), and anything but a regular file is closed unread. So a named pipe at the path, or at the
    end of a link, can never hold the hook."""
    limit = MAX_SWITCH_FILE_BYTES + 1
    reason = _network_link_reason(path)
    if reason:
        raise _NotReadableKind(reason)
    flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
             | getattr(os, "O_CLOEXEC", 0))
    fd = os.open(path, flags)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise _NotReadableKind("not a regular file (a pipe, a device or a socket is at the file path)")
        chunks: list[bytes] = []
        total = 0
        while total < limit:
            chunk = os.read(fd, min(1 << 16, limit - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


#: The private name, kept for the helper's own callers.
_read_regular_file_bytes = read_regular_file_bytes


def _read_file(path: Path, label: str) -> _FileRead:
    """Read one switch file. Never raises."""
    try:
        info = os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return _FileRead(path, label, "missing", {}, "", "", "")
    except OSError as exc:
        return _broken(path, label, "unreadable", "%s|%s|0" % (path, type(exc).__name__), str(exc))
    if stat.S_ISDIR(info.st_mode):
        return _broken(path, label, "unreadable",
                       "%s|IsADirectoryError|%s" % (path, info.st_mtime_ns), "a folder is at the file path")
    try:
        raw = _read_regular_file_bytes(path)
    except _NotReadableKind as exc:
        return _broken(path, label, "unreadable",
                       "%s|%s|%s" % (path, "NotReadableKind", _mtime_text(path)), str(exc))
    except OSError as exc:
        return _broken(path, label, "unreadable",
                       "%s|%s|%s" % (path, type(exc).__name__, _mtime_text(path)), str(exc))
    fingerprint = hashlib.sha256(raw).hexdigest()
    if len(raw) > MAX_SWITCH_FILE_BYTES:
        return _broken(path, label, "too-large", fingerprint, "larger than %d bytes" % MAX_SWITCH_FILE_BYTES)
    try:
        if raw.startswith(codecs.BOM_UTF8):
            text = raw[len(codecs.BOM_UTF8):].decode("utf-8")
        elif raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
            text = raw.decode("utf-16")  # the codec consumes the mark
        else:
            text = raw.decode("utf-8")
    except UnicodeError as exc:
        return _broken(path, label, "undecodable", fingerprint, str(exc))
    if not text.strip():
        return _FileRead(path, label, "empty", {}, fingerprint, "", "")
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as exc:
        return _broken(path, label, "invalid-json", fingerprint, str(exc)[:200])
    if not isinstance(data, dict):
        return _broken(path, label, "not-an-object", fingerprint, "the top level is not a JSON object")
    return _FileRead(path, label, "ok", data, fingerprint, "", "")


def _scan_entries(read: _FileRead, *, local: bool) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """The normalised entries of a readable file and the problems found in it."""
    entries: dict[str, Any] = {}
    problems: list[dict[str, str]] = []
    for key, raw in read.data.items():
        if key == "$comment":
            continue
        spec = CATALOG.get(key)
        if spec is None:
            problems.append({"kind": "unknown-key", "key": str(key)})
            continue
        if spec.local_only and not local:
            problems.append({"kind": "misplaced-key", "key": key})
            continue
        value = _entry_value(spec, raw)
        if value is _BAD:
            problems.append({"kind": "bad-value", "key": key})
            entries[key] = _BAD
            if spec.kind == "index":
                entries[key] = "off"  # an unknown contract_index value means off
            continue
        entries[key] = value
    return entries, problems


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------
def _project_root(project: Any) -> Path | None:
    """The project the lookup is about: the caller's, else ``project_dir()``, else none."""
    try:
        if project is not None and str(project).strip():
            candidate = Path(str(project))
            try:
                return candidate.resolve()
            except OSError:
                return candidate
        if _pp is not None:
            found = _pp.project_dir()
            return Path(found) if found is not None else None
    except Exception:  # noqa: BLE001 -- no project known: every default
        return None
    return None


def _linked_main_root(project: Path) -> Path | None:
    """The main checkout of a LINKED worktree whose own root is ``project``; ``None`` otherwise."""
    if _pp is None:
        return None
    try:
        if _pp.tree_kind(str(project)) != "linked-worktree":
            return None
        own_root, _gitdir = _pp.worktree_own_root(str(project))
        if not own_root or os.path.realpath(own_root) != os.path.realpath(str(project)):
            return None
        root = _pp.main_checkout_root(str(project))
        return Path(root) if root else None
    except Exception:  # noqa: BLE001 -- undecidable: no fallback
        return None


def _state_folder(project: Path | None) -> Path | None:
    try:
        if _pp is not None:
            return Path(_pp.state_dir())
    except Exception:  # noqa: BLE001
        pass
    return (project / ".claude" / "state") if project is not None else None


def _marker_name(prefix: str, text: str, suffix: str) -> str:
    return "%s-%s.%s" % (prefix, hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:32], suffix)


def _marker_exists(folder: Path | None, name: str) -> bool:
    try:
        return folder is not None and (folder / name).exists()
    except OSError:
        return False


def _write_marker(folder: Path | None, name: str) -> bool:
    try:
        if folder is None:
            return False
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text("reported\n", encoding="utf-8")
        return True
    except OSError:
        return False


def _report(read: _FileRead, problems: list[dict[str, str]], project: Path | None) -> None:
    """Report-once rule: the log record first, the marker only after the log write succeeded."""
    try:
        folder = _state_folder(project)
        name = _marker_name("switches", "%s|%s" % (read.path, read.state), "reported")
        if _marker_exists(folder, name):
            return
        details = {"file": str(read.path), "state": read.state[:64], "problems": problems}
        if read.detail:
            details["detail"] = read.detail
        written = log_event("switches", "problem", file=str(read.path), details=details)
        if written is True:
            _write_marker(folder, name)
    except Exception:  # noqa: BLE001 -- the report is passive; the problem is reported again next time
        return


class _Resolution(NamedTuple):
    layers: tuple[tuple[str, dict[str, Any]], ...]   # personal first, then committed
    ignored: bool                                    # a broken file made every file ignored


def _resolve(project: Any) -> _Resolution:
    root = _project_root(project)
    if root is None:
        return _Resolution((), False)
    claude = root / ".claude"
    committed = _read_file(claude / SWITCH_FILE_NAME, SWITCH_FILE_NAME)
    own_local_path = claude / LOCAL_SWITCH_FILE_NAME
    if os.path.lexists(own_local_path):
        personal = _read_file(own_local_path, LOCAL_SWITCH_FILE_NAME)
    else:
        personal = _FileRead(own_local_path, LOCAL_SWITCH_FILE_NAME, "missing", {}, "", "", "")
        main_root = _linked_main_root(root)
        if main_root is not None:
            main_path = main_root / ".claude" / LOCAL_SWITCH_FILE_NAME
            if os.path.lexists(main_path):
                personal = _read_file(main_path, MAIN_CHECKOUT_LABEL)

    layers: list[tuple[str, dict[str, Any]]] = []
    ignored = False
    for read, is_local in ((personal, True), (committed, False)):
        if read.status == "broken":
            ignored = True
            _report(read, [{"kind": read.kind, "key": ""}], root)
        elif read.status == "ok":
            entries, problems = _scan_entries(read, local=is_local)
            if problems:
                _report(read, problems, root)
            layers.append((read.label, entries))
    if ignored:
        return _Resolution((), True)
    return _Resolution(tuple(layers), False)


def _reading(spec: SwitchSpec, resolution: _Resolution) -> SwitchReading:
    for label, entries in resolution.layers:
        if spec.key in entries:
            value = entries[spec.key]
            if value is _BAD:
                return SwitchReading(spec.key, spec.default, DEFAULT_LABEL, ())
            return SwitchReading(spec.key, str(value), label, ())
    return SwitchReading(spec.key, spec.default, DEFAULT_LABEL, ())


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def reading(key: str, project: Any = None) -> SwitchReading:
    """The Switch reading for one key. An unknown key raises ``KeyError`` (a programming error)."""
    spec = CATALOG[key]
    return _reading(spec, _resolve(project))


def switch(key: str, project: Any = None) -> str:
    """The value in force for ``key``: ``"on"``/``"off"``, a pin path or ``""``, or ``"on"``/``"off"``/``"trace"``."""
    return reading(key, project).value


def effective_switches(project: Any = None) -> dict[str, SwitchReading]:
    """Every catalog key's reading. Problems are reported, never raised."""
    resolution = _resolve(project)
    return {key: _reading(spec, resolution) for key, spec in CATALOG.items()}


def off_notice(
    key: str,
    *,
    hook: str,
    session_id: str | None = None,
    project: Any = None,
    guard: bool = False,
) -> dict[str, str] | None:
    """Visible-off rule. When ``key`` holds a non-default value, write one line to standard error.

    For a guard switched off, also return ``{"systemMessage": ...}`` (the host shows it to the person),
    once per session, per key, per value and per source file; the caller prints it as JSON. Returns
    ``None`` when there is nothing to show. Never raises.
    """
    try:
        current = reading(key, project)
        if current.value == CATALOG[key].default:
            return None
        try:
            sys.stderr.write("[%s] switch %s is %s (from %s)\n" % (hook, key, current.value, current.source))
        except Exception:  # noqa: BLE001
            pass
        if not guard:
            return None
        folder = _state_folder(_project_root(project))
        name = _marker_name("switches-notice", "|".join((session_id or "", key, current.value, current.source)), "shown")
        if session_id and _marker_exists(folder, name):
            return None
        if session_id:
            _write_marker(folder, name)  # a failed write only means the notice is shown again
        return {"systemMessage": (
            "Guard switched off: %s is %s (set in %s). The %s guard is not enforcing. "
            "Set it back to on in the switch file to turn it on again."
            % (key, current.value, current.source, hook))}
    except Exception:  # noqa: BLE001
        return None


def names_override_file(path_or_text: Any) -> bool:
    """Name test of the Arm-write rule: True when the path or text names ``database-override.<anything>``."""
    try:
        return bool(_NAME_TEST_RE.search(str(path_or_text)))
    except Exception:  # noqa: BLE001
        return False


def _normalised_parts(path_text: Any) -> list[str]:
    """The parts of a path as the file system reads it: both slashes fold, ``.`` parts vanish, ``..``
    removes the part before it, and a part that is nothing but dots and spaces (Windows drops trailing
    dots and spaces) vanishes too."""
    parts: list[str] = []
    for part in str(path_text).replace("\\", "/").split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        if not part.rstrip(". "):
            continue
        parts.append(part)
    return parts


def names_override_path(path_text: Any) -> bool:
    """Name test of the Arm-write rule for an edit tool's target path (W1).

    True when the LAST part of the normalised path starts with ``database-override.`` (any case, either
    slash). ``<arm>/.`` and ``<arm>/x/..`` reach the arm and are named; ``<arm>/../notes.md`` is not."""
    try:
        parts = _normalised_parts(path_text)
        return bool(parts) and parts[-1].lower().startswith(ARM_NAME_PREFIX)
    except Exception:  # noqa: BLE001
        return False


def _safe_id(tool_call_id: Any) -> str:
    text = _SAFE_ID_RE.sub("_", str(tool_call_id or "").strip())
    return text[:100]


def _remove_quietly(path: Path) -> None:
    try:
        if os.path.islink(path) or path.is_file():
            os.unlink(path)
        elif path.is_dir():
            os.rmdir(path)
    except OSError:
        pass


def _is_fresh_age(modified: float) -> bool:
    """Fresh-arm window: modified in the last 15 minutes and not more than 60 seconds ahead of now."""
    age = time.time() - modified
    return -ARM_FUTURE_SKEW_SECONDS <= age <= ARM_FRESH_SECONDS


def _sweep_old_claims(claude: Path) -> None:
    """Remove claims older than the arm's lifetime, or dated more than 60 seconds ahead."""
    try:
        for entry in claude.glob(CLAIM_PREFIX + "*"):
            try:
                if not _is_fresh_age(os.lstat(entry).st_mtime):
                    _remove_quietly(entry)
            except OSError:
                continue
    except OSError:
        pass


def _fresh_regular_file(path: Path) -> bool:
    try:
        info = os.lstat(path)
        return stat.S_ISREG(info.st_mode) and _is_fresh_age(info.st_mtime)
    except OSError:
        return False


def claim_database_override(project: Any, tool_call_id: Any) -> str:
    """Claim the Database override arm by an atomic rename. Returns an Override outcome; never raises.

    ``absent``, ``stale``, ``unusable``, ``claimed`` or ``claimed-by-sibling``. The outcome
    ``no-prompt-available`` is decided by the guard, from the permission mode.
    """
    try:
        root = _project_root(project)
        if root is None:
            return "absent"
        claude = root / ".claude"
        arm = claude / ARM_FILE_NAME
        identifier = _safe_id(tool_call_id)
        sibling_claim = (claude / (CLAIM_PREFIX + identifier)) if identifier else None
        _sweep_old_claims(claude)
        try:
            info = os.lstat(arm)
        except (FileNotFoundError, NotADirectoryError):
            if sibling_claim is not None and _fresh_regular_file(sibling_claim):
                return "claimed-by-sibling"
            return "absent"
        except OSError:
            return "unusable"
        if not stat.S_ISREG(info.st_mode):
            _remove_quietly(arm)
            return "unusable"
        if not _is_fresh_age(info.st_mtime):
            _remove_quietly(arm)
            return "stale"
        target = sibling_claim if sibling_claim is not None else claude / (CLAIM_PREFIX + "noid-" + uuid.uuid4().hex[:12])
        try:
            if os.path.lexists(target):  # a second claim for one tool call never overwrites the first
                return "claimed-by-sibling" if sibling_claim is not None else "unusable"
            os.rename(arm, target)
        except FileNotFoundError:
            if sibling_claim is not None and _fresh_regular_file(sibling_claim):
                return "claimed-by-sibling"
            return "absent"
        except OSError:
            return "unusable"
        return "claimed"
    except Exception:  # noqa: BLE001 -- never raises: no override
        return "unusable"


__all__ = [
    "CATALOG", "SwitchSpec", "SwitchReading", "reading", "switch", "effective_switches", "off_notice",
    "names_override_file", "names_override_path", "claim_database_override",
]
