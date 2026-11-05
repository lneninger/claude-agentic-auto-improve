#!/usr/bin/env python3
"""
codegraph-first-guard.py -- PreToolUse hook for the CodeGraph-First Protocol.

Asks the agent to start an investigation with a CodeGraph tool: it blocks Read / Grep / Glob on source-code paths
until one has been called in the current investigation turn. It is a NUDGE, never a wall: it fails open whenever
CodeGraph is provably unavailable, and the identical retry of a call it just blocked is allowed once.

The "turn" is bounded by UserPromptSubmit and keyed to the SESSION, not to a directory:
    UserPromptSubmit -> codegraph-turn-reset.py deletes the session's marker and retry tickets
    PostToolUse on mcp__codegraph__* -> codegraph-turn-tracker.py writes the marker
    PreToolUse on Read|Grep|Glob -> this hook checks for the marker

Hook contract (Claude Code):
    stdin:  JSON with { session_id, cwd, tool_name, tool_input: {...}, agent_id (subagents only) }
    exit 0: allow (a `[codegraph-first-guard] allowed (<reason>)` line on stderr when it is a fail-open or a retry)
    exit 2: block (stderr shown to Claude)
    other:  error (hook fails open -- logs to stderr, allows the call)

Session folder (shared by the three hooks):
    <system temp folder>/auto-improve-codegraph-<session key>/
        turn.json            the Turn marker {ts, tool, summary, pid}
        ticket-<64 hex>      a Retry escape ticket, issued at a block, consumed by the identical retry
        availability.json    the cached server and index verdicts
        logged-<reason>      at most one log record per session per fail-open reason

        transcript-cursor.json   the shadow's Transcript cursor (issue #261); transcript-cursor.<pid>.tmp is its temp file

Decision order (concept contracts 2026-11-05-codegraph-guard-fail-open and 2026-11-05-codegraph-hooks-redesign, G-1):
    0. the Session folder is unusable            -> allow (fail-open:state-unwritable; it logs on every call,
                                                    because there is no writable state to rate-limit it)
    2. the Turn marker exists                    -> allow (checked BEFORE the paths are classified: steps 1 and 2 are
                                                    both silent allows, so only the internal reason differs)
    1. no target / only non-source targets       -> allow
    3. the payload carries a non-empty agent_id  -> allow (fail-open:subagent)
    4. no Project index / index of another tree  -> allow (fail-open:no-index / fail-open:index-other-tree)
    5. the server is not configured / disabled   -> allow (fail-open:server-not-configured / server-disabled)
    6. a ticket matches the call's fingerprint   -> delete it, allow (retry-escape-used)
    7. otherwise write the ticket and block.

main() runs the decision in three parts (G-2): the Live plan (a pure function: it reads, it writes nothing), the SHADOW
SECTION (the same planner with the Transcript turn state in place of the Turn marker; it logs one Shadow record to
<CLAUDE_PROJECT_DIR>/.claude/logs/codegraph-shadow.jsonl and enforces nothing; whatever it raises is swallowed), then the
Live plan's effects (availability.json, the ticket, the notice flags, log records, the stderr line, the exit code).

There is no kill switch: no environment variable turns the guard off.
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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Issue #261, G-1: the two helpers are imported on first USE (classification, the fallback banner, a log record), not at
# module load, so a call the Turn marker allows never pays for them. Every module-level name below keeps its meaning and
# stays patchable (``mock.patch.object(guard, "_pp", None)``): the names resolve through the module ``__getattr__`` on
# first read, a value set before that read is never overwritten, and this file reads them through ``_late``.
#:   log_event                        ``_error_log.log_event`` (passive error logging), or a no-op when it cannot be imported.
#:   _pp                              ``_project_paths`` (project-local .claude first, global second), or None. This hook had
#:                                    no dependency on it before issue #222 (has_bypass_segment needs the checkout-equivalent path).
#:   _pp_checkout_equivalent_path     bound with ``getattr`` (concept-gate.py's identical comment): a missing function is treated
#:                                    EXACTLY like ``_pp`` being None, the fallback-mode banner text included.
#:   _pp_worktree_own_root            issue #259: bound the same way; a helper from an earlier release lacks it, the inline walk is used.
#:   _pp_tree_kind, _pp_main_checkout_root
#:                                    bound ONLY from a helper that carries the hop refusal (``_hop_allowed``): an older helper
#:                                    probes the host a hostile ``gitdir:`` line names before any caller-side check could run,
#:                                    so with one of those ``index-other-tree`` cannot fire and the old functions are never called.
_PP_NAMES = frozenset({
    "_pp", "_pp_checkout_equivalent_path", "_pp_worktree_own_root", "_pp_has_hop_refusal", "_pp_tree_kind",
    "_pp_main_checkout_root"})


#: What ``import _error_log`` / ``import _project_paths`` would have resolved to AT MODULE LOAD, kept so that a deferred import
#: binds the same helper: the modules already in ``sys.modules`` then, and the search path then (both are cheap to copy).
_HELPER_NAMES = ("_error_log", "_project_paths")
_LOAD_TIME_MODULES = {name: sys.modules.get(name) for name in _HELPER_NAMES}
_LOAD_TIME_PATH = list(sys.path)


def _import_helper(name: str):
    """``import <name>`` deferred to first use, resolving as it would have at module load. Raises ImportError when absent."""
    held = _LOAD_TIME_MODULES.get(name)
    if held is not None:
        return held  # it was already imported when this file loaded: the same object an eager import bound
    from importlib import machinery, util
    spec = machinery.PathFinder.find_spec(name, _LOAD_TIME_PATH)
    if spec is None or spec.loader is None:
        raise ImportError("No module named %r" % name)
    cached = sys.modules.get(name)
    if cached is not None and getattr(cached, "__file__", None) and spec.origin \
            and os.path.normcase(os.path.abspath(cached.__file__)) == os.path.normcase(os.path.abspath(spec.origin)):
        return cached  # already imported since (``_error_log`` imports ``_project_paths``): share it, never load twice
    module = util.module_from_spec(spec)
    registered = name not in sys.modules
    if registered:
        sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        if registered:
            sys.modules.pop(name, None)
        raise
    return module


def _load_log_event() -> None:
    try:
        bound = _import_helper("_error_log").log_event
    except Exception:
        def bound(*args, **kwargs):  # type: ignore[misc]
            return
    globals().setdefault("log_event", bound)


def _load_project_paths() -> None:
    scope = globals()
    try:
        helper = _import_helper("_project_paths")
    except Exception:  # pragma: no cover - hooks must never crash a tool call
        helper = None
    scope.setdefault("_pp", helper)
    pp = scope["_pp"]
    scope.setdefault("_pp_checkout_equivalent_path", getattr(pp, "checkout_equivalent_path", None) if pp is not None else None)
    scope.setdefault("_pp_worktree_own_root", getattr(pp, "worktree_own_root", None) if pp is not None else None)
    scope.setdefault("_pp_has_hop_refusal", pp is not None and callable(getattr(pp, "_hop_allowed", None)))
    scope.setdefault("_pp_tree_kind", getattr(pp, "tree_kind", None) if scope["_pp_has_hop_refusal"] else None)
    scope.setdefault("_pp_main_checkout_root",
                     getattr(pp, "main_checkout_root", None) if scope["_pp_has_hop_refusal"] else None)


def __getattr__(name: str):
    """PEP 562: bind a helper-derived module name on first read."""
    if name == "log_event":
        _load_log_event()
    elif name in _PP_NAMES:
        _load_project_paths()
    else:
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    return globals()[name]


def _late(name: str):
    """The current value of a lazily bound module-level name (a patched value wins)."""
    try:
        return globals()[name]
    except KeyError:
        return __getattr__(name)

#: The full path this hook's copy of ``_project_paths.py`` would live at, used
#: only to name the missing helper in a fallback-mode block banner (INV-5).
_PROJECT_PATHS_EXPECTED_PATH = str(Path(__file__).resolve().parent / "_project_paths.py")

#: Case-insensitive via the flag, never a ``.lower()`` copy (see
#: concept-gate.py's identical comment). The optional trailing group after
#: ``worktrees`` folds the Windows aliases the helper recognises (round 3
#: task F).
_FALLBACK_WORKTREE_MARKER_RE = re.compile(
    r"/\.claude/worktrees(?:[.\ ]*|:[^/]*)/[^/]+", re.IGNORECASE
)


def _fallback_checkout_equivalent(path_str: str) -> str:
    """INV-5 fallback: crude stand-in for ``_project_paths.checkout_equivalent_path``.

    Used ONLY when ``import _project_paths`` failed. Strips the segment
    test's input down to the text after the LAST worktree-segment marker, so
    worktree source still gets no bypass while the helper is missing. A path
    with no marker is returned unchanged (today's behaviour).

    "." components are dropped BEFORE doubled separators are collapsed (round
    3 task E) -- see concept-gate.py's identical comment.
    """
    norm = path_str.replace("\\", "/")
    no_dots = re.sub(r"(^|/)\.(?=/|$)", r"\1", norm)
    collapsed = re.sub(r"/{2,}", "/", no_dots)
    matches = list(_FALLBACK_WORKTREE_MARKER_RE.finditer(collapsed))
    if not matches:
        return norm
    return collapsed[matches[-1].end():]


def _segment_test_path(path_str: str) -> str:
    """The text this guard's segment bypass test should read (INV-2)."""
    bound = _late("_pp_checkout_equivalent_path")
    if bound is not None:
        return bound(path_str)
    return _fallback_checkout_equivalent(path_str)


# File extensions that bypass the gate unconditionally (non-code).
TRIVIAL_EXTENSIONS = {
    ".md", ".markdown", ".txt", ".rst",
    ".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".gitignore", ".gitattributes", ".editorconfig",
    ".env", ".lock",
    ".log", ".csv", ".tsv",
    ".sql", ".http",
}

# File extensions considered source code (gated without prior CodeGraph call).
SOURCE_EXTENSIONS = {
    ".cs", ".fs", ".vb", ".fsx", ".csx",
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".html", ".scss", ".sass", ".css", ".less",
    ".py", ".pyx", ".pyi",
    ".java", ".kt", ".scala",
    ".go", ".rs", ".cpp", ".c", ".h", ".hpp",
    ".rb", ".php", ".swift",
}

# Path substrings that bypass the gate unconditionally (generated, deps, etc.).
BYPASS_PATH_SEGMENTS = [
    "/.claude/",
    "\\.claude\\",
    "/.claude\\",
    "\\.claude/",
    "/.git/",
    "\\.git\\",
    "/node_modules/",
    "\\node_modules\\",
    "/bin/",
    "\\bin\\",
    "/obj/",
    "\\obj\\",
    "/dist/",
    "\\dist\\",
    "/build/",
    "\\build\\",
    "/migrations/",
    "\\migrations\\",
    "/generated/",
    "\\generated\\",
    "/assets/wiki/",
    "\\assets\\wiki\\",
    "/__pycache__/",
    "\\__pycache__\\",
    "/.venv/",
    "\\.venv\\",
    "/venv/",
    "\\venv\\",
    "/concepts/",
    "\\concepts\\",
    "/.codegraph/",
    "\\.codegraph\\",
]

# Filenames that bypass the gate.
BYPASS_FILENAMES = {
    "CLAUDE.md",
    "memory.md",
    "MECHANISMS.md",
    "VOCABULARY.md",
    "JOURNAL.md",
    "INTEGRATION.md",
    "README.md",
    ".gitkeep",
}

# ---------------------------------------------------------------------------
# Session folder (the pattern of _project_paths._marker_path, copied inline: an add-on copies a helper only when
# the project lacks it, so an old project helper must not be a dependency).
# ---------------------------------------------------------------------------
SESSION_PREFIX = "auto-improve-codegraph-"
MARKER_NAME = "turn.json"
AVAILABILITY_NAME = "availability.json"
TICKET_PREFIX = "ticket-"
LOGGED_PREFIX = "logged-"
LEGACY_SENTINEL_NAME = ".codegraph-used-this-turn"
SERVER_NAME = "codegraph"
_SESSION_ID_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9_-])?")  # never ends in "." (Windows strips it)
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

#: One sentence per allow reason that prints a stderr line.
NOTICES = {
    "fail-open:no-index": (
        "no CodeGraph index (.codegraph/codegraph.db) was found for this project, so there is nothing to ask "
        "first. Run `codegraph init -i` to build one."),
    "fail-open:index-other-tree": (
        "the CodeGraph index belongs to the main checkout, not to this working tree, so its answers would be "
        "stale here. Run `codegraph init -i` in this tree to bring the gate back."),
    "fail-open:server-not-configured": "the CodeGraph MCP server is not configured for this project.",
    "fail-open:server-disabled": "the CodeGraph MCP server is disabled for this project.",
    "fail-open:subagent": "this is a subagent session, which may have no CodeGraph tool attached.",
    "fail-open:state-unwritable": (
        "the guard's session folder in the system temp folder cannot be used, so it cannot record a retry."),
    "retry-escape-used": (
        "the identical call was blocked just before; it is allowed once and logged as a retry-escape."),
}


def log(msg: str) -> None:
    """Log to stderr so Claude sees the diagnostic line."""
    print(f"[codegraph-first-guard] {msg}", file=sys.stderr)


def _is_link_stat(st: os.stat_result) -> bool:
    """Delivery cleanup's link test: a symlink, or on Windows a reparse point (junction). Never a Python 3.12-only helper."""
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & _REPARSE_POINT)


def _is_link(path: str) -> bool:
    try:
        return _is_link_stat(os.lstat(path))
    except OSError:
        return False


def _norm_path(path: str) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _payload_cwd(payload: dict) -> str:
    value = payload.get("cwd")
    return value if isinstance(value, str) and value else os.getcwd()


def session_key(payload: dict) -> str:
    """The session_id when it matches the grammar, else ``cwd-`` + 16 hex digits of SHA-256 of the normalised cwd."""
    sid = payload.get("session_id")
    if isinstance(sid, str) and _SESSION_ID_RE.fullmatch(sid):
        return sid
    digest = hashlib.sha256(_norm_path(_payload_cwd(payload)).encode("utf-8", "replace")).hexdigest()
    return "cwd-" + digest[:16]


def _atomic_write(final: str, data: str) -> bool:
    """Write ``data`` to a random sibling created with O_EXCL (and O_NOFOLLOW where the OS has it), then
    ``os.replace`` it onto ``final``. The final name is never opened for writing, so a link planted there is
    replaced, not written through."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    temp = os.path.join(os.path.dirname(final), ".tmp-" + os.urandom(8).hex())
    try:
        fd = os.open(temp, flags, 0o600)
    except OSError:
        return False
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data.encode("utf-8"))
        os.replace(temp, final)
    except OSError:
        try:
            os.remove(temp)
        except OSError:
            pass
        return False
    return True


class Session:
    """The Session folder of one payload and the small state kept in it."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.key = session_key(payload)
        self.folder = os.path.join(tempfile.gettempdir(), SESSION_PREFIX + self.key)

    def folder_usable(self) -> bool:
        """False when the folder is a link, not a folder, owned by another POSIX user, or not writable.
        An absent folder is usable (it is created on the first write)."""
        try:
            st = os.lstat(self.folder)
        except FileNotFoundError:
            return True
        except OSError:
            return False
        if _is_link_stat(st) or not stat.S_ISDIR(st.st_mode):
            return False
        if hasattr(os, "getuid") and st.st_uid != os.getuid():
            return False
        return os.access(self.folder, os.W_OK)

    def ensure_folder(self) -> bool:
        """Create the folder when absent and re-check it. False when it cannot be used."""
        try:
            os.mkdir(self.folder, 0o700)
        except FileExistsError:
            pass
        except OSError:
            return False
        return self.folder_usable()

    def path(self, name: str) -> str:
        return os.path.join(self.folder, name)

    def has_plain_file(self, name: str) -> bool:
        try:
            st = os.lstat(self.path(name))
        except OSError:
            return False
        return stat.S_ISREG(st.st_mode) and not _is_link_stat(st)

    def write(self, name: str, data: str) -> bool:
        if not self.ensure_folder():
            return False
        return _atomic_write(self.path(name), data)

    def read_json(self, name: str) -> dict:
        if not self.has_plain_file(name):
            return {}
        try:
            with open(self.path(name), "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def create_once(self, name: str) -> str:
        """Create an empty flag file: 'created', 'exists', or 'error'."""
        if not self.ensure_folder():
            return "error"
        try:
            fd = os.open(self.path(name), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return "exists"
        except OSError:
            return "error"
        os.close(fd)
        return "created"


# ---------------------------------------------------------------------------
# Project index and tree ownership (no subprocess: .git entries and stat calls only)
# ---------------------------------------------------------------------------
def _has_project_index(folder: str) -> bool:
    """A Project index: ``<folder>/.codegraph/codegraph.db`` is a regular file; neither it nor ``.codegraph`` is a
    link. A ``.codegraph`` folder without ``codegraph.db`` (CodeGraph's per-user data folder) is NOT an index."""
    try:
        cg = os.path.join(folder, ".codegraph")
        cg_st = os.lstat(cg)
        if _is_link_stat(cg_st) or not stat.S_ISDIR(cg_st.st_mode):
            return False
        db_st = os.lstat(os.path.join(cg, "codegraph.db"))
        return stat.S_ISREG(db_st.st_mode) and not _is_link_stat(db_st)
    except (OSError, ValueError):
        return False


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


def _hop_allowed(target: str, own: str, *also: str) -> bool:
    """A pointer hop may be looked at when it is local, or a UNC or device path whose host is the host of the tree's
    own path or of any other spelling given (``also``: its ``os.path.realpath`` form). The text AND its normal form
    are judged, and a ``..`` segment inside a UNC or device path is never allowed: the text checked is the text opened."""
    allowed = {h for h in (_remote_host(o) for o in (own,) + also) if h}
    climbs = ".." in target.replace("\\", "/").split("/")
    for text in (target, os.path.normpath(target)):
        host = _remote_host(text)
        if host is not None and (not host or host not in allowed or climbs):
            return False
    return True


def _own_spellings(path: str) -> tuple:
    """The spellings of a tree's own path that count for the same-host rule: the written form, plus its
    ``os.path.realpath`` form when the written form is local (a mapped drive resolves to ``\\\\server\\share``).
    A path already written as UNC or device is never resolved: that would touch its host."""
    return (path,) if _remote_host(path) is not None else (path, os.path.realpath(path))


def _inline_own_root(path: str) -> tuple[str | None, str | None]:
    """Inline copy of ``_project_paths.worktree_own_root`` (used when the helper lacks it). A gitdir that is a UNC
    or device path naming another host than the tree, holds neither ``/.git/worktrees/`` nor ``/.git/modules/``, or
    is cut off by the 4096-byte read cap is undecidable: ``(F, None)``, and nothing under it is touched."""

    def pointer(folder: str, first: str) -> str | None:
        raw = first[len("gitdir:"):].strip() if first.startswith("gitdir:") else ""
        if not raw or not _hop_allowed(raw, *_own_spellings(folder)):
            return None
        target = os.path.normpath(os.path.join(folder, raw)).replace("\\", "/")
        if not _hop_allowed(target, *_own_spellings(folder)) or not any(m in target.lower() for m in ("/.git/worktrees/", "/.git/modules/")):
            return None
        return target

    try:
        folder = os.path.abspath(path)
        while not os.path.exists(folder):
            parent = os.path.dirname(folder)
            if parent == folder:
                return None, None
            folder = parent
        while True:
            entry = os.path.join(folder, ".git")
            if os.path.isdir(entry):
                return folder, None
            if os.path.isfile(entry):
                try:
                    with open(entry, "rb") as fh:
                        data = fh.read(4096)
                    first = "" if len(data) >= 4096 and b"\n" not in data else data.split(b"\n", 1)[0].decode("utf-8").strip()
                except (OSError, ValueError, UnicodeError):
                    return None, None
                return folder, pointer(folder, first)
            parent = os.path.dirname(folder)
            if parent == folder:
                return None, None
            folder = parent
    except (OSError, ValueError):
        return None, None


def _own_root(path: str) -> tuple[str | None, str | None]:
    bound = _late("_pp_worktree_own_root")
    if bound is not None:
        try:
            return bound(path)
        except Exception:  # noqa: BLE001 - fall to the inline copy of the same walk
            pass
    return _inline_own_root(path)


def _main_candidate(path: str) -> str | None:
    """The Main checkout candidate of ``path``: main_checkout_root when bound and decidable; else the text before
    ``/.git/worktrees/`` in the gitdir of the nearest ``.git`` file; else the text before the last worktree
    segment; else None."""
    bound = _late("_pp_main_checkout_root")
    if bound is not None:
        try:
            found = bound(path)
            if found and _hop_allowed(found, *_own_spellings(path)):
                return found
        except Exception:  # noqa: BLE001
            pass
    gitdir = _own_root(path)[1]
    if gitdir and _hop_allowed(gitdir, *_own_spellings(path)):
        at = gitdir.replace("\\", "/").lower().find("/.git/worktrees/")
        if at > 0:
            return gitdir.replace("\\", "/")[:at]
    norm = str(path).replace("\\", "/")
    matches = list(_FALLBACK_WORKTREE_MARKER_RE.finditer(norm))
    if matches:
        return norm[:matches[-1].start()] or None
    return None


def _ancestors(path: str) -> list[str]:
    out: list[str] = []
    current = os.path.abspath(path)
    while True:
        out.append(current)
        parent = os.path.dirname(current)
        if parent == current:
            return out
        current = parent


def _project_dir_env() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR", "") or ""


def index_verdict(cwd: str) -> str:
    """``no-index``, ``index-other-tree`` or ``index-present`` for the Caller tree of ``cwd``."""
    project = _project_dir_env()
    search: list[str] = _ancestors(cwd)
    if project:
        search += _ancestors(project)
    for base in [cwd] + ([project] if project else []):
        candidate = _main_candidate(base)
        if candidate:
            search.append(candidate)
    if not any(_has_project_index(folder) for folder in dict.fromkeys(search)):
        return "no-index"
    root = _own_root(cwd or project)[0]
    tree_kind, main_checkout_root = _late("_pp_tree_kind"), _late("_pp_main_checkout_root")
    if root is not None and tree_kind is not None and main_checkout_root is not None:
        try:
            if tree_kind(root) == "linked-worktree":
                main = main_checkout_root(root)
                if (main and _hop_allowed(main, *_own_spellings(root)) and _norm_path(os.path.realpath(main)) != _norm_path(os.path.realpath(root))
                        and not _has_project_index(root) and _has_project_index(main)):
                    return "index-other-tree"
        except Exception:  # noqa: BLE001 - undecidable: the gate stays
            pass
    return "index-present"


# ---------------------------------------------------------------------------
# Server state (mirrors auto_improve_finish_install._mcp_server_state; a parity test pins the copy)
# ---------------------------------------------------------------------------
def _read_json_file(path: str):
    try:
        with open(path, "rb") as fh:
            return json.loads(fh.read().decode("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _servers_in(data) -> dict:
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    return dict(servers) if isinstance(servers, dict) else {}


def _starts_a_server(entry) -> bool:
    return isinstance(entry, dict) and any(isinstance(entry.get(k), str) and entry[k].strip() for k in ("command", "url"))


def _lists_server(data, key: str) -> bool:
    values = data.get(key) if isinstance(data, dict) else None
    return isinstance(values, list) and SERVER_NAME in values


def _config_home() -> str:
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return env if env else os.path.join(os.path.expanduser("~"), ".claude")


def _server_state_at(project: str) -> str:
    """``configured``, ``not-configured`` or ``disabled`` for the CodeGraph server as seen from ``project``."""
    project_path = Path(project)
    home = _config_home()
    user_files = sorted({os.path.join(os.path.expanduser("~"), ".claude.json"), os.path.join(home, ".claude.json")})
    try:
        resolved = str(project_path.resolve())
    except OSError:
        resolved = str(project_path)
    wanted = {_norm_path(project), _norm_path(resolved), project_path.as_posix()}
    found: list = []
    in_project = _servers_in(_read_json_file(os.path.join(project, ".mcp.json")))
    if SERVER_NAME in in_project:
        found.append(in_project[SERVER_NAME])
    layers: list = [
        _read_json_file(os.path.join(project, ".claude", "settings.json")),
        _read_json_file(os.path.join(project, ".claude", "settings.local.json")),
        _read_json_file(os.path.join(home, "settings.json")),
    ]
    for path in user_files:
        data = _read_json_file(path)
        if SERVER_NAME in _servers_in(data):
            found.append(_servers_in(data)[SERVER_NAME])
        projects = data.get("projects") if isinstance(data, dict) else None
        for key, entry in (projects.items() if isinstance(projects, dict) else []):
            if _norm_path(key) in wanted or str(key).replace("\\", "/") in wanted:
                layers.append(entry)
                if SERVER_NAME in _servers_in(entry):
                    found.append(_servers_in(entry)[SERVER_NAME])
    if not any(_starts_a_server(entry) for entry in found):
        return "not-configured"
    if any(_lists_server(data, "disabledMcpjsonServers") for data in layers):
        return "disabled"
    return "configured"


def server_verdict(cwd: str) -> str:
    """The server verdict over the Server project paths: CLAUDE_PROJECT_DIR and its Main checkout candidate (the
    payload cwd and its candidate when the variable is unset). ``configured`` if ANY path says so."""
    base = _project_dir_env() or cwd
    paths = [base]
    candidate = _main_candidate(base)
    if candidate and _norm_path(candidate) != _norm_path(base):
        paths.append(candidate)
    states = [_server_state_at(p) for p in paths]
    if "configured" in states:
        return "configured"
    if "disabled" in states:
        return "disabled"
    return "not-configured"


def availability_plan(session: Session, cwd: str) -> tuple[str, str, str | None]:
    """(server verdict, index verdict, availability.json body to write or None), cached in availability.json: the server
    once per session, the index once per distinct cwd. A stale cache can only fail open. READS ONLY: the write is the
    caller's effect (G-2)."""
    cache = session.read_json(AVAILABILITY_NAME)
    trees = cache.get("trees") if isinstance(cache.get("trees"), dict) else {}
    changed = False
    server = cache.get("server")
    if server not in ("configured", "not-configured", "disabled"):
        server = server_verdict(cwd)
        changed = True
    key = _norm_path(cwd)
    index = trees.get(key)
    if index not in ("no-index", "index-other-tree", "index-present"):
        index = index_verdict(cwd)
        trees[key] = index
        changed = True
    body = json.dumps({"server": server, "trees": trees, "checked_at": int(time.time())}) + "\n" if changed else None
    return server, index, body


def availability(session: Session, cwd: str) -> tuple[str, str]:
    """(server verdict, index verdict) with the cache written, as before the plan/apply split."""
    server, index, body = availability_plan(session, cwd)
    if body is not None:
        session.write(AVAILABILITY_NAME, body)
    return server, index


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------
def normalize(s: str) -> str:
    return s.replace("\\", "/").lower()


def has_bypass_segment(path_str: str) -> bool:
    # INV-2: the segment test reads the checkout-equivalent path (every
    # worktree segment removed) instead of the raw one.
    norm = normalize(_segment_test_path(path_str))
    return any(normalize(seg) in norm for seg in BYPASS_PATH_SEGMENTS)


def _project_roots() -> list[str]:
    """The normalized roots a path must sit under to count as inside the project.

    The project dir Claude Code reports, plus the main checkout when that dir is itself a
    worktree (``<main>/.claude/worktrees/<name>``): a sibling worktree is inside the same project.
    Empty when no project dir is known, which makes every path count as inside (strict, as before).
    """
    raw = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not raw:
        return []
    root = normalize(str(Path(raw).resolve())).rstrip("/")
    roots = [root]
    marker = "/.claude/worktrees/"
    if marker in root + "/":
        roots.append(root.split(marker, 1)[0])
    return roots


def is_outside_project(path_str: str) -> bool:
    """True only when a project root is known and the path is under none of its roots.

    Any failure to decide returns False, so the gate stays strict instead of silently widening.
    """
    try:
        roots = _project_roots()
        if not roots:
            return False
        target = normalize(str(Path(path_str).resolve())).rstrip("/")
        return not any(target == r or target.startswith(r + "/") for r in roots)
    except Exception:  # noqa: BLE001 - a hook must never crash a tool call; stay strict
        return False


def classify_path(path_str: str) -> str:
    """
    Classify a file-path-like string.

    Returns:
        'allowed' -- always allow (markdown, config, generated, deps, etc.)
        'source'  -- gated; requires prior CodeGraph call
        'unknown' -- ambiguous; gated under strict policy
    """
    if not path_str:
        return "allowed"

    if has_bypass_segment(path_str):
        return "allowed"

    name = Path(path_str).name
    if name in BYPASS_FILENAMES:
        return "allowed"

    suffix = Path(path_str).suffix.lower()
    if suffix in TRIVIAL_EXTENSIONS:
        return "allowed"
    if suffix in SOURCE_EXTENSIONS:
        return "source"

    # #612: the gate protects investigation of THIS project's code. A non-source file that lives
    # outside the project (a background command's output file in the temp folder) is not that.
    if is_outside_project(path_str):
        return "allowed"

    return "unknown"


def classify_pattern(pattern: str) -> str:
    """
    Classify a Grep regex pattern or Glob filename pattern.

    Returns:
        'allowed' -- pattern explicitly targets allowed file types
        'source'  -- pattern targets source files
        'unknown' -- ambiguous
    """
    if not pattern:
        return "unknown"

    lower = pattern.lower()

    # Glob-style file-extension targets.
    for ext in TRIVIAL_EXTENSIONS:
        if lower.endswith(ext) or f"*{ext}" in lower or f"{{{ext[1:]}" in lower:
            return "allowed"
    for ext in SOURCE_EXTENSIONS:
        if lower.endswith(ext) or f"*{ext}" in lower:
            return "source"

    # Generic patterns like `**/*` with no extension token -> ambiguous.
    return "unknown"


def extract_targets(tool_name: str, tool_input: dict) -> tuple[list[str], list[str]]:
    """
    Return (path_targets, pattern_targets) for the given tool payload.

    path_targets    -- file/dir paths that classify_path() handles.
    pattern_targets -- glob/regex patterns that classify_pattern() handles.
    """
    paths: list[str] = []
    patterns: list[str] = []

    if tool_name == "Read":
        for key in ("file_path", "filePath", "path"):
            v = tool_input.get(key)
            if isinstance(v, str) and v:
                paths.append(v)
                break

    elif tool_name == "Glob":
        v = tool_input.get("pattern")
        if isinstance(v, str) and v:
            patterns.append(v)
        v = tool_input.get("path")
        if isinstance(v, str) and v:
            paths.append(v)

    elif tool_name == "Grep":
        v = tool_input.get("path")
        if isinstance(v, str) and v:
            paths.append(v)
        v = tool_input.get("glob")
        if isinstance(v, str) and v:
            patterns.append(v)
        v = tool_input.get("type")
        # `type: "cs"` / `type: "ts"` etc. -> source-ish; convert to pattern.
        if isinstance(v, str) and v:
            patterns.append(f"*.{v.lstrip('.')}")

    return paths, patterns


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------
def call_fingerprint(tool_name: str, tool_input: dict) -> str:
    """SHA-256 of the tool name and the canonical JSON of the input: the identity of 'the same call'."""
    canonical = json.dumps(tool_input, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256((tool_name + canonical).encode("utf-8", "replace")).hexdigest()


class Plan:
    """One planned decision: the outcome and the state effects that would be applied, none of them applied yet."""

    __slots__ = ("session", "decision", "reason", "fingerprint", "step0_ok", "turn_marker", "target_class", "availability",
                 "availability_write", "ticket_op")

    def __init__(self, session: Session) -> None:
        self.session = session
        self.decision = "allow"
        self.reason = ""
        self.fingerprint = ""
        self.step0_ok = True
        self.turn_marker: bool | None = None  # None until step 2 read it
        self.target_class = "not-computed"
        self.availability: tuple[str, str] | None = None  # (server verdict, index verdict) once step 4 computed them
        self.availability_write: str | None = None  # availability.json body to write at apply
        self.ticket_op: tuple | None = None  # ("delete", name) or ("write", name, body)

    def done(self, decision: str, reason: str) -> "Plan":
        self.decision, self.reason = decision, reason
        return self


def _class_of(all_classes: list[str]) -> str:
    if any(c == "source" for c in all_classes):
        return "source"
    return "unknown" if any(c == "unknown" for c in all_classes) else "allowed"


def _plan(tool_name: str, tool_input: dict, payload: dict | None, gate: str | None, base: "Plan | None") -> Plan:
    """The decision as a pure function (it reads, it writes nothing). Order 0, 2, 1, 3-7 (G-1).

    ``gate`` is None for the Live plan (step 2 reads the Turn marker). For the Shadow decision it is the Transcript
    turn state, and ``base`` is the Live plan whose step-0 and availability verdicts are reused, never recomputed (S-1);
    the planned effects of a Shadow decision are never applied."""
    payload = payload if isinstance(payload, dict) else {}
    shadow = gate is not None and base is not None
    session = base.session if shadow else Session(payload)
    plan = Plan(session)

    # 0. an unusable Session folder: a guard that cannot record an escape must not block.
    plan.step0_ok = base.step0_ok if shadow else session.folder_usable()
    if not plan.step0_ok:
        return plan.done("allow", "fail-open:state-unwritable")

    # 2. the Turn marker of this session (the Transcript turn state in the Shadow decision; unknown counts as open).
    #    Checked before the paths are classified: both steps allow with no effect and no output.
    if shadow:
        if gate == "open":
            return plan.done("allow", "transcript-open")
        if gate.startswith("unknown"):
            return plan.done("allow", "transcript-unknown")
    else:
        plan.turn_marker = session.has_plain_file(MARKER_NAME)
        if plan.turn_marker:
            return plan.done("allow", "turn-marker-present")

    # 1. no target, or only non-source targets.
    paths, patterns = extract_targets(tool_name, tool_input)
    if not paths and not patterns:
        plan.target_class = "allowed"
        return plan.done("allow", "no-target")
    all_classes = [classify_path(p) for p in paths] + [classify_pattern(p) for p in patterns]
    plan.target_class = _class_of(all_classes)
    if all_classes and all(c == "allowed" for c in all_classes):
        return plan.done("allow", "non-source-target")

    # 3. a subagent (the payload carries a non-empty agent_id; verified against a live session).
    agent_id = payload.get("agent_id")
    if isinstance(agent_id, str) and agent_id:
        return plan.done("allow", "fail-open:subagent")

    if shadow and base.availability is not None:
        server, index = base.availability
    else:
        cwd = _payload_cwd(payload) if payload.get("cwd") else (_project_dir_env() or os.getcwd())
        server, index, body = availability_plan(session, cwd)
        if not shadow:
            plan.availability_write = body
    plan.availability = (server, index)

    # 4. no Project index, or an index that belongs to another working tree.
    if index in ("no-index", "index-other-tree"):
        return plan.done("allow", "fail-open:" + index)

    # 5. the server is not configured, or is disabled.
    if server in ("not-configured", "disabled"):
        return plan.done("allow", "fail-open:server-" + server)

    # 6. the identical retry of a call this session just had blocked (a read: the live apply consumes the ticket).
    plan.fingerprint = call_fingerprint(tool_name, tool_input)
    ticket = TICKET_PREFIX + plan.fingerprint
    if session.has_plain_file(ticket):
        if not shadow:
            plan.ticket_op = ("delete", ticket)
        return plan.done("allow", "retry-escape-used")

    # 7. issue the ticket (at apply) and block.
    if not shadow:
        body = json.dumps({"ts": int(time.time()), "tool": tool_name, "fingerprint": plan.fingerprint}) + "\n"
        plan.ticket_op = ("write", ticket, body)
    if any(c == "source" for c in all_classes):
        return plan.done("block", "source-target")
    # Only "unknown" left (Grep regex, generic Glob like `**/*`): ambiguous code investigation is gated too.
    return plan.done("block", "ambiguous-target")


def plan_live(tool_name: str, tool_input: dict, payload: dict | None = None) -> Plan:
    """The Live plan (G-2 step 1): the decision and its planned state effects, none applied."""
    return _plan(tool_name, tool_input, payload, None, None)


def apply_state(plan: Plan) -> tuple[str, str]:
    """The Live plan's STATE effects (G-2 step 3): the availability.json write, the ticket delete or write. Returns the final
    (decision, reason). A ticket already gone (an identical parallel call consumed it after the plan) keeps the planned
    allow; apply never re-decides. A ticket that cannot be written turns the planned block into
    fail-open:state-unwritable, as before the split. Output, notice flags and log records are main()'s effects."""
    session = plan.session
    if plan.availability_write is not None:
        session.write(AVAILABILITY_NAME, plan.availability_write)
    op = plan.ticket_op
    if op is not None and op[0] == "delete":
        try:
            os.remove(session.path(op[1]))
        except OSError:
            pass  # someone else consumed it: the planned allow stands
    elif op is not None and op[0] == "write":
        if not session.write(op[1], op[2]):
            return "allow", "fail-open:state-unwritable"
    return plan.decision, plan.reason


def evaluate(tool_name: str, tool_input: dict, payload: dict | None = None) -> tuple[str, str, Session, str]:
    """Return (decision, reason, session, fingerprint). decision: 'allow' | 'block'. Plan, then its state effects."""
    plan = plan_live(tool_name, tool_input, payload)
    decision, reason = apply_state(plan)
    return decision, reason, plan.session, plan.fingerprint


def decide(tool_name: str, tool_input: dict, payload: dict | None = None) -> tuple[str, str]:
    """Return (decision, reason). decision: 'allow' | 'block'."""
    decision, reason, _session, _fingerprint = evaluate(tool_name, tool_input, payload)
    return decision, reason


REASON_TEXT = {
    "source-target": "source-code target without a CodeGraph call this turn",
    "ambiguous-target": "ambiguous codebase investigation without a CodeGraph call this turn",
}


def cg_suggestion(tool_name: str, tool_input: dict) -> str:
    """Return a tailored suggestion. It names no individual tool: it says `mcp__codegraph__*`."""
    if tool_name == "Read":
        path = (
            tool_input.get("file_path")
            or tool_input.get("filePath")
            or tool_input.get("path")
            or ""
        )
        name = Path(path).stem if path else "Symbol"
        # Strip common C# suffixes for a cleaner search term.
        for suf in ("Service", "Controller", "Repository", "Configuration", "Entity"):
            if name.endswith(suf) and name != suf:
                name = name[: -len(suf)] or name
                break
        return (
            f"Before reading source files, ask CodeGraph with a mcp__codegraph__* tool\n"
            f"your session offers: a question about \"{name}\" (where it is defined, who calls it,\n"
            f"what it depends on) usually replaces opening the file."
        )

    if tool_name == "Grep":
        pattern = tool_input.get("pattern", "") or ""
        return (
            f"Before grepping source code, ask CodeGraph with a mcp__codegraph__* tool\n"
            f"your session offers: a question about \"{pattern[:80]}\" returns symbol hits with\n"
            f"file and line, and usually replaces Grep entirely."
        )

    if tool_name == "Glob":
        pattern = tool_input.get("pattern", "") or ""
        return (
            f"Before globbing for source files, ask CodeGraph with a mcp__codegraph__* tool\n"
            f"your session offers: a question about \"{pattern[:80]}\" lists the indexed files.\n"
            f"Glob is appropriate only for non-indexed files (markdown, config)."
        )

    return "Call a mcp__codegraph__* tool first."


def block(reason: str, tool_name: str, tool_input: dict) -> None:
    """Emit block message and exit 2."""
    bar = "=" * 62
    suggestion = cg_suggestion(tool_name, tool_input)
    message = [
        "",
        bar,
        "[codegraph-first-guard] BLOCKED -- CodeGraph-First Protocol",
        bar,
        f"Tool:     {tool_name}",
        f"Reason:   {REASON_TEXT.get(reason, reason)}",
        "",
    ]
    if _late("_pp_checkout_equivalent_path") is None:
        message.append(
            f"NOTE: _project_paths.py could not be imported (looked for "
            f"{_PROJECT_PATHS_EXPECTED_PATH}). Fallback mode is in effect: "
            "worktree source gets no bypass until this helper is restored."
        )
        message.append("")
    message.extend([
        "CodeGraph is the primary investigation tool. Every codebase",
        "question starts with a CodeGraph call -- only after that does",
        "the gate open for Read / Grep / Glob in the same turn.",
        "",
        suggestion,
        "",
        "If no mcp__codegraph__* tool is available to you in this session,",
        "repeat this exact call once; it will be allowed and logged.",
        "To remove the guard instead, run",
        "/auto-improve-codegraph-uninstall and start a new session.",
        "",
        "If the index is stale, run `codegraph sync` or `codegraph init -i`.",
        "/auto-improve-codegraph-install installs the add-on.",
        bar,
        "",
    ])
    try:
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    print("\n".join(message), file=sys.stderr)
    _late("log_event")(
        hook="codegraph-first-guard",
        event="block",
        file=None,
        details={"tool": tool_name, "reason": reason},
    )
    sys.exit(2)


def announce(reason: str, tool_name: str, session: Session, fingerprint: str) -> None:
    """The stderr line of a fail-open or a retry, and its log record (fail-open: once per session per reason)."""
    try:
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    log(f"allowed ({reason}): {NOTICES.get(reason, '')}")
    log_event = _late("log_event")
    if reason == "retry-escape-used":
        log_event(hook="codegraph-first-guard", event="retry-escape", file=None, session_id=session.key,
                  details={"tool": tool_name, "fingerprint": fingerprint[:12]})
        return
    short = reason.split(":", 1)[1]
    flag = LOGGED_PREFIX + short
    if reason == "fail-open:state-unwritable":
        # No writable state exists to rate-limit it: this reason logs on every call.
        log_event(hook="codegraph-first-guard", event="fail-open", file=None, session_id=session.key,
                  details={"reason": short, "tool": tool_name})
        return
    if session.has_plain_file(flag):
        return
    written = log_event(hook="codegraph-first-guard", event="fail-open", file=None, session_id=session.key,
                        details={"reason": short, "tool": tool_name})
    # The flag is created AFTER the record: a call whose record could not be written (log_event returned False)
    # leaves no flag, so the next call logs the reason. A helper that returns nothing is taken as written.
    if written is not False:
        session.create_once(flag)


# ---------------------------------------------------------------------------
# SHADOW SECTION (issue #261): the Shadow decision, computed beside the live one, logged, never enforced.
# main() runs it between the Live plan and the Live plan's effects (G-2). It is wrapped so that nothing it raises,
# SystemExit included, can change the exit code, stdout, stderr or the Session folder (S-3). Its only writes are the
# Transcript cursor (in the Session folder) and one Shadow record (in the project's measurement log).
# ---------------------------------------------------------------------------
CURSOR_NAME = "transcript-cursor.json"
SHADOW_LOG_NAME = "codegraph-shadow.jsonl"
SHADOW_LOG_CAP = 10 * 1024 * 1024  #: at this size one {"event":"log-full"} line is written and writing stops
SHADOW_LINE_MAX = 1024
SHADOW_TIME_BUDGET_S = 0.05  #: wall clock for the whole shadow section; checked between chunks and lines
TRANSCRIPT_READ_LIMIT = 2 * 1024 * 1024  #: bytes read per call; also the cold window; also the longest line parsed
TRANSCRIPT_CHUNK = 256 * 1024
CODEGRAPH_TOOL_PREFIX = "mcp__codegraph__"
_CODEGRAPH_TOOL_BYTES = CODEGRAPH_TOOL_PREFIX.encode("ascii")


def classify_entry(obj) -> str:
    """The Transcript entry class of one parsed transcript line: 'human-prompt' (a boundary), 'codegraph-use' or 'other'.
    The rule is the one the t1 live checks recorded for Claude Code 2.1.318. Fail-open bias: only an entry positively
    identified as a human prompt is a boundary."""
    if not isinstance(obj, dict):
        return "other"
    kind = obj.get("type")
    if kind == "assistant":
        if obj.get("isSidechain"):
            return "other"
        message = obj.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        for block in content if isinstance(content, list) else ():
            if isinstance(block, dict) and block.get("type") == "tool_use":
                name = block.get("name")
                if isinstance(name, str) and name.startswith(CODEGRAPH_TOOL_PREFIX):
                    return "codegraph-use"
        return "other"
    if kind != "user":
        return "other"
    if obj.get("isSidechain") or obj.get("isMeta") or obj.get("isCompactSummary"):
        return "other"
    if any(key in obj for key in ("origin", "toolUseResult", "sourceToolAssistantUUID")):
        return "other"
    message = obj.get("message")
    if not isinstance(message, dict) or message.get("role") != "user":
        return "other"
    source = obj.get("promptSource")
    if not isinstance(source, str) or source == "system":
        return "other"
    content = message.get("content")
    if isinstance(content, str):
        return "human-prompt"
    if isinstance(content, list):
        if any(isinstance(block, dict) and block.get("type") == "tool_result" for block in content):
            return "other"
        return "human-prompt"
    return "other"


def _classify_line(line: bytes) -> str:
    """'human-prompt', 'codegraph-use', 'other', or 'error' (a complete line that is not a JSON object). A line holding
    neither marker is not parsed, only checked for the braces of an object."""
    text = line.strip()
    if not text:
        return "other"
    if b'"user"' in text or _CODEGRAPH_TOOL_BYTES in text:
        try:
            return classify_entry(json.loads(text))
        except Exception:  # noqa: BLE001 - malformed JSON, bad bytes, nesting too deep
            return "error"
    if text[:1] != b"{" or text[-1:] != b"}":
        return "error"
    return "other"


def _identity(st: os.stat_result) -> str:
    if getattr(st, "st_ino", 0):
        return "%d:%d" % (getattr(st, "st_dev", 0), st.st_ino)
    return "ctime:%d" % getattr(st, "st_ctime_ns", 0)  # no inode: the creation time


def _valid_cursor(raw) -> dict | None:
    """The cursor when it has the contract's shape, else None (an unparseable or misshapen cursor reads as absent)."""
    if not isinstance(raw, dict):
        return None
    if not isinstance(raw.get("path"), str) or not isinstance(raw.get("identity"), str):
        return None
    scanned = raw.get("scanned_to")
    if isinstance(scanned, bool) or not isinstance(scanned, int) or scanned < 0:
        return None
    if not isinstance(raw.get("skipping"), bool) or not isinstance(raw.get("session_seen"), bool):
        return None
    if raw.get("turn") not in ("open", "closed", None):
        return None
    return raw


def _cursor_folder_ok(session: Session) -> bool:
    """The cursor is read and written only inside an EXISTING Session folder that is a real folder (never a link). The
    shadow never creates the folder: the reset hook does on the first prompt, and the live ticket write otherwise."""
    try:
        st = os.lstat(session.folder)
    except OSError:
        return False
    return stat.S_ISDIR(st.st_mode) and not _is_link_stat(st)


def read_transcript(payload: dict, session: Session, use_cursor: bool, deadline: float) -> dict:
    """The Transcript turn state of this call, by a true tail read.

    Returns {state, session_seen, bytes_read, skipped, cursor}. ``cursor`` is the dict to persist (or None). ``state`` is
    'open', 'closed' or 'unknown:<cause>'. A cold scan starts 2 MB before the end; at most 2 MB is read per call; only
    complete lines are parsed; a hit limit always answers window-exceeded, boundary found or not."""
    res: dict = {"state": "", "session_seen": False, "bytes_read": 0, "skipped": 0, "cursor": None}
    agent_id = payload.get("agent_id")
    if isinstance(agent_id, str) and agent_id:
        res["state"] = "unknown:subagent"  # a subagent's own entries are in another file; the parent's would read closed
        return res
    path = payload.get("transcript_path")
    if not isinstance(path, str) or not path:
        res["state"] = "unknown:no-transcript"
        return res
    try:
        st = os.stat(path)
    except (FileNotFoundError, NotADirectoryError):
        res["state"] = "unknown:no-transcript"
        return res
    except (OSError, ValueError):
        res["state"] = "unknown:unreadable"
        return res
    if not stat.S_ISREG(st.st_mode):  # a FIFO or a device would block open(); a folder is not a transcript
        res["state"] = "unknown:no-transcript"
        return res
    if time.monotonic() >= deadline:
        res["state"] = "unknown:time-exceeded"
        return res
    size, ident, norm = st.st_size, _identity(st), _norm_path(path)
    limit = TRANSCRIPT_READ_LIMIT

    cursor, rewritten = None, False
    if use_cursor:
        cursor = _valid_cursor(session.read_json(CURSOR_NAME))
        if cursor is not None and (cursor["path"] != norm or cursor["identity"] != ident or cursor["scanned_to"] > size):
            cursor, rewritten = None, True  # a different file, or shorter than scanned_to: a cold scan
    if cursor is not None:
        pos, skipping, turn, seen = cursor["scanned_to"], cursor["skipping"], cursor["turn"], cursor["session_seen"]
    else:
        pos = max(0, size - limit)
        skipping, turn, seen = False, ("closed" if pos == 0 else None), False

    try:
        fh = open(path, "rb")
    except OSError:
        res["state"] = "unknown:unreadable"
        return res
    errors, skipped, timed_out = 0, 0, False
    start_pos, read_to, budget, buf = pos, pos, limit, b""
    try:
        with fh:
            if cursor is None and pos > 0:
                fh.seek(pos - 1)  # mid-file: drop the first partial line unless the window starts on a line start
                if fh.read(1) != b"\n":
                    skipping = True
            fh.seek(pos)
            while read_to < size:
                if time.monotonic() >= deadline:
                    timed_out = True
                    break
                want = min(TRANSCRIPT_CHUNK, budget)
                if want <= 0:
                    break
                chunk = fh.read(want)
                if not chunk:
                    break
                read_to += len(chunk)
                budget -= len(chunk)
                res["bytes_read"] += len(chunk)
                buf += chunk
                if skipping:
                    cut = buf.find(b"\n")
                    if cut < 0:
                        pos += len(buf)
                        buf = b""
                        continue
                    pos += cut + 1
                    buf = buf[cut + 1:]
                    skipping = False
                begin = 0
                while True:
                    cut = buf.find(b"\n", begin)
                    if cut < 0:
                        break
                    kind = _classify_line(buf[begin:cut])
                    begin = cut + 1
                    if kind == "human-prompt":
                        turn = "closed"
                    elif kind == "codegraph-use":
                        turn, seen = "open", True
                    elif kind == "error":
                        errors += 1
                    if time.monotonic() >= deadline:
                        timed_out = True
                        break
                pos += begin
                buf = buf[begin:]
                if timed_out:
                    break
                if len(buf) >= limit:  # one line longer than the limit: skip it (counted), keep going past its newline
                    pos += len(buf)
                    buf = b""
                    skipping = True
                    skipped += 1
    except OSError:
        res["state"] = "unknown:unreadable"
        return res
    hit_limit = read_to < size and not timed_out
    res["skipped"], res["session_seen"] = skipped, seen
    if timed_out:
        res["state"] = "unknown:time-exceeded"  # the cursor is not written
        return res
    if rewritten:
        res["state"] = "unknown:rewritten"
    elif hit_limit or turn is None:
        res["state"] = "unknown:window-exceeded"
    elif errors:
        res["state"] = "unknown:parse-error"
    else:
        res["state"] = turn
    unchanged = cursor is not None and pos == start_pos and skipping == cursor["skipping"]
    if use_cursor and not unchanged:
        res["cursor"] = {"path": norm, "identity": ident, "scanned_to": pos, "skipping": skipping, "turn": turn,
                         "session_seen": seen, "updated_at": int(time.time())}
    return res


def _write_cursor(session: Session, cursor: dict) -> bool:
    """``transcript-cursor.<pid>.tmp`` in the Session folder, then ``os.replace``. Last replace wins."""
    final = session.path(CURSOR_NAME)
    temp = session.path("transcript-cursor.%d.tmp" % os.getpid())
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    try:
        try:
            fd = os.open(temp, flags, 0o600)
        except FileExistsError:  # a leftover of an earlier process that had this pid
            os.remove(temp)
            fd = os.open(temp, flags, 0o600)
    except OSError:
        return False
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write((json.dumps(cursor) + "\n").encode("utf-8"))
        os.replace(temp, final)
    except OSError:
        try:
            os.remove(temp)
        except OSError:
            pass
        return False
    return True


def _shadow_log_path() -> str | None:
    """``<CLAUDE_PROJECT_DIR>/.claude/logs/codegraph-shadow.jsonl`` from the environment variable ALONE (never the home
    folder). None when the variable is unset or ``<project>/.claude`` is absent: then no record is written."""
    project = _project_dir_env()
    if not project or not os.path.isdir(os.path.join(project, ".claude")):
        return None
    return os.path.join(project, ".claude", "logs", SHADOW_LOG_NAME)


def _append_shadow_line(path: str, record: dict) -> bool:
    """One ``os.write`` of one line (at most 1 KB) on a file opened for append, no lock and no wait. The size check
    precedes the write: at the cap one log-full line is written (unless the tail already holds one) and writing stops."""
    line = (json.dumps(record, separators=(",", ":")) + "\n").encode("utf-8")
    if len(line) > SHADOW_LINE_MAX:
        return False
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0), 0o600)
    except OSError:
        return False
    try:
        if os.fstat(fd).st_size >= SHADOW_LOG_CAP:
            with open(path, "rb") as fh:
                fh.seek(-256, os.SEEK_END)
                if b'"log-full"' in fh.read():
                    return False
            line = (json.dumps({"event": "log-full", "ts": int(time.time())}, separators=(",", ":")) + "\n").encode("utf-8")
        os.write(fd, line)
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


def _outcome(live: str, shadow: str) -> str:
    if live == shadow:
        return "agree"
    return "shadow-more-open" if shadow == "allow" else "shadow-more-closed"


def shadow_section(tool_name: str, tool_input: dict, payload: dict, live: Plan) -> None:
    """The shadow (G-2 step 2): read the transcript, recompute the decision with the Transcript turn state in place of the
    Turn marker, persist the cursor, append one Shadow record. Reads and writes nothing else. main() swallows whatever this
    raises."""
    started = time.monotonic()
    log_path = _shadow_log_path()
    if log_path is None:
        return  # nothing could be recorded: the section costs nothing
    deadline = started + SHADOW_TIME_BUDGET_S
    session = live.session
    use_cursor = live.step0_ok and _cursor_folder_ok(session)  # #259 step 0: never through a link, a not-a-folder or a foreign folder
    result = read_transcript(payload, session, use_cursor, deadline)
    shadow = _plan(tool_name, tool_input, payload, result["state"], live)
    if use_cursor and result["cursor"] is not None:
        _write_cursor(session, result["cursor"])
    prompt_id = payload.get("prompt_id")
    agent_id = payload.get("agent_id")
    record = {
        "ts": int(time.time()),
        "session": hashlib.sha256(session.key.encode("utf-8", "replace")).hexdigest()[:12],
        "agent": isinstance(agent_id, str) and bool(agent_id),
        "tool": tool_name,
        "target_class": shadow.target_class,
        "live_decision": live.decision,
        "live_reason": live.reason,
        "turn_marker": live.turn_marker,
        "transcript_turn": result["state"],
        "session_seen": bool(result["session_seen"]),
        "shadow_decision": shadow.decision,
        "shadow_reason": shadow.reason,
        "outcome": _outcome(live.decision, shadow.decision),
        "fp": live.fingerprint[:12] or "none",
        "prompt_key": (hashlib.sha256(prompt_id.encode("utf-8", "replace")).hexdigest()[:12]
                       if isinstance(prompt_id, str) and prompt_id else "none"),
        "shadow_ms": round((time.monotonic() - started) * 1000, 1),
        "bytes_read": result["bytes_read"],
        "skipped_long_line": result["skipped"],
    }
    _append_shadow_line(log_path, record)


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        log(f"failed to parse stdin payload: {e}")
        sys.exit(0)
    if not isinstance(payload, dict):
        payload = {}

    tool_name = payload.get("tool_name", "")
    if tool_name not in {"Read", "Grep", "Glob"}:
        sys.exit(0)

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        sys.exit(0)

    # G-2: (1) the Live plan, (2) the shadow, (3) the Live plan's effects.
    plan = plan_live(tool_name, tool_input, payload)
    try:
        shadow_section(tool_name, tool_input, payload, plan)
    except BaseException:  # noqa: BLE001 - S-3: nothing the shadow raises, SystemExit included, may change the live outcome
        pass
    decision, reason = apply_state(plan)
    session, fingerprint = plan.session, plan.fingerprint
    if decision == "allow":
        if reason.startswith("fail-open:") or reason == "retry-escape-used":
            announce(reason, tool_name, session, fingerprint)
        sys.exit(0)

    block(reason, tool_name, tool_input)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        log(f"internal error (failing open): {e}")
        sys.exit(0)
