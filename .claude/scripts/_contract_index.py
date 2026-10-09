"""
_contract_index.py -- the contract lookup index.

A disposable, machine-local memory of what each concept contract file said the
last time a gate read it: its Status and its "Files to touch" entries. Two hooks
(concept-gate and bash-gate) answer one question per real source write -- "is
this file listed in an approved contract?" -- and used to read every contract
file to find out. This module lets a gate skip a read when, and only when, the
file provably has not changed since it was read.

It changes how contracts are found, never what is allowed:

  * The gates keep their own loops, their own allow rules and ONE parser each.
    This module never parses a contract: on a miss it calls the gate's own
    function on the real file, exactly as the gate would without an index.
  * A stored record is used only when ALL of these hold (rule R1):
      (a) os.stat of the path (never a directory-listing entry) gives the same
          size, modification time and file id as the record;
      (b) the file's modification time is at least two seconds older than the
          moment it was parsed;
      (c) the file's modification time is at least two seconds older than the
          moment of the lookup (a file stamped in the future never qualifies).
    Anything else is a miss: the gate reads the file as it always did.
  * A result a read error can produce (status "unknown", an empty entry list)
    is never stored (rule R4).
  * Any trouble with the index -- missing, unreadable, truncated, wrong schema,
    variant, fingerprint or root -- means "empty", never "partly usable" (I2).

Public entry points (a gate binds each with getattr and wraps every call; if
one is missing the gate uses its own functions):

    make_variant(name, status_fn, entries_fn, cover_fn, sources) -> variant
    status_of(variant, path)            -> the Status the gate's own function gives
    covers(variant, path, target)       -> True iff the entries cover the target

Storage: <X>/.claude/cache/contract-index/<variant>-<fingerprint[:12]>.json,
where <X>/.claude/concepts is the contract root. One file per (root, variant,
fingerprint). Written by atomic replace of a same-folder temporary file named
<file>.<pid>.<random hex>.tmp; never edited in place; no lock (last writer wins:
every record validates itself). Deleting the folder is always safe.

Switch CLAUDE_CONTRACT_INDEX (trimmed, case-insensitive, read once per process):
    unset, empty, on, 1, true, yes   index on
    off, 0, false, no                off: no index read or write, no output
    trace                            on, plus one stderr line per variant at exit
    anything else                    off, plus one stderr line naming the value
No value is ever looser than "on": the worst a value does is run slower or
louder.

Named limit (cannot be seen): a same-size in-place rewrite whose modification
time is then restored to its old value, more than two seconds after the last
parse. Recovery: CLAUDE_CONTRACT_INDEX=off, or delete the index folder.

Standard library only.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import sys
import time
from pathlib import Path

#: The index file format version.
SCHEMA = 1

#: Two seconds, in nanoseconds: the racy window of rules R1 (b) and (c).
_RACY_NS = 2_000_000_000

_ON_VALUES = {"", "on", "1", "true", "yes"}
_OFF_VALUES = {"off", "0", "false", "no"}

#: Resolved once per process: "on", "off" or "trace".
_MODE: str | None = None

#: Every variant made in this process, for the exit handler.
_VARIANTS: list = []

#: True once the exit handler is registered.
_ARMED = False


# ---------------------------------------------------------------------------
# Switch
# ---------------------------------------------------------------------------
def _mode() -> str:
    """The lookup mode, read from the environment once per process."""
    global _MODE
    if _MODE is None:
        raw = os.environ.get("CLAUDE_CONTRACT_INDEX", "").strip()
        value = raw.lower()
        if value in _ON_VALUES:
            _MODE = "on"
        elif value in _OFF_VALUES:
            _MODE = "off"
        elif value == "trace":
            _MODE = "trace"
        else:
            _MODE = "off"
            try:
                print(
                    f"[contract-index] unknown CLAUDE_CONTRACT_INDEX value {raw!r}; "
                    "the index is off",
                    file=sys.stderr,
                )
            except Exception:
                pass
    return _MODE


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class _Root:
    """One contract root's records for one variant."""

    def __init__(self, root_dir: str, root_norm: str, index_path: str, usable: bool) -> None:
        self.root_dir = root_dir
        self.root_norm = root_norm
        self.index_path = index_path
        self.usable = usable
        self.records: dict = {}
        self.loaded = False
        self.dirty = False


class _Variant:
    """A gate's variant spec plus this process's counters."""

    def __init__(self, name, status_fn, entries_fn, cover_fn, sources) -> None:
        self.name = str(name)
        self.status_fn = status_fn
        self.entries_fn = entries_fn
        self.cover_fn = cover_fn
        self.sources = [str(s) for s in sources]
        self.fingerprint: str | None = None
        self.fingerprint_tried = False
        self.roots: dict = {}
        self.by_spelling: dict = {}
        self.hits = 0
        self.misses = 0
        self.uncacheable = 0
        self.write = "skipped"
        self.read_start = 0
        self.read_end = 0
        self.replace_start = 0
        self.replace_end = 0
        self.replace_count = 0
        self.replace_failed = False


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------
def make_variant(name, status_fn, entries_fn, cover_fn, sources):
    """Describe one gate's parser variant.

    ``status_fn(path)`` and ``entries_fn(path)`` are the gate's own functions;
    ``cover_fn(entries, target)`` is its own entries-cover function; ``sources``
    are the files whose bytes define those functions (they form the
    fingerprint, so a changed parser never reads an older parser's records).
    """
    variant = _Variant(name, status_fn, entries_fn, cover_fn, sources)
    _VARIANTS.append(variant)
    return variant


def status_of(variant, path):
    """The contract's Status, exactly as the gate's own function returns it."""
    return _resolve(variant, path, "status")


def covers(variant, path, target):
    """True iff the contract's Files-to-touch entries cover ``target``."""
    entries = _resolve(variant, path, "entries")
    return variant.cover_fn(entries, target)


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------
def _resolve(variant, path, want: str):
    """Serve ``want`` ("status" or "entries") from the index, or from the real file."""
    real = variant.entries_fn if want == "entries" else variant.status_fn
    mode = _mode()
    if mode == "off":
        return real(path)
    if mode == "trace":
        _arm()

    root = None
    rel = None
    before = None
    try:
        located = _locate(path)
        if located is not None:
            root = _root_state(variant, located[0])
            rel = located[1]
            if not root.usable:
                root = None
            else:
                if not root.loaded:
                    _load(variant, root)
                before = os.stat(path)
    except Exception:
        root = None
        before = None

    if root is not None and before is not None:
        try:
            if _trusted(root.records.get(rel), before, want):
                variant.hits += 1
                return root.records[rel][want]
        except Exception:
            pass

    parsed_at = time.time_ns()  # taken BEFORE the read
    value = real(path)
    if want == "status":
        unusable = value == "unknown"
    else:
        unusable = not value
    if unusable:
        variant.uncacheable += 1
    else:
        variant.misses += 1
        if root is not None and before is not None:
            try:
                _remember(root, rel, path, before, parsed_at, want, value)
            except Exception:
                pass
    return value


def _locate(path):
    """(root folder, path relative to it) for a contract path, or None.

    The root is the nearest ancestor named "concepts" (case-insensitive) whose
    parent is named ".claude".
    """
    p = Path(path)
    for parent in p.parents:
        if parent.name.lower() == "concepts" and parent.parent.name == ".claude":
            return parent, p.relative_to(parent).as_posix()
    return None


def _root_state(variant, root: Path):
    """The shared state of one root, however its path is spelled."""
    spelled = str(root)
    state = variant.by_spelling.get(spelled)
    if state is not None:
        return state
    norm = os.path.normcase(os.path.abspath(spelled))
    state = variant.roots.get(norm)
    if state is None:
        fingerprint = _fingerprint(variant)
        usable = fingerprint is not None and os.path.isdir(spelled)
        index_path = ""
        if usable:
            folder = os.path.join(os.path.dirname(spelled), "cache", "contract-index")
            index_path = os.path.join(folder, f"{variant.name}-{fingerprint[:12]}.json")
        state = _Root(spelled, norm, index_path, usable)
        variant.roots[norm] = state
    variant.by_spelling[spelled] = state
    return state


def _fingerprint(variant) -> str | None:
    """Hash of the bytes of the files that define the variant's parse functions."""
    if not variant.fingerprint_tried:
        variant.fingerprint_tried = True
        try:
            digest = hashlib.sha256()
            for source in variant.sources:
                with open(source, "rb") as handle:
                    data = handle.read()
                digest.update(str(len(data)).encode("ascii"))
                digest.update(b":")
                digest.update(data)
            variant.fingerprint = digest.hexdigest()
        except Exception:
            variant.fingerprint = None
    return variant.fingerprint


def _load(variant, root: _Root) -> None:
    """Load a root's index file. Anything wrong with it means an empty index."""
    start = time.time_ns()
    records: dict = {}
    try:
        with open(root.index_path, "rb") as handle:
            raw = handle.read()
        data = json.loads(raw.decode("utf-8"))
        if (
            isinstance(data, dict)
            and data.get("schema") == SCHEMA
            and data.get("variant") == variant.name
            and data.get("fingerprint") == variant.fingerprint
            and data.get("root") == root.root_norm
            and isinstance(data.get("records"), dict)
        ):
            records = data["records"]
    except Exception:
        records = {}
    end = time.time_ns()
    root.records = records
    root.loaded = True
    if variant.read_end == 0:
        variant.read_start = start
    variant.read_end = end


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _trusted(record, stat_result, want: str) -> bool:
    """Rule R1: may this record answer for the file as it is now?"""
    if not isinstance(record, dict):
        return False
    size = record.get("size")
    mtime = record.get("mtime_ns")
    file_id = record.get("file_id")
    parsed_at = record.get("parsed_at_ns")
    if not (_is_int(size) and _is_int(mtime) and _is_int(file_id) and _is_int(parsed_at)):
        return False
    if not isinstance(record.get("status"), str):
        return False
    if want == "entries":
        entries = record.get("entries")
        if not isinstance(entries, list) or not entries:
            return False
        if not all(isinstance(e, str) for e in entries):
            return False
    # (a) the same signature, from os.stat of the path itself
    if (size != stat_result.st_size or mtime != stat_result.st_mtime_ns
            or file_id != stat_result.st_ino):
        return False
    # (b) not racy when it was parsed
    if mtime > parsed_at - _RACY_NS:
        return False
    # (c) not racy now, and not stamped in the future
    if mtime > time.time_ns() - _RACY_NS:
        return False
    return True


def _remember(root: _Root, rel, path, before, parsed_at: int, want: str, value) -> None:
    """Rule R4: keep a miss's result only if the file did not move under the read."""
    after = os.stat(path)
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
            after.st_size, after.st_mtime_ns, after.st_ino):
        return
    signature = {
        "size": before.st_size,
        "mtime_ns": before.st_mtime_ns,
        "file_id": before.st_ino,
    }
    if want == "status":
        record = dict(signature)
        record["parsed_at_ns"] = parsed_at
        record["status"] = value
        root.records[rel] = record
    else:
        record = root.records.get(rel)
        if not isinstance(record, dict):
            return
        if any(record.get(key) != signature[key] for key in signature):
            return
        record["entries"] = list(value)
    root.dirty = True
    _arm()


# ---------------------------------------------------------------------------
# Exit: write what changed, then report (trace mode only)
# ---------------------------------------------------------------------------
def _arm() -> None:
    """Register the one exit handler (once). It runs on every exit path."""
    global _ARMED
    if not _ARMED:
        _ARMED = True
        atexit.register(_finish)


def _finish() -> None:
    """Exit handler: write dirty index files, then print the trace lines.

    Wrapped end to end: it cannot change an exit code and prints nothing
    outside trace mode.
    """
    try:
        for variant in list(_VARIANTS):
            _flush(variant)
        if _MODE == "trace":
            for variant in list(_VARIANTS):
                try:
                    print(_trace_line(variant), file=sys.stderr)
                except Exception:
                    pass
            try:
                sys.stderr.flush()
            except Exception:
                pass
    except BaseException:
        pass


def _flush(variant) -> None:
    """Write one variant's dirty roots; record the outcome, never raise."""
    try:
        _save_variant(variant)
    except Exception as exc:
        variant.write = "failed:" + _cause(exc)


def _cause(exc: BaseException) -> str:
    return "".join(type(exc).__name__.split()) or "error"


def _save_variant(variant) -> None:
    """Write every dirty root of the variant, one atomic replace each."""
    for root in list(variant.roots.values()):
        if not (root.dirty and root.usable):
            continue
        try:
            _save_root(variant, root)
            if not variant.write.startswith("failed:"):
                variant.write = "ok"
        except Exception as exc:
            variant.write = "failed:" + _cause(exc)


def _save_root(variant, root: _Root) -> None:
    """Atomic replace of one index file by a same-folder temporary file (I3)."""
    folder = os.path.dirname(root.index_path)
    os.makedirs(folder, exist_ok=True)
    payload = {
        "schema": SCHEMA,
        "variant": variant.name,
        "fingerprint": variant.fingerprint,
        "root": root.root_norm,
        "records": root.records,
    }
    temp = f"{root.index_path}.{os.getpid()}.{os.urandom(6).hex()}.tmp"
    replaced = False
    try:
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
        start = time.time_ns()
        try:
            os.replace(temp, root.index_path)
            replaced = True
        finally:
            _note_replace(variant, start, time.time_ns(), replaced)
    finally:
        if not replaced:
            try:
                os.unlink(temp)
            except OSError:
                pass


def _note_replace(variant, start: int, end: int, ok: bool) -> None:
    """Remember the wall-clock interval of an attempted os.replace."""
    if variant.replace_count == 0:
        variant.replace_start = start
    variant.replace_end = end
    variant.replace_count += 1
    if not ok:
        variant.replace_failed = True


def _trace_line(variant) -> str:
    """The one trace line of a variant (one physical line, no spaces in a cause)."""
    if variant.replace_count:
        outcome = "failed" if variant.replace_failed else "ok"
        replace = f"{variant.replace_start}:{variant.replace_end}:{outcome}"
    else:
        replace = "none"
    return (
        f"[contract-index] variant={variant.name} hits={variant.hits} "
        f"misses={variant.misses} uncacheable={variant.uncacheable} "
        f"write={variant.write} read={variant.read_start}:{variant.read_end} "
        f"replace={replace}"
    )
