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

Decision order (concept contract 2026-11-05-codegraph-guard-fail-open):
    0. the Session folder is unusable            -> allow (fail-open:state-unwritable; it logs on every call,
                                                    because there is no writable state to rate-limit it)
    1. no target / only non-source targets       -> allow
    2. the Turn marker exists                    -> allow
    3. the payload carries a non-empty agent_id  -> allow (fail-open:subagent)
    4. no Project index / index of another tree  -> allow (fail-open:no-index / fail-open:index-other-tree)
    5. the server is not configured / disabled   -> allow (fail-open:server-not-configured / server-disabled)
    6. a ticket matches the call's fingerprint   -> delete it, allow (retry-escape-used)
    7. otherwise write the ticket and block.

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

# Passive error logging (fail-soft import).
sys.path.insert(0, str(Path(__file__).parent))
try:
    from _error_log import log_event
except Exception:
    def log_event(*args, **kwargs):  # type: ignore[no-redef]
        return

# Project-local .claude first, global second (fail-soft import). This hook
# had no dependency on _project_paths before issue #222 -- has_bypass_segment
# now needs the checkout-equivalent path (INV-2).
try:
    import _project_paths as _pp
except Exception:  # pragma: no cover - hooks must never crash a tool call
    _pp = None

#: Round 3 task D: bound at import time via ``getattr`` (see concept-gate.py's
#: identical comment). A missing function is treated EXACTLY like ``_pp``
#: being ``None`` everywhere below, including the fallback-mode banner text.
_pp_checkout_equivalent_path = (
    getattr(_pp, "checkout_equivalent_path", None) if _pp is not None else None
)

#: Issue #259: the tree functions are bound the same way. A ``_project_paths.py`` from an earlier release lacks
#: them; then ``index-other-tree`` cannot fire (the tree kind is unknown) and the walk below is an inline copy.
#: ``tree_kind`` and ``main_checkout_root`` are bound ONLY from a helper that carries the hop refusal
#: (``_hop_allowed``): an older helper probes the host a hostile ``gitdir:`` line names before any caller-side check
#: could run, so with one of those ``index-other-tree`` cannot fire and the guard never calls the old functions.
_pp_worktree_own_root = getattr(_pp, "worktree_own_root", None) if _pp is not None else None
_pp_has_hop_refusal = _pp is not None and callable(getattr(_pp, "_hop_allowed", None))
_pp_tree_kind = getattr(_pp, "tree_kind", None) if _pp_has_hop_refusal else None
_pp_main_checkout_root = getattr(_pp, "main_checkout_root", None) if _pp_has_hop_refusal else None

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
    if _pp_checkout_equivalent_path is not None:
        return _pp_checkout_equivalent_path(path_str)
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
    if _pp_worktree_own_root is not None:
        try:
            return _pp_worktree_own_root(path)
        except Exception:  # noqa: BLE001 - fall to the inline copy of the same walk
            pass
    return _inline_own_root(path)


def _main_candidate(path: str) -> str | None:
    """The Main checkout candidate of ``path``: main_checkout_root when bound and decidable; else the text before
    ``/.git/worktrees/`` in the gitdir of the nearest ``.git`` file; else the text before the last worktree
    segment; else None."""
    if _pp_main_checkout_root is not None:
        try:
            found = _pp_main_checkout_root(path)
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
    if root is not None and _pp_tree_kind is not None and _pp_main_checkout_root is not None:
        try:
            if _pp_tree_kind(root) == "linked-worktree":
                main = _pp_main_checkout_root(root)
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


def availability(session: Session, cwd: str) -> tuple[str, str]:
    """(server verdict, index verdict), cached in availability.json: the server once per session, the index once
    per distinct cwd. A stale cache can only fail open."""
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
    if changed:
        session.write(AVAILABILITY_NAME, json.dumps({"server": server, "trees": trees, "checked_at": int(time.time())}) + "\n")
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


def evaluate(tool_name: str, tool_input: dict, payload: dict | None = None) -> tuple[str, str, Session, str]:
    """Return (decision, reason, session, fingerprint). decision: 'allow' | 'block'. See the module docstring."""
    payload = payload if isinstance(payload, dict) else {}
    session = Session(payload)
    fingerprint = ""

    # 0. an unusable Session folder: a guard that cannot record an escape must not block.
    if not session.folder_usable():
        return "allow", "fail-open:state-unwritable", session, fingerprint

    # 1. no target, or only non-source targets.
    paths, patterns = extract_targets(tool_name, tool_input)
    if not paths and not patterns:
        return "allow", "no-target", session, fingerprint
    all_classes = [classify_path(p) for p in paths] + [classify_pattern(p) for p in patterns]
    if all_classes and all(c == "allowed" for c in all_classes):
        return "allow", "non-source-target", session, fingerprint

    # 2. the Turn marker of this session.
    if session.has_plain_file(MARKER_NAME):
        return "allow", "turn-marker-present", session, fingerprint

    # 3. a subagent (the payload carries a non-empty agent_id; verified against a live session).
    agent_id = payload.get("agent_id")
    if isinstance(agent_id, str) and agent_id:
        return "allow", "fail-open:subagent", session, fingerprint

    cwd = _payload_cwd(payload) if payload.get("cwd") else (_project_dir_env() or os.getcwd())
    server, index = availability(session, cwd)

    # 4. no Project index, or an index that belongs to another working tree.
    if index in ("no-index", "index-other-tree"):
        return "allow", "fail-open:" + index, session, fingerprint

    # 5. the server is not configured, or is disabled.
    if server in ("not-configured", "disabled"):
        return "allow", "fail-open:server-" + server, session, fingerprint

    # 6. the identical retry of a call this session just had blocked.
    fingerprint = call_fingerprint(tool_name, tool_input)
    ticket = TICKET_PREFIX + fingerprint
    if session.has_plain_file(ticket):
        try:
            os.remove(session.path(ticket))
            return "allow", "retry-escape-used", session, fingerprint
        except OSError:
            pass  # someone else consumed it, or it cannot be removed: fall through to a fresh block

    # 7. issue the ticket and block.
    body = json.dumps({"ts": int(time.time()), "tool": tool_name, "fingerprint": fingerprint}) + "\n"
    if not session.write(ticket, body):
        return "allow", "fail-open:state-unwritable", session, fingerprint
    if any(c == "source" for c in all_classes):
        return "block", "source-target", session, fingerprint
    # Only "unknown" left (Grep regex, generic Glob like `**/*`): ambiguous code investigation is gated too.
    return "block", "ambiguous-target", session, fingerprint


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
    if _pp_checkout_equivalent_path is None:
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
    log_event(
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

    decision, reason, session, fingerprint = evaluate(tool_name, tool_input, payload)
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
