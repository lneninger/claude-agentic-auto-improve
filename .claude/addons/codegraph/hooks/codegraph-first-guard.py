#!/usr/bin/env python3
"""
codegraph-first-guard.py -- the CodeGraph-First Protocol's one hook file (PreToolUse guard and UserPromptSubmit row).

PreToolUse (no argument). Asks the agent to start an investigation with a CodeGraph tool: it blocks Read / Grep / Glob on
source-code paths until CodeGraph has been used in the current investigation turn. It lets reads through whenever
CodeGraph is provably unavailable, and the identical retry of a call it just blocked is allowed once (in the same prompt).
When its own session folder cannot be used it blocks instead (session-state-unusable), says why and how to fix it, and
offers no retry: planted or broken state must never open the gate.

The "turn" is read from the SESSION TRANSCRIPT, the log file Claude Code itself writes (issue #262, the cut-over). The turn
is the span after the last human prompt. Three things open it, each counted when the main session issues the call, whether
or not the call succeeds:
    * a tool use named mcp__codegraph__*                                      (route mcp)
    * a Bash tool use of a Counted ``codegraph`` command, strict form        (route cli)
    * an Agent (or older Task) tool use, a subagent dispatch                 (route agent, C-7)
A new human prompt closes it. A background task notification does not. Every transcript read that is not a clear open or
closed answer allows, with a logged reason (fail-open:transcript-<cause>).

Hook contract (Claude Code):
    stdin:  JSON with { session_id, cwd, tool_name, tool_input: {...}, transcript_path, prompt_id, agent_id (subagents only) }
    exit 0: allow (a `[codegraph-first-guard] allowed (<reason>)` line on stderr when it is a fail-open or a retry)
    exit 2: block (stderr shown to Claude)
    other:  error (hook fails open -- logs to stderr, allows the call)

UserPromptSubmit (the argument ``notice``). Two duties that the retired reset hook had, and nothing else: once per session it
creates the session folder and prunes old ones (``prune_session_folders``), then it runs the Connection notice
(``notice_section``): one JSON object when the CodeGraph server is configured and its index exists but no
``codegraph serve --mcp`` process belongs to this session. It always exits 0, never blocks a prompt, swallows whatever it
raises (SystemExit included), writes no bytecode and deletes no ticket.

Session folder, under the Per-user session parent (issue #271): the folder auto-improve-codegraph in %LOCALAPPDATA% on Windows,
in $XDG_CACHE_HOME (else ~/.cache) on POSIX, mode 0700. The system temp folder is never read, written or pruned:
    <Per-user session parent>/auto-improve-codegraph-<session key>/
        ticket-<64 hex>      a Retry escape ticket {ts, tool, fingerprint, prompt_key}, issued at a block, consumed by the
                             identical retry in the same prompt
        availability.json    the cached server and index verdicts
        logged-<reason>      at most one log record per session per fail-open reason (and for cli-fallback)
        pruned               set on the first prompt of a session (the prompt row prunes once)
        transcript-cursor.json   the Transcript cursor; transcript-cursor.<pid>.tmp is its temp file
    (turn.json and mcp-seen belong to the retired tracker: nothing writes them any more; the pruner still knows both names
    so a folder an older release left behind is removed.)

Decision order (concept contracts 2026-11-05-codegraph-guard-fail-open, 2026-11-05-codegraph-hooks-redesign (G-1),
2026-11-06-session-folder-owner-and-tool-named and 2026-11-09-codegraph-hooks-cutover (C-1)):
    0. resolve the Session state                 -> unusable: the Stateless session (it reads and writes nothing)
    1. the Transcript turn state                 -> open: allow transcript-open (silent). Read only when step 0 found the
                                                    Session folder usable; an unusable folder reads as closed.
    2. no target / only non-source targets       -> allow (silent, whatever the state)
    3. the payload carries a non-empty agent_id  -> allow fail-open:subagent
    3a. any other unknown:<cause> state          -> allow fail-open:transcript-<cause>
    4-5. no Project index / index of another tree (fail-open:no-index / fail-open:index-other-tree);
         the server is not configured / disabled  (fail-open:server-not-configured / server-disabled)
    6. a ticket matches the call's fingerprint AND the call's prompt_key -> delete it, allow (retry-escape-used)
    7. otherwise write the ticket and block; the Session state unusable blocks here (session-state-unusable) without a
       ticket; when the write fails, resolve the Session state again: unusable -> session-state-unusable, still usable
       -> retry-ticket-unwritten. It never allows.

main() runs the decision in two parts (C-2): the Live plan (a pure function: it reads, it writes nothing but the Session
folder's lazy creation), then its effects in this order: availability.json, the ticket, the cursor, the cli-fallback record,
the notice flags and log records, one Measurement record in <CLAUDE_PROJECT_DIR>/.claude/logs/codegraph-shadow.jsonl, then
stderr and the exit code. Every effect after the ticket is wrapped: whatever it raises, BaseException included, changes
neither the exit code nor stderr.

There is no kill switch: no environment variable turns the guard off.
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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Issue #261, G-1: the two helpers are imported on first USE (classification, the fallback banner, a log record), not at
# module load, so a call an open turn allows never pays for them. Every module-level name below keeps its meaning and
# stays patchable (``mock.patch.object(guard, "_pp", None)``): the names resolve through the module ``__getattr__`` on
# first read, a value set before that read is never overwritten, and this file reads them through ``_late``.
#:   log_event                        ``_error_log.log_event`` (passive error logging), or a no-op when it cannot be imported.
#:   _pp                              ``_project_paths`` (project-local .claude first, global second), or None. This hook had
#:                                    no dependency on it before issue #222 (has_bypass_segment needs the checkout-equivalent path).
#:   _pp_checkout_equivalent_path     bound with ``getattr`` (concept-gate.py's identical comment): a missing function is treated
#:                                    EXACTLY like ``_pp`` being None, the fallback-mode banner text included.
#:   _pp_worktree_own_root            issue #259: bound the same way; a helper from an earlier release lacks it, the inline walk is used.
#:   _pp_tree_kind, _pp_main_checkout_root
#:                                    bound ONLY on the Hop proof (issue #271): the helper declares ``TREE_HOP_REFUSAL = True``, or
#:                                    it has the 0.15.2 shape (``_hop_allowed`` and ``worktree_own_root`` both callable). An older
#:                                    helper probes the host a hostile ``gitdir:`` line names before any caller-side check could
#:                                    run, so with one of those ``index-other-tree`` cannot fire and the old functions are never
#:                                    called. The same expression gates the bridge (``_claude_paths.TREE_HOP_REFUSAL``) and the installer.
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
    scope.setdefault("_pp_has_hop_refusal", pp is not None and (
        getattr(pp, "TREE_HOP_REFUSAL", False) is True
        or (callable(getattr(pp, "_hop_allowed", None)) and callable(getattr(pp, "worktree_own_root", None)))))
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
AVAILABILITY_NAME = "availability.json"
TICKET_PREFIX = "ticket-"
LOGGED_PREFIX = "logged-"
SERVER_NAME = "codegraph"
CLI_FALLBACK_FLAG = LOGGED_PREFIX + "cli-fallback"
PRUNED_FLAG = "pruned"
#: The only file names a session folder may hold (the atomic-write ``.tmp-<16 hex>`` siblings included); a folder with any other
#: entry is kept whole. ``turn.json`` and ``mcp-seen`` are the retired tracker's names: nothing writes them any more, but a folder an
#: older release left behind must still prune. The Transcript cursor ``transcript-cursor.json`` and its temp file are known names.
KNOWN_FILE_RE = re.compile(
    r"turn\.json|mcp-seen|availability\.json|pruned|logged-[a-z0-9-]+|ticket-[0-9a-f]{64}|\.tmp-[0-9a-f]{16}"
    r"|transcript-cursor\.json|transcript-cursor\.[0-9]+\.tmp")
#: A session folder younger than this (by its newest file) is never pruned.
MIN_AGE_SECONDS = 7 * 24 * 60 * 60
#: The Counted commands: the subcommands whose command line mirrors a CodeGraph MCP tool (moved verbatim from the retired tracker).
COUNTED_COMMANDS = frozenset({"query", "explore", "context", "node", "callers", "callees", "impact", "files"})
_CONTROL_RE = re.compile(r"[;&|<>`\n\r]|\$\(")
_SUMMARY_UNSAFE_RE = re.compile(r"[^A-Za-z0-9_. -]+")
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
    "retry-escape-used": (
        "the identical call was blocked just before; it is allowed once and logged as a retry-escape."),
}


def log(msg: str) -> None:
    """Log to stderr so Claude sees the diagnostic line."""
    try:
        sys.stderr.reconfigure(errors="backslashreplace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    try:
        print(f"[codegraph-first-guard] {msg}", file=sys.stderr)
    except Exception:  # noqa: BLE001 - a diagnostic line must never change the verdict
        pass


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


# ---------------------------------------------------------------------------
# Per-user session parent (issue #271). This is its one active inline copy since the cut-over (C-6); the disabled tracker and
# reset hooks keep their last released copies, and a parity test pins them to this one: an add-on copies a helper only when
# the project lacks it, so an old helper must not be a dependency.
# ---------------------------------------------------------------------------
PARENT_NAME = "auto-improve-codegraph"
#: The closed set of Parent problems. The Session folder inside a usable parent adds ``session-<link / not-a-folder /
#: foreign-owner / unwritable / check-failed>``.
PARENT_PROBLEMS = ("unset", "not-absolute", "remote", "cannot-create", "link", "not-a-folder", "foreign-owner",
                   "open-mode", "unwritable", "check-failed")
_LOCAL_DEVICE_HOST_RE = re.compile(r"\?[a-z]:")


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
    """The Session folder of one payload and the small state kept in it.

    ``resolve()`` computes the Session state verdict (the Per-user session parent, then the Session folder). While
    ``problem`` is set the object is the Stateless session: every read answers "absent" and every write answers
    False WITHOUT any filesystem call, so nothing is created inside or through an unusable folder. A Session that
    has not been resolved yet is stateless too."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.key = session_key(payload)
        self.parent = ""
        self.folder = ""
        self.problem: str | None = "check-failed"
        self.detail = "the session state was not resolved"

    def resolve(self) -> None:
        """Resolve the Session state verdict again, from the environment of this call."""
        self.parent, self.problem, self.detail = resolve_session_parent()
        self.folder = ""
        if self.problem is None:
            self.folder = os.path.join(self.parent, SESSION_PREFIX + self.key)
            self.problem, self.detail = session_folder_problem(self.folder)

    def ensure_folder(self) -> bool:
        """Create the folder when absent and re-check it. False when it cannot be used."""
        if self.problem is not None:
            return False
        try:
            os.mkdir(self.folder, 0o700)
        except FileExistsError:
            pass
        except Exception:  # noqa: BLE001
            return False
        return session_folder_problem(self.folder)[0] is None

    def path(self, name: str) -> str:
        return os.path.join(self.folder, name)

    def has_plain_file(self, name: str) -> bool:
        if self.problem is not None:
            return False
        try:
            st = os.lstat(self.path(name))
        except (OSError, ValueError):
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


def _server_entries_at(project: str) -> tuple[list, list]:
    """(the CodeGraph server entries found for ``project``, the settings layers read), in precedence order."""
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
    return found, layers


def _server_state_at(project: str) -> str:
    """``configured``, ``not-configured`` or ``disabled`` for the CodeGraph server as seen from ``project``."""
    found, layers = _server_entries_at(project)
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


def server_starts_process(path: str) -> bool:
    """True when the selected CodeGraph server entry of the first Server project path that ``server_verdict`` judges
    ``configured`` has a non-empty ``command`` (a ``url``-only server starts no process for the session)."""
    base = _project_dir_env() or path
    paths = [base]
    candidate = _main_candidate(base)
    if candidate and _norm_path(candidate) != _norm_path(base):
        paths.append(candidate)
    for p in paths:
        if _server_state_at(p) != "configured":
            continue
        found, _layers = _server_entries_at(p)
        for entry in found:
            if _starts_a_server(entry):
                command = entry.get("command")
                return isinstance(command, str) and bool(command.strip())
        return False
    return False


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

    __slots__ = ("session", "decision", "reason", "fingerprint", "step0_ok", "target_class", "availability",
                 "availability_write", "ticket_op", "prompt_key", "transcript")

    def __init__(self, session: Session) -> None:
        self.session = session
        self.decision = "allow"
        self.reason = ""
        self.fingerprint = ""
        self.step0_ok = True
        self.target_class = "not-computed"
        self.availability: tuple[str, str] | None = None  # (server verdict, index verdict) once step 4 computed them
        self.availability_write: str | None = None  # availability.json body to write at apply
        self.ticket_op: tuple | None = None  # ("delete", name) or ("write", name, body)
        self.prompt_key = "none"  # 12 hex of the SHA-256 of the payload's prompt_id; "none" when the host sends none
        self.transcript: dict = _empty_read("closed")  # what step 1 read (the Transcript turn state and its facts)

    def done(self, decision: str, reason: str) -> "Plan":
        self.decision, self.reason = decision, reason
        return self


def _class_of(all_classes: list[str]) -> str:
    if any(c == "source" for c in all_classes):
        return "source"
    return "unknown" if any(c == "unknown" for c in all_classes) else "allowed"


def _prompt_key(payload: dict) -> str:
    """The prompt a call belongs to: 12 hex characters of the SHA-256 of ``prompt_id``, or ``none`` when there is none (Q6: a ticket
    keyed ``none`` may match)."""
    prompt_id = payload.get("prompt_id")
    if isinstance(prompt_id, str) and prompt_id:
        return hashlib.sha256(prompt_id.encode("utf-8", "replace")).hexdigest()[:12]
    return "none"


def _read_turn(payload: dict, session: Session, usable: bool) -> dict:
    """Step 1's read. An unusable Session folder skips it and the state reads ``closed`` (C-1: no transcript is read from an
    unusable folder, exactly as the marker was never read from one). An exception inside the read is the cause ``error``."""
    if not usable:
        return _empty_read("closed")
    started = time.perf_counter()
    try:
        result = read_transcript(payload, session, True, started + TRANSCRIPT_TIME_BUDGET_S)
    except Exception:  # noqa: BLE001 - anything unexpected is an unknown state, which allows (fail open)
        result = _empty_read("unknown:error")
    result["ms"] = round((time.perf_counter() - started) * 1000, 1)
    return result


def _ticket_matches(session: Session, name: str, prompt_key: str) -> bool:
    """A Retry escape ticket matches only when it is a plain file, its JSON parses and its ``prompt_key`` equals the call's. An old
    ticket (no key), an unparseable one or one from another prompt reads as absent (step 7 overwrites it)."""
    body = session.read_json(name)
    return isinstance(body.get("prompt_key"), str) and body["prompt_key"] == prompt_key


def _plan(tool_name: str, tool_input: dict, payload: dict | None) -> Plan:
    """The decision as a pure function (it reads, it writes nothing but the Session folder's lazy creation). Order 0-7 (C-1)."""
    payload = payload if isinstance(payload, dict) else {}
    session = Session(payload)
    plan = Plan(session)

    # 0. the Session state verdict (the Per-user session parent, then the Session folder). Unusable: the Stateless
    #    session reads and writes nothing, the proof steps still run, and the call is blocked at step 7 (fail closed:
    #    planted or broken state must never open the gate).
    session.resolve()
    plan.step0_ok = session.problem is None
    plan.prompt_key = _prompt_key(payload)

    # 1. the Transcript turn state. It is read before the paths are classified (C-3); ``open`` allows with no effect and no output.
    plan.transcript = _read_turn(payload, session, plan.step0_ok)
    state = plan.transcript["state"]
    if state == "open":
        return plan.done("allow", "transcript-open")

    # 2. no target, or only non-source targets.
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

    # 3a. any other unknown state: fail open with the cause (after classification, so an allowlisted read prints nothing).
    if state.startswith("unknown:"):
        return plan.done("allow", "fail-open:transcript-" + state.split(":", 1)[1])

    cwd = _payload_cwd(payload) if payload.get("cwd") else (_project_dir_env() or os.getcwd())
    server, index, body = availability_plan(session, cwd)
    plan.availability_write = body
    plan.availability = (server, index)

    # 4. no Project index, or an index that belongs to another working tree.
    if index in ("no-index", "index-other-tree"):
        return plan.done("allow", "fail-open:" + index)

    # 5. the server is not configured, or is disabled.
    if server in ("not-configured", "disabled"):
        return plan.done("allow", "fail-open:server-" + server)

    # 6. the identical retry of a call this session just had blocked IN THIS PROMPT (the live apply consumes the ticket).
    plan.fingerprint = call_fingerprint(tool_name, tool_input)
    ticket = TICKET_PREFIX + plan.fingerprint
    if _ticket_matches(session, ticket, plan.prompt_key):
        plan.ticket_op = ("delete", ticket)
        return plan.done("allow", "retry-escape-used")

    # 7. issue the ticket (at apply) and block. Never an allow: an unusable Session state blocks without a ticket, and
    #    a ticket write that fails at apply resolves the verdict again (apply_state).
    if plan.step0_ok:
        body = json.dumps({"ts": int(time.time()), "tool": tool_name, "fingerprint": plan.fingerprint,
                           "prompt_key": plan.prompt_key}) + "\n"
        plan.ticket_op = ("write", ticket, body)
    if not plan.step0_ok:
        return plan.done("block", "session-state-unusable")
    if any(c == "source" for c in all_classes):
        return plan.done("block", "source-target")
    # Only "unknown" left (Grep regex, generic Glob like `**/*`): ambiguous code investigation is gated too.
    return plan.done("block", "ambiguous-target")


def plan_live(tool_name: str, tool_input: dict, payload: dict | None = None) -> Plan:
    """The Live plan (C-2 step 1): the decision and its planned state effects, none applied."""
    return _plan(tool_name, tool_input, payload)


def apply_state(plan: Plan) -> tuple[str, str]:
    """The Live plan's STATE effects (C-2): the availability.json write, the ticket delete or write. Returns the final
    (decision, reason). A ticket already gone (an identical parallel call consumed it after the plan) keeps the planned
    allow; apply never re-decides. A ticket that cannot be written resolves the Session state again (the
    folder may have changed since the plan, for example it became a link): unusable -> block session-state-unusable,
    still usable -> block retry-ticket-unwritten. It never allows. Output, the cursor, notice flags and log records are
    main()'s effects."""
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
            session.resolve()
            if session.problem is not None:
                return "block", "session-state-unusable"
            return "block", "retry-ticket-unwritten"
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
    "session-state-unusable": "the guard's per-user session folder cannot be used (session-state-unusable)",
    "retry-ticket-unwritten": "the retry of this call could not be recorded (retry-ticket-unwritten)",
}

#: Problem token -> the problem in plain words. ``{where}`` is the parent or the Session folder; a Parent base problem
#: names the setting instead.
PROBLEM_WORDS = {
    "unset": "the setting is empty or missing",
    "not-absolute": "the setting is not an absolute path",
    "remote": "the setting points at a network share, not at this computer",
    "cannot-create": "the folder cannot be created",
    "link": "the folder is a link",
    "not-a-folder": "the path is a file, not a folder",
    "foreign-owner": "the folder belongs to another user",
    "open-mode": "the folder is open to other users",
    "unwritable": "the folder is not writable",
    "check-failed": "the folder could not be checked",
    "session-link": "the session folder is a link",
    "session-not-a-folder": "the session folder path is a file, not a folder",
    "session-foreign-owner": "the session folder belongs to another user",
    "session-unwritable": "the session folder is not writable",
    "session-check-failed": "the session folder could not be checked",
}


def problem_fix(problem: str, where: str) -> str:
    """What the user does about ``problem`` (I-7): the fix that matches the problem, never a shell route to the source."""
    setting = "LOCALAPPDATA" if os.name == "nt" else "XDG_CACHE_HOME (or HOME)"
    if problem in ("unset", "not-absolute", "remote"):
        return f"set {setting} to an absolute, local folder you own, then start a new session."
    if problem == "cannot-create":
        return f"make sure the folder {os.path.dirname(where)} exists and you can write in it, then start a new session."
    if problem in ("link", "session-link"):
        return f"remove the link at {where}, then start a new session."
    if problem in ("not-a-folder", "session-not-a-folder"):
        return f"remove the file at {where} (it is not a folder), then start a new session."
    if problem in ("foreign-owner", "session-foreign-owner"):
        return f"remove {where} (it belongs to another user) or point {setting} at a folder you own, then start a new session."
    if problem == "open-mode":
        return f"run `chmod 700 {where}`, then start a new session."
    if problem in ("unwritable", "session-unwritable"):
        return f"make {where} writable for your user, then start a new session."
    return "fix the cause named above, then start a new session."


def unusable_lines(session: Session) -> list:
    """The body of a ``session-state-unusable`` banner (I-7): the path, the problem in plain words with its token, the
    fix, and the uninstall way out. It offers no retry and names no individual tool."""
    where = session.folder if session.problem.startswith("session-") else session.parent
    words = PROBLEM_WORDS.get(session.problem, "the folder cannot be used")
    detail = f": {session.detail}" if session.detail else ""
    return [
        f"Problem:  {where} -- {words} ({session.problem}){detail}",
        f"Fix:      {problem_fix(session.problem, where)}",
        "",
        "Until this is fixed the guard cannot record a CodeGraph call, so a CodeGraph call does not open the gate and",
        "a repeat of this call is blocked the same way: this block offers no retry.",
        "To remove the guard instead, run",
        "/auto-improve-codegraph-uninstall and start a new session.",
    ]


COPYABLE_TERM_MAX = 80
_TERM_UNSAFE_RE = re.compile(r"[^A-Za-z0-9_. -]+")


def neutral_term(text: str) -> str:
    """The Copyable command's term: keep ``[A-Za-z0-9_.-]`` and spaces, fold every other run to one space, strip leading
    ``-`` and ``.`` (so it never reads as an option), trim to 80, fall back to ``Symbol``."""
    folded = _TERM_UNSAFE_RE.sub(" ", text if isinstance(text, str) else "")
    folded = folded.lstrip("-. ")[:COPYABLE_TERM_MAX].strip()
    return folded or "Symbol"


def _term_of(tool_name: str, tool_input: dict) -> str:
    """The name or pattern the suggestion is about, before neutralising."""
    def text_of(key: str) -> str:
        value = tool_input.get(key) if isinstance(tool_input, dict) else None
        return value if isinstance(value, str) else ""  # only a string can be named in the message

    if tool_name == "Read":
        path = text_of("file_path") or text_of("filePath") or text_of("path")
        name = Path(path).stem if path else "Symbol"
        # Strip common C# suffixes for a cleaner search term.
        for suf in ("Service", "Controller", "Repository", "Configuration", "Entity"):
            if name.endswith(suf) and name != suf:
                name = name[: -len(suf)] or name
                break
        return name
    return text_of("pattern") if tool_name in ("Grep", "Glob") else ""


def cg_suggestion(tool_name: str, tool_input: dict) -> str:
    """Return a tailored suggestion. It names no individual tool: it says `mcp__codegraph__*`."""
    term = neutral_term(_term_of(tool_name, tool_input))
    if tool_name == "Read":
        return (
            f"Before reading source files, ask CodeGraph with a mcp__codegraph__* tool\n"
            f"your session offers: a question about \"{term}\" (where it is defined, who calls it,\n"
            f"what it depends on) usually replaces opening the file."
        )

    if tool_name == "Grep":
        return (
            f"Before grepping source code, ask CodeGraph with a mcp__codegraph__* tool\n"
            f"your session offers: a question about \"{term}\" returns symbol hits with\n"
            f"file and line, and usually replaces Grep entirely."
        )

    if tool_name == "Glob":
        return (
            f"Before globbing for source files, ask CodeGraph with a mcp__codegraph__* tool\n"
            f"your session offers: a question about \"{term}\" lists the indexed files.\n"
            f"Glob is appropriate only for non-indexed files (markdown, config)."
        )

    return "Call a mcp__codegraph__* tool first."


def copyable_command(tool_name: str, tool_input: dict) -> str:
    """The command-line equivalent the banner offers: ``codegraph explore "<term>"``."""
    return f'codegraph explore "{neutral_term(_term_of(tool_name, tool_input))}"'


def block(reason: str, tool_name: str, tool_input: dict, session: Session | None = None) -> None:
    """Emit block message and exit 2. The retry lines are chosen by reason (I-7c): ``source-target`` and
    ``ambiguous-target`` keep the two-line retry escape, ``session-state-unusable`` has none, and
    ``retry-ticket-unwritten`` says the guard tries again to record the retry. The uninstall lines stay for every reason."""
    def build() -> tuple:
        bar = "=" * 62
        suggestion = cg_suggestion(tool_name, tool_input)
        details: dict = {"tool": tool_name, "reason": reason}
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
        if reason == "session-state-unusable" and session is not None and session.problem is not None:
            details.update({"problem": session.problem, "parent": session.parent})
            message.extend(unusable_lines(session))
        else:
            if reason == "retry-ticket-unwritten" and session is not None:
                details["folder"] = session.folder
                message.extend([
                    f"The guard could not record the retry of this call in its session folder {session.folder}.",
                    "The usual cause is a passing lock (an antivirus or an indexer scanning the folder) or a full disk.",
                    "",
                ])
            message.extend([
                "CodeGraph is the primary investigation tool. Every codebase",
                "question starts with a CodeGraph call -- only after that does",
                "the gate open for Read / Grep / Glob in the same turn.",
                "",
                suggestion,
                "",
                "Two routes open the gate for the rest of this turn: a mcp__codegraph__*",
                "tool, or a CodeGraph command in the Bash tool. When the MCP tools are gone",
                "(the connection dropped), run this one command on its own, no pipe or `&&`:",
                "",
                f"    {copyable_command(tool_name, tool_input)}",
                "",
                "Also accepted, one at a time: query, context, node, callers, callees, impact, files.",
                "In a worktree the command line reads the main checkout's index, unless one was",
                "built in that worktree.",
                "",
            ])
            if reason == "retry-ticket-unwritten":
                message.extend([
                    "Repeat this exact call: the guard tries again to record the retry. When that works the block says",
                    "`source-target` or `ambiguous-target`, and the identical call after it is allowed.",
                    "Or ask CodeGraph with a mcp__codegraph__* tool, which opens the gate, or remove the guard:",
                    "run /auto-improve-codegraph-uninstall and start a new session.",
                ])
            else:
                message.extend([
                    "If no mcp__codegraph__* tool is available to you in this session,",
                    "repeat this exact call once; it will be allowed and logged.",
                    "To remove the guard instead, run",
                    "/auto-improve-codegraph-uninstall and start a new session.",
                ])
            message.extend([
                "",
                "If the index is stale, run `codegraph sync` or `codegraph init -i`.",
                "/auto-improve-codegraph-install installs the add-on.",
            ])
        message.extend([bar, ""])
        return message, details

    try:
        try:
            message, details = build()
        except Exception:  # noqa: BLE001 - a field of an odd type must still reach the exit-2 block below
            message = ["[codegraph-first-guard] BLOCKED -- CodeGraph-First Protocol", "Call a mcp__codegraph__* tool first."]
            details = {"tool": str(tool_name), "reason": str(reason)}
        try:
            # backslashreplace: a lone surrogate in the text must print as an escape, never raise and end the hook in the allow
            sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
        try:
            print("\n".join(message), file=sys.stderr)
        except Exception:  # noqa: BLE001 - the verdict is the exit code, not the text
            pass
        try:
            # the log line is written as UTF-8: a lone surrogate (from an environment value) would drop the whole record
            safe = {k: (v.encode("utf-8", "backslashreplace").decode("utf-8") if isinstance(v, str) else v)
                    for k, v in details.items()}
            _late("log_event")(
                hook="codegraph-first-guard",
                event="block",
                file=None,
                details=safe,
            )
        except Exception:  # noqa: BLE001
            pass
    finally:
        sys.exit(2)


def announce_record(reason: str, tool_name: str, session: Session, fingerprint: str) -> None:
    """The log record of a fail-open or a retry (fail-open: once per session per reason, the flag created after the record landed).

    While the Session state is unusable (the Stateless session) NOTHING is logged: no state exists to rate-limit a record, and no
    flag is created inside or through the unusable folder."""
    if session.problem is not None:
        return
    log_event = _late("log_event")
    if reason == "retry-escape-used":
        log_event(hook="codegraph-first-guard", event="retry-escape", file=None, session_id=session.key,
                  details={"tool": tool_name, "fingerprint": fingerprint[:12]})
        return
    short = reason.split(":", 1)[1]
    flag = LOGGED_PREFIX + short
    if session.has_plain_file(flag):
        return
    written = log_event(hook="codegraph-first-guard", event="fail-open", file=None, session_id=session.key,
                        details={"reason": short, "tool": tool_name})
    # The flag is created AFTER the record: a call whose record could not be written (log_event returned False)
    # leaves no flag, so the next call logs the reason. A helper that returns nothing is taken as written.
    if written is not False:
        session.create_once(flag)


def announce_line(reason: str) -> None:
    """The one stderr line of a fail-open or a retry. It prints on every such call, whatever the Session state."""
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    log(f"allowed ({reason}): {NOTICES.get(reason, '')}")


def announce(reason: str, tool_name: str, session: Session, fingerprint: str) -> None:
    """The log record, then the stderr line (the pair main() splits so that the line is the last effect). A record that
    raises is swallowed: it must never change the line."""
    try:
        announce_record(reason, tool_name, session, fingerprint)
    except BaseException:  # noqa: BLE001
        pass
    announce_line(reason)


# ---------------------------------------------------------------------------
# TRANSCRIPT TURN STATE (issues #261 and #262). The Transcript turn state is the live input of step 1 since the cut-over: a true
# tail read of the session transcript, a cursor kept in the Session folder, and one Measurement record per guarded call
# in the project's measurement log. The cursor write, the cli-fallback record, the record and the notice flags are effects that
# main() wraps one by one: whatever they raise, SystemExit included, cannot change the exit code or stderr (C-2).
# ---------------------------------------------------------------------------
CURSOR_NAME = "transcript-cursor.json"
SHADOW_LOG_NAME = "codegraph-shadow.jsonl"  #: unchanged path (the file's name outlived the shadow era)
SHADOW_LOG_CAP = 10 * 1024 * 1024  #: at this size one {"event":"log-full"} line is written and writing stops
SHADOW_LINE_MAX = 1024
TRANSCRIPT_TIME_BUDGET_S = 0.05  #: wall clock (perf_counter) for the whole turn read; checked between chunks and lines
TRANSCRIPT_READ_LIMIT = 2 * 1024 * 1024  #: bytes read per call; also the cold window; also the longest line parsed
TRANSCRIPT_CHUNK = 256 * 1024
CODEGRAPH_TOOL_PREFIX = "mcp__codegraph__"
_CODEGRAPH_TOOL_BYTES = CODEGRAPH_TOOL_PREFIX.encode("ascii")
#: The tool names of a subagent dispatch: ``Agent`` (Claude Code 2.1.318) and ``Task`` (older hosts).
DISPATCH_TOOLS = ("Agent", "Task")
#: Which route opened the turn, strongest first: ``mcp`` beats ``cli``, which beats ``agent``.
_ROUTE_RANK = {"mcp": 3, "cli": 2, "agent": 1}
_BYTE_MARKERS = (b'"user"', _CODEGRAPH_TOOL_BYTES, b"codegraph ", b'"Agent"', b'"Task"')


def counted_subcommand(tool_input) -> tuple[str, str] | None:
    """(subcommand, summary) when the Bash command is a Counted command in the strict form, else None. Moved verbatim from the
    retired tracker (the Transcript entry rule counts it from the transcript).

    One simple command, an optional single trailing `` 2>&1``, no control operator, no background run; the raw text starts
    with ``codegraph `` and token 0 is exactly ``codegraph``. That is narrower than the row's ``if``, which matches each
    sub-command of a compound command and strips ``VAR=`` prefixes."""
    if not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command")
    if not isinstance(command, str) or tool_input.get("run_in_background"):
        return None
    text = command[:-5] if command.endswith(" 2>&1") else command
    if _CONTROL_RE.search(text) or not command.startswith("codegraph "):
        return None
    import shlex  # deferred: only a Bash line that survived the checks above needs it
    try:
        tokens = shlex.split(text, posix=True)
    except ValueError:
        return None
    if len(tokens) < 2 or tokens[0] != "codegraph" or tokens[1] not in COUNTED_COMMANDS:
        return None
    summary = _SUMMARY_UNSAFE_RE.sub(" ", " ".join(tokens[1:3])).strip()[:80]
    return tokens[1], summary


def entry_facts(obj) -> tuple[str, str | None, str | None]:
    """``(class, route, command)`` of one parsed transcript line. ``class``: 'human-prompt' (a boundary), 'codegraph-use' (route ``mcp``:
    a ``mcp__codegraph__*`` tool use; route ``cli``: a Bash tool use of a Counted command, ``command`` its subcommand),
    'subagent-dispatch' (route ``agent``: an Agent or Task tool use, C-7) or 'other'. Only an assistant entry of the main chain counts. The
    rule is the one the t1 live checks recorded for Claude Code 2.1.318. Fail-open bias: only an entry positively identified as a
    human prompt is a boundary."""
    if not isinstance(obj, dict):
        return "other", None, None
    kind = obj.get("type")
    if kind == "assistant":
        if obj.get("isSidechain"):
            return "other", None, None
        message = obj.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        cli: tuple[str, str] | None = None
        dispatch = False
        for block in content if isinstance(content, list) else ():
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = block.get("name")
            if not isinstance(name, str):
                continue
            if name.startswith(CODEGRAPH_TOOL_PREFIX):
                return "codegraph-use", "mcp", None
            if name == "Bash" and cli is None:
                cli = counted_subcommand(block.get("input"))
            elif name in DISPATCH_TOOLS:
                dispatch = True
        if cli is not None:
            return "codegraph-use", "cli", cli[0]
        if dispatch:
            return "subagent-dispatch", "agent", None
        return "other", None, None
    if kind != "user":
        return "other", None, None
    if obj.get("isSidechain") or obj.get("isMeta") or obj.get("isCompactSummary"):
        return "other", None, None
    if any(key in obj for key in ("origin", "toolUseResult", "sourceToolAssistantUUID")):
        return "other", None, None
    message = obj.get("message")
    if not isinstance(message, dict) or message.get("role") != "user":
        return "other", None, None
    source = obj.get("promptSource")
    if not isinstance(source, str) or source == "system":
        return "other", None, None
    content = message.get("content")
    if isinstance(content, str):
        return "human-prompt", None, None
    if isinstance(content, list):
        if any(isinstance(block, dict) and block.get("type") == "tool_result" for block in content):
            return "other", None, None
        return "human-prompt", None, None
    return "other", None, None


def classify_entry(obj) -> str:
    """The Transcript entry class of one parsed transcript line: 'human-prompt', 'codegraph-use', 'subagent-dispatch' or 'other'."""
    return entry_facts(obj)[0]


def _classify_line(line: bytes) -> tuple[str, str | None, str | None]:
    """``entry_facts`` of a line, or ``('error', None, None)`` for a complete line that is not a JSON object. A line holding none
    of the byte markers is not parsed, only checked for the braces of an object."""
    text = line.strip()
    if not text:
        return "other", None, None
    if any(marker in text for marker in _BYTE_MARKERS):
        try:
            return entry_facts(json.loads(text))
        except Exception:  # noqa: BLE001 - malformed JSON, bad bytes, nesting too deep
            return "error", None, None
    if text[:1] != b"{" or text[-1:] != b"}":
        return "error", None, None
    return "other", None, None


def _identity(st: os.stat_result) -> str:
    if getattr(st, "st_ino", 0):
        return "%d:%d" % (getattr(st, "st_dev", 0), st.st_ino)
    return "ctime:%d" % getattr(st, "st_ctime_ns", 0)  # no inode: the creation time


def _valid_cursor(raw) -> dict | None:
    """The cursor when it has the contract's shape, else None (an unparseable or misshapen cursor reads as absent). A cursor
    written before the cut-over has no ``open_route``, ``open_command`` or ``mcp_seen``: it reads as absent and forces a cold scan."""
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
    if raw.get("open_route") not in ("mcp", "cli", "agent", None) or not isinstance(raw.get("mcp_seen"), bool):
        return None
    command = raw.get("open_command")
    if command is not None and not isinstance(command, str):
        return None
    return raw


def _empty_read(state: str) -> dict:
    """A read result that read nothing: ``state`` and the zero facts."""
    return {"state": state, "session_seen": False, "mcp_seen": False, "open_route": None, "open_command": None,
            "bytes_read": 0, "skipped": 0, "cursor": None, "ms": 0.0}


def read_transcript(payload: dict, session: Session, use_cursor: bool, deadline: float) -> dict:
    """The Transcript turn state of this call, by a true tail read.

    Returns {state, session_seen, mcp_seen, open_route, open_command, bytes_read, skipped, cursor}. ``cursor`` is the dict to persist
    (or None). ``state`` is 'open', 'closed' or 'unknown:<cause>'. ``deadline`` is a ``time.perf_counter()`` value. A cold scan starts
    2 MB before the end; at most 2 MB is read per call; only complete lines are parsed; a hit limit always answers
    window-exceeded, boundary found or not."""
    res = _empty_read("")
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
    if time.perf_counter() >= deadline:
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
        route, command, mcp_seen = cursor["open_route"], cursor["open_command"], cursor["mcp_seen"]
    else:
        pos = max(0, size - limit)
        skipping, turn, seen = False, ("closed" if pos == 0 else None), False
        route, command, mcp_seen = None, None, False

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
                if time.perf_counter() >= deadline:
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
                    kind, how, what = _classify_line(buf[begin:cut])
                    begin = cut + 1
                    if kind == "human-prompt":
                        turn, route, command = "closed", None, None
                    elif kind in ("codegraph-use", "subagent-dispatch"):
                        turn = "open"
                        if how == "mcp":
                            seen, mcp_seen = True, True
                        elif how == "cli":
                            seen = True
                        if route is None or _ROUTE_RANK[how] > _ROUTE_RANK[route]:
                            route, command = how, (what if how == "cli" else None)
                    elif kind == "error":
                        errors += 1
                    if time.perf_counter() >= deadline:
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
    res["skipped"], res["session_seen"], res["mcp_seen"] = skipped, seen, mcp_seen
    res["open_route"], res["open_command"] = route, command
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
                         "session_seen": seen, "updated_at": int(time.time()), "open_route": route,
                         "open_command": command, "mcp_seen": mcp_seen}
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


def measurement_record(tool_name: str, payload: dict, plan: Plan, decision: str, reason: str) -> dict:
    """The enforced Measurement record (contract C-1, Data Shapes). It keeps the Shadow record's keys so the report reads it as it
    is: ``outcome`` is ``enforced``, ``shadow_*`` equal ``live_*`` (the enforced decision and reason), ``turn_marker`` is null and
    ``turn_route`` names the route that opened the turn. It carries no second decision, so it cannot mark a block as false."""
    agent_id = payload.get("agent_id")
    found = plan.transcript
    return {
        "ts": int(time.time()),
        "session": hashlib.sha256(plan.session.key.encode("utf-8", "replace")).hexdigest()[:12],
        "agent": isinstance(agent_id, str) and bool(agent_id),
        "tool": tool_name,
        "target_class": plan.target_class,
        "live_decision": decision,
        "live_reason": reason,
        "turn_marker": None,
        "turn_route": found["open_route"] if found["state"] == "open" else None,
        "transcript_turn": found["state"],
        "session_seen": bool(found["session_seen"]),
        "shadow_decision": decision,
        "shadow_reason": reason,
        "outcome": "enforced",
        "fp": plan.fingerprint[:12] or "none",
        "prompt_key": plan.prompt_key,
        "shadow_ms": found["ms"],
        "bytes_read": found["bytes_read"],
        "skipped_long_line": found["skipped"],
    }


def _apply_cursor(plan: Plan) -> None:
    """The cursor write (C-2 effect 3): inside a usable Session folder only, created first when absent (the reset hook that used to
    create it retired). A failed write is ignored."""
    cursor = plan.transcript.get("cursor")
    session = plan.session
    if cursor is None or not plan.step0_ok or session.problem is not None or not session.ensure_folder():
        return
    _write_cursor(session, cursor)


def _apply_cli_fallback(plan: Plan) -> None:
    """The ``cli-fallback`` record (C-4, moved from the tracker): the turn is open by the command-line route and no MCP call was seen
    this session. One record per session; the flag is created only after the record landed."""
    found, session = plan.transcript, plan.session
    if found["state"] != "open" or found["open_route"] != "cli" or found["mcp_seen"] or session.problem is not None:
        return
    if session.has_plain_file(CLI_FALLBACK_FLAG):
        return
    landed = _late("log_event")(hook="codegraph-first-guard", event="cli-fallback", file=None, session_id=session.key,
                                details={"reason": "mcp-unavailable", "command": found["open_command"]})
    if landed is not False:
        session.create_once(CLI_FALLBACK_FLAG)


def _apply_measurement(tool_name: str, payload: dict, plan: Plan, decision: str, reason: str) -> None:
    """One Measurement record in the project's log, when a log can be written (C-2 effect 6)."""
    path = _shadow_log_path()
    if path is None:
        return
    _append_shadow_line(path, measurement_record(tool_name, payload, plan, decision, reason))


def _quiet(effect, *args) -> None:
    """Run one late effect. Whatever it raises, BaseException included, is swallowed: it can change neither the exit code nor stderr."""
    try:
        effect(*args)
    except BaseException:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# The prompt row (``notice``): pruning once per session and the Connection notice, moved from the retired reset hook (C-5).
# ---------------------------------------------------------------------------
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
    import subprocess  # deferred: only macOS reads the table this way
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


def notice_section(payload) -> str:
    """The Connection notice. Returns a closed-set outcome (``shown``, ``silent:probe-present``, ``silent:precondition``,
    ``silent:host-untrusted``, ``silent:undecidable``, ``silent:budget``, ``silent:error``); prints the notice JSON itself only for
    ``shown``. Writes no file (no bytecode): ``sys.dont_write_bytecode`` is set throughout."""
    started = time.perf_counter()
    saved_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        payload = payload if isinstance(payload, dict) else {}
        agent_id = payload.get("agent_id")
        if isinstance(agent_id, str) and agent_id:
            return "silent:precondition"
        cwd = payload.get("cwd")
        cwd = cwd if isinstance(cwd, str) and cwd else os.getcwd()
        server, index, _body = availability_plan(Session(payload), cwd)
        if server != "configured" or index != "index-present" or not server_starts_process(cwd):
            return "silent:precondition"
        if time.perf_counter() - started > NOTICE_BUDGET_S:
            return "silent:budget"
        table = read_process_table(os.getpid(), max(NOTICE_BUDGET_S - (time.perf_counter() - started), 0.01))
        if time.perf_counter() - started > NOTICE_BUDGET_S:
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


def notice_main() -> None:
    """The ``notice`` row (UserPromptSubmit). It always exits 0 and never blocks a prompt: whatever a duty raises, SystemExit
    included, is swallowed, and one duty failing does not skip the other. It writes no bytecode and deletes no ticket, no turn
    marker and no legacy sentinel."""
    saved_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
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
            # Fail closed (I-8): prune nothing under the parent. The line says why and makes no claim about the gate.
            where = folder or parent
            extra = f": {detail}" if detail else ""
            log(f"the per-user session folder {where} cannot be used ({problem}{extra}); nothing was pruned")
        else:
            _quiet(_prune_once, folder, parent)
            _quiet(notice_section, payload)  # prints the notice itself when it shows one; its outcome is for the bench and the tests
    except BaseException:  # noqa: BLE001
        pass
    finally:
        sys.dont_write_bytecode = saved_bytecode
    sys.exit(0)


def _prune_once(folder: str, parent: str) -> None:
    if _first_prompt_of_session(folder):
        prune_session_folders(parent)


def main() -> None:
    if sys.argv[1:2] == ["notice"]:
        notice_main()
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

    # C-2: the Live plan, then its effects in this order: availability.json and the ticket (apply_state), the cursor, the
    # cli-fallback record, the notice flags and log record, one Measurement record, then stderr and the exit code.
    plan = plan_live(tool_name, tool_input, payload)
    decision, reason = apply_state(plan)
    session, fingerprint = plan.session, plan.fingerprint
    _quiet(_apply_cursor, plan)
    _quiet(_apply_cli_fallback, plan)
    announced = decision == "allow" and (reason.startswith("fail-open:") or reason == "retry-escape-used")
    if announced:
        _quiet(announce_record, reason, tool_name, session, fingerprint)
    _quiet(_apply_measurement, tool_name, payload, plan, decision, reason)
    if decision == "allow":
        if announced:
            announce_line(reason)
        sys.exit(0)

    block(reason, tool_name, tool_input, session)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        log(f"internal error (failing open): {e}")
        sys.exit(0)
