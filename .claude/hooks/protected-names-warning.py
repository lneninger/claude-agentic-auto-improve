#!/usr/bin/env python3
"""
protected-names-warning.py -- the turn-end warning of the Protected-name check.

A member of ``stop-dispatcher.py``'s ``CHECKS`` list (registration form B: no ``hooks.json`` entry, no new
program start). At turn end it compares the database-guard rules file of two trees, the one the payload's
``cwd`` is in and the ``CLAUDE_PROJECT_DIR`` tree (each once; one tree reached by two routes is one tree),
with the same file at the tip of the LOCAL default-branch ref, using ``_protected_names.py``.

RESULT (a Guard Outcome: only ``clean`` or ``noted``, never ``stopped``)
  * a removal (or a rules file the check cannot read): ONE JSON ``systemMessage`` on one line of standard
    output, naming each tree and the missing names. The same set in the same session is quiet the second
    time; a different set speaks again; a new session speaks again.
  * origin exists but its default-branch ref cannot be read: one noted line per session and tree.
  * no origin, git missing, or any other failure to check: silent.
  * kept, first install: silent.

NEVER stops a turn: exit 0 on every path, its own exception included. NEVER touches the network: it runs
no ``git fetch`` (the check is called without ``fetch``).

NO-CHANGE FAST PATH (form B): per tree and session it remembers a signature of the rules file (size and
modification time) and of the default-branch ref files (read from the git folder, no git process). When the
signature is unchanged since its last run in the session it runs NO git call at all.

STATE: one small JSON record per session, ``auto-improve-protected-names-<session id>``, in the system
temporary folder.

Hook contract (Claude Code Stop):
    stdin:  JSON with { session_id, cwd, ... }
    stdout: one JSON line { "systemMessage": ... } when there is something to say
    exit 0: always
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

STATE_PREFIX = "auto-improve-protected-names-"

#: The loose ref files whose content decides whether the default branch moved, relative to the common git folder.
_REF_FILES = ("refs/remotes/origin/HEAD", "refs/remotes/origin/master", "refs/remotes/origin/main")
_RULES_REL_PARTS = (".claude", "hooks", "db-destructive-guard.rules.json")


def _session_id(payload):
    session = payload.get("session_id") if isinstance(payload, dict) else None
    text = session if isinstance(session, str) and session else "unknown"
    return re.sub(r"[^A-Za-z0-9_.-]", "_", text)[:128]


def _find_tree_root(start):
    """The nearest folder at or above ``start`` that holds a ``.git`` entry, or None."""
    try:
        current = os.path.abspath(start)
    except Exception:  # noqa: BLE001
        return None
    for _ in range(64):
        if os.path.exists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent
    return None


def _trees(payload):
    """The distinct tree roots to check: the payload's cwd tree, then the CLAUDE_PROJECT_DIR tree."""
    starts = []
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    if isinstance(cwd, str) and cwd.strip():
        starts.append(cwd)
    project = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    if project:
        starts.append(project)
    roots, seen = [], set()
    for start in starts:
        root = _find_tree_root(start)
        if root is None:
            continue
        key = os.path.normcase(os.path.realpath(root))
        if key not in seen:
            seen.add(key)
            roots.append(root)
    return roots


def _stat_pair(path):
    try:
        st = os.stat(path)
        return [st.st_size, st.st_mtime_ns]
    except OSError:
        return None


def _read_small(path):
    try:
        with open(path, "rb") as handle:
            return handle.read(4096).decode("utf-8", errors="replace").strip()
    except OSError:
        return None


def _git_dirs(root):
    """``(git_dir, common_dir)`` read from the files, with no git process. Either may be None."""
    dot_git = os.path.join(root, ".git")
    git_dir = None
    if os.path.isdir(dot_git):
        git_dir = dot_git
    elif os.path.isfile(dot_git):
        text = _read_small(dot_git) or ""
        if text.startswith("gitdir:"):
            git_dir = os.path.normpath(os.path.join(root, text[len("gitdir:"):].strip()))
    if git_dir is None:
        return None, None
    common = git_dir
    text = _read_small(os.path.join(git_dir, "commondir"))
    if text:
        common = os.path.normpath(os.path.join(git_dir, text))
    return git_dir, common


def _signature(root):
    """A string that changes when the tree's rules file or the default-branch ref files change."""
    _git_dir, common = _git_dirs(root)
    sig = {"rules": _stat_pair(os.path.join(root, *_RULES_REL_PARTS))}
    if common is not None:
        sig["refs"] = {name: _read_small(os.path.join(common, *name.split("/"))) for name in _REF_FILES}
        sig["packed"] = _stat_pair(os.path.join(common, "packed-refs"))
        sig["config"] = _stat_pair(os.path.join(common, "config"))
    return json.dumps(sig, sort_keys=True)


def _state_path(session):
    return os.path.join(tempfile.gettempdir(), STATE_PREFIX + session)


def _load_state(session):
    try:
        with open(_state_path(session), "r", encoding="utf-8") as handle:
            state = json.load(handle)
        if isinstance(state, dict) and isinstance(state.get("trees"), dict):
            state.setdefault("spoken", [])
            state.setdefault("noted", [])
            return state
    except Exception:  # noqa: BLE001
        pass
    return {"trees": {}, "spoken": [], "noted": []}


def _save_state(session, state):
    try:
        with open(_state_path(session), "w", encoding="utf-8") as handle:
            json.dump(state, handle)
    except Exception:  # noqa: BLE001
        pass


def _removal_message(root, result):
    verdict = result["verdict"]
    if verdict == "names-removed":
        names = ", ".join(repr(n) for n in result["missing"])
        return ("Protected database names are missing from %s: %s. The default branch lists them, so only a "
                "person removes them: restore them, or change only the rules file in its own pull request "
                "and merge it by hand." % (root, names))
    side = "the default branch's" if verdict == "reference-malformed" else "this tree's"
    return ("The protected-name check cannot read %s database-guard rules file for %s (%s); the guard fails "
            "closed until a person repairs it." % (side, root, result.get("reason", "")))


def run(data):
    """The messages to say, as a list of strings. Raises only on a bug the caller swallows."""
    try:
        payload = json.loads(data.decode("utf-8", errors="replace")) if data.strip() else {}
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    import _protected_names

    session = _session_id(payload)
    state = _load_state(session)
    messages = []
    changed = False
    for root in _trees(payload):
        key = os.path.normcase(os.path.realpath(root))
        sig = _signature(root)
        record = state["trees"].get(key)
        if isinstance(record, dict) and record.get("sig") == sig:
            continue  # nothing changed since the last run in this session: no git call
        state["trees"][key] = {"sig": sig}
        changed = True
        result = _protected_names.check(root)  # no fetch, ever
        verdict = result["verdict"]
        if verdict in ("names-removed", "working-malformed", "reference-malformed"):
            spoken_key = "%s|%s|%s" % (key, verdict, "\x1f".join(result["missing"]))
            if spoken_key not in state["spoken"]:
                state["spoken"].append(spoken_key)
                messages.append(_removal_message(root, result))
        elif verdict == "unverifiable" and result.get("reason_code") == "no-default-ref":
            if key not in state["noted"]:
                state["noted"].append(key)
                messages.append("Protected-name check: %s has an origin but its default branch ref cannot be "
                                "read, so protected database names were not compared." % root)
    if changed:
        _save_state(session, state)
    return messages


def main():
    try:
        data = sys.stdin.buffer.read()
    except Exception:  # noqa: BLE001
        data = b""
    try:
        messages = run(data)
        if messages:
            sys.stdout.write(json.dumps({"systemMessage": "\n".join(messages)}) + "\n")
            sys.stdout.flush()
    except BaseException:  # noqa: BLE001 -- a Stop hook never holds a session
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
