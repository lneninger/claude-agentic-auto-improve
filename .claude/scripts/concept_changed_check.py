#!/usr/bin/env python3
"""
concept_changed_check.py -- the Changed-file check: the concept rule, enforced after the fact.

WHAT IT IS
----------
The default enforcement of the concept rule for shell commands. Instead of reading each command
before it runs (a program start on every shell command, and a parser that misreads some commands
and cannot see what a program such as ``python`` or ``node`` writes), it asks git which files
changed and judges each one through ``concept-gate.py``'s own matcher. It runs in two places:

  * At turn end, inside ``stop-dispatcher.py`` (the plugin already starts that process at Stop,
    so the check adds no program start of its own). Input: the Stop payload on stdin.
  * At commit time, as ``concept_changed_check.py --staged``, from the commit step of
    ``/verify-before-done`` and ``/git-commit``. It judges the staged added, copied, modified and
    renamed files, with no baseline.

ONE MATCHER, NOT TWO
--------------------
It lives in the scripts folder and loads ``concept-gate.py`` from the hooks folder beside it
(``../hooks/``) by file path, and imports ``_error_log`` from there. It calls the gate's
``resolve_target``, ``is_trivial_target``, ``pinned_contract`` and ``bypass_env``
(``resolve_target`` applies the gate's own trivial-file rules). It has no second "Files to touch"
reader and no second trivial list, so the two can never disagree. The stop text reuses the gate's
``block_message``. A missing gate or helper is "could not check": exit 0 with one error-log line
at turn end, exit 3 with ``--staged``.

RESULT (a Guard Outcome)
------------------------
  * stopped  exit 2. stderr: one fixed paragraph, then the gate's next-steps text and the files.
  * noted    exit 0 and one JSON ``systemMessage`` on stdout naming the files.
  * clean    exit 0 and nothing said.

At turn end a file counts as changed in this session when git reports it uncommitted (modified,
added, renamed or untracked and not ignored; deletions are never judged) AND it is absent from the
session baseline or its content hash differs from the baseline's. The baseline is written by
``working-agreements.py`` at a ``startup`` SessionStart (see ``write_baseline`` below). A tree with
no baseline, or an unreadable one, counts every uncommitted file (the stricter reading).

It stops only for a file it has not stopped for before in this session, lists only those new
files, never stops twice for the same set, and yields (noted) when ``stop_hook_active`` is set, so
it can never hold a session. A file git marks ``linguist-generated`` is always noted, never
stopped: generator output is not written by a tool call.

FAILS OPEN
----------
git missing, a folder that is not a git tree, a git call over 5 seconds, or its own exception
gives exit 0 at turn end, one error-log line (hook ``concept-changed-check``) and at most one
``systemMessage`` per session saying shell writes were not checked. With ``--staged`` the same
failures give exit 3 ("could not check"), and the skill says so in one sentence and goes on.

GIT CALLS (each with a 5 second limit; no other subprocess, no network)
-----------------------------------------------------------------------
  1. ``git status --porcelain=v1 -z --untracked-files=all``
  2. ``git hash-object --stdin-paths`` (content hashes, one call)
  3. ``git check-attr -z --stdin linguist-generated``

STATE (in the system temporary folder, named by the session id)
---------------------------------------------------------------
  auto-improve-changed-baseline-<session>   the baseline (written at startup)
  auto-improve-changed-stopped-<session>    files already stopped for
  auto-improve-changed-notice-<session>     the one "not checked" note per session

Turn it off, like the gate, with CLAUDE_CONCEPT_GATE=off.

Exit codes:
    0  clean or noted (or failed open at turn end)
    2  stopped (a file no approved contract covers)
    3  --staged only: could not check
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_NAME = "concept-changed-check"
HERE = Path(__file__).resolve().parent
#: The hooks folder beside the scripts folder: where ``concept-gate.py`` and ``_error_log.py`` live.
HOOKS_DIR = HERE.parent / "hooks"

#: Seconds any one git call may take before the check gives up (and fails open).
GIT_TIMEOUT_SECONDS = 5

BASELINE_PREFIX = "auto-improve-changed-baseline-"
STOPPED_PREFIX = "auto-improve-changed-stopped-"
NOTICE_PREFIX = "auto-improve-changed-notice-"

#: The only SessionStart source that writes a baseline. Resume, clear, compact and a missing
#: source write nothing, so a compaction can never absorb changes made earlier in the session.
BASELINE_SOURCE = "startup"

#: Staged states (the index column of the porcelain status) that are judged at commit time:
#: added, copied, modified, renamed. A staged deletion is never judged.
STAGED_STATES = "ACMR"

#: Marks a hash for a path that is not a regular file (a link, say), so it still has an entry.
NO_HASH = "-"

#: The fixed opening of every turn-end stop (round-four finding 8).
FIXED_PARAGRAPH = (
    "These files changed in this working tree during this session and no approved contract "
    "covers them. A person editing in another program, or another session in the same tree, may "
    "have written some of them. If you did not write a file, tell the user which ones and do not "
    "edit or revert them; for the files you wrote, run /design-first or pin the contract that "
    "covers them."
)

#: The opening of a commit-time stop.
STAGED_PARAGRAPH = (
    "These staged files are not covered by any approved contract, so the commit is refused. "
    "Run /design-first or pin the contract that covers them, then commit again."
)


class CannotCheck(Exception):
    """The check could not run (git missing, not a git tree, a slow git call). Fails open."""


# ---------------------------------------------------------------------------
# Logging and per-session state
# ---------------------------------------------------------------------------
def _log(event: str, session: str, details: dict, file: str | None = None) -> None:
    """One structured line in the hook error log. Never raises."""
    try:
        if str(HOOKS_DIR) not in sys.path:
            sys.path.insert(0, str(HOOKS_DIR))
        from _error_log import log_event  # type: ignore

        log_event(hook=HOOK_NAME, event=event, file=file, session_id=session or None, details=details)
    except Exception:
        return


def _safe_session(session: object) -> str:
    text = session if isinstance(session, str) and session else "unknown"
    return re.sub(r"[^A-Za-z0-9_.-]", "_", text)[:128]


def _state_path(prefix: str, session: object) -> Path:
    return Path(tempfile.gettempdir()) / (prefix + _safe_session(session))


def _write_json_atomic(path: Path, data: object) -> bool:
    scratch = path.with_name(path.name + ".tmp-%d" % os.getpid())
    try:
        scratch.write_text(json.dumps(data), encoding="utf-8")
        os.replace(scratch, path)
        return True
    except OSError:
        try:
            scratch.unlink()
        except OSError:
            pass
        return False


def _read_json_object(path: Path) -> dict | None:
    """A JSON file that holds an object, or ``None`` when missing, unreadable or not an object."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _tree_key(root: str) -> str:
    """The identity of a working tree in the baseline: its real top-level folder, case-folded."""
    return os.path.normcase(os.path.realpath(root))


def _file_key(root: str, rel: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.join(root, rel))).replace("\\", "/")


# ---------------------------------------------------------------------------
# git
# ---------------------------------------------------------------------------
def _tree_root(start: str) -> str:
    """The top-level folder of the git working tree holding ``start``. No subprocess."""
    here = Path(os.path.abspath(start))
    for folder in [here, *here.parents]:
        if (folder / ".git").exists():
            return str(folder)
    raise CannotCheck("%s is not inside a git working tree" % start)


def _git(root: str, args: list[str], data: bytes = b"") -> bytes:
    """Run one git call with a time limit and return its output.

    Output goes through temporary files, not pipes: if the time limit passes and git is killed, a
    child it started could still hold a pipe open and make the wait for the pipe last as long as
    that child does. Files have no such wait.
    """
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"  # a read-only look must not take the index lock
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with tempfile.TemporaryFile() as fin, tempfile.TemporaryFile() as fout, tempfile.TemporaryFile() as ferr:
        fin.write(data)
        fin.seek(0)
        try:
            proc = subprocess.Popen(["git", *args], cwd=root, stdin=fin, stdout=fout, stderr=ferr,
                                    env=env, creationflags=flags)
        except OSError as exc:
            raise CannotCheck("git could not be started: %s" % exc)
        try:
            proc.wait(timeout=GIT_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
                proc.wait(timeout=2)
            except Exception:
                pass
            raise CannotCheck("a git call took longer than %d seconds" % GIT_TIMEOUT_SECONDS)
        fout.seek(0)
        ferr.seek(0)
        out = fout.read()
        if proc.returncode != 0:
            raise CannotCheck("git %s failed: %s" % (args[0], ferr.read().decode("utf-8", "replace").strip()[:200]))
        return out


def _status(root: str, untracked: bool) -> list[tuple[str, str]]:
    """(two-letter state, path relative to ``root``) for every entry git reports."""
    raw = _git(root, ["status", "--porcelain=v1", "-z",
                      "--untracked-files=all" if untracked else "--untracked-files=no"])
    parts = raw.split(b"\0")
    entries: list[tuple[str, str]] = []
    index = 0
    while index < len(parts):
        token = parts[index]
        index += 1
        if len(token) < 4:
            continue
        state = token[:2].decode("ascii", "replace")
        path = os.fsdecode(token[3:])
        if "R" in state or "C" in state:
            index += 1  # a rename or copy is followed by its origin path
        entries.append((state, path))
    return entries


def _hashes(root: str, rels: list[str]) -> dict[str, str]:
    """Content hash of each path, in one git call. A path that is not a regular file gets NO_HASH."""
    result = {rel: NO_HASH for rel in rels}
    regular = [rel for rel in rels
               if "\n" not in rel and os.path.isfile(os.path.join(root, rel))]
    if not regular:
        return result
    out = _git(root, ["hash-object", "--stdin-paths"], ("\n".join(regular) + "\n").encode("utf-8"))
    lines = out.decode("ascii", "replace").split()
    if len(lines) != len(regular):
        raise CannotCheck("git hash-object returned %d hashes for %d paths" % (len(lines), len(regular)))
    result.update(zip(regular, lines))
    return result


def _generated(root: str, rels: list[str]) -> set[str]:
    """The paths git marks ``linguist-generated`` (set, or true). One git call."""
    if not rels:
        return set()
    data = b"".join(rel.encode("utf-8") + b"\0" for rel in rels)
    out = _git(root, ["check-attr", "-z", "--stdin", "linguist-generated"], data)
    fields = out.split(b"\0")
    found: set[str] = set()
    for at in range(0, len(fields) - 2, 3):
        if fields[at + 2].decode("utf-8", "replace") in ("set", "true"):
            found.add(fields[at].decode("utf-8", "replace"))
    return found


def _uncommitted_files(root: str) -> list[str]:
    """Paths git reports uncommitted (untracked ones included) that exist as files; deletions are dropped."""
    files = []
    for _state, rel in _status(root, untracked=True):
        full = os.path.join(root, rel)
        if os.path.lexists(full) and not (os.path.isdir(full) and not os.path.islink(full)):
            files.append(rel)
    return files


# ---------------------------------------------------------------------------
# The baseline
# ---------------------------------------------------------------------------
def write_baseline(payload: object) -> bool:
    """Record every uncommitted file (path and content hash) of the session's tree.

    Called by ``working-agreements.py`` (which loads this file by path) on SessionStart. It writes only when the payload's
    ``source`` is ``startup``; for resume, clear, compact or a missing source it writes nothing,
    so a baseline already written for that session id stays exactly as it is. It never raises and
    never prints: any failure leaves no baseline, which makes the check stricter, not looser.
    """
    try:
        if not isinstance(payload, dict) or payload.get("source") != BASELINE_SOURCE:
            return False
        session = payload.get("session_id")
        if not isinstance(session, str) or not session:
            return False
        cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) and payload.get("cwd") else os.getcwd()
        root = _tree_root(cwd)
        rels = _uncommitted_files(root)
        files = _hashes(root, rels) if rels else {}
        record = {"session": session, "trees": {_tree_key(root): files}}
        return _write_json_atomic(_state_path(BASELINE_PREFIX, session), record)
    except BaseException:  # noqa: BLE001 -- a SessionStart caller must never fail a session
        return False


def _baseline_for(session: str, root: str) -> dict[str, str] | None:
    """The baseline's {path: hash} for this tree, or ``None`` (none written, unreadable, other tree)."""
    record = _read_json_object(_state_path(BASELINE_PREFIX, session))
    if record is None or not isinstance(record.get("trees"), dict):
        return None
    files = record["trees"].get(_tree_key(root))
    if not isinstance(files, dict):
        return None
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in files.items()):
        return None
    return files


def _changed_in_session(root: str, rels: list[str], baseline: dict[str, str] | None) -> list[str]:
    """The uncommitted files that are absent from the baseline or whose content hash differs."""
    if baseline is None:
        return list(rels)
    known = [rel for rel in rels if rel in baseline]
    now = _hashes(root, known) if known else {}
    return [rel for rel in rels if rel not in baseline or now.get(rel) != baseline[rel]]


# ---------------------------------------------------------------------------
# The concept gate (the one matcher)
# ---------------------------------------------------------------------------
def _load_gate():
    """``concept-gate.py`` from the hooks folder beside this file's folder, loaded by path."""
    path = HOOKS_DIR / "concept-gate.py"
    if not path.is_file():
        raise CannotCheck("%s is missing" % path)
    if not (HOOKS_DIR / "_error_log.py").is_file():
        raise CannotCheck("%s is missing" % (HOOKS_DIR / "_error_log.py"))
    spec = importlib.util.spec_from_file_location("concept_gate_for_changed_check", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("resolve_target", "is_trivial_target", "pinned_contract", "bypass_env", "block_message",
                 "detect_project_name"):
        if not hasattr(module, name):
            raise CannotCheck("%s has no %s" % (path, name))
    return module


def _uncovered(gate, root: str, rels: list[str]) -> list[tuple[str, str]]:
    """(path, reason) for each file the gate would block."""
    pinned = gate.pinned_contract()
    found = []
    for rel in rels:
        target = Path(os.path.join(root, rel))
        if gate.is_trivial_target(target):
            continue  # the gate's own trivial list; resolve_target would allow it too
        allowed, reason, _contract = gate.resolve_target(target, pinned)
        if not allowed:
            found.append((rel, reason or "no matching contract"))
    return found


def _stop_text(gate, paragraph: str, root: str, items: list[tuple[str, str]], earlier: int) -> str:
    first_path, first_reason = items[0]
    target = Path(os.path.join(root, first_path))
    extras = ["Files with no approved contract (%d):" % len(items)]
    extras.extend("  - %s" % rel.replace("\\", "/") for rel, _reason in items)
    if earlier:
        extras.append("(%d earlier file(s) were already reported this session and are not listed again.)" % earlier)
    body = gate.block_message(first_reason, str(target), gate.detect_project_name(target), extras)
    return paragraph + "\n" + body


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def _say(message: str) -> None:
    """One ``systemMessage`` on stdout."""
    sys.stdout.write(json.dumps({"systemMessage": message}))
    sys.stdout.flush()


def _write_stderr(text: str) -> None:
    try:
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    sys.stderr.write(text if text.endswith("\n") else text + "\n")
    sys.stderr.flush()


def _note_once(session: str, reason: str) -> None:
    """The one "shell writes were not checked" note per session."""
    marker = _state_path(NOTICE_PREFIX, session)
    try:
        fd = os.open(str(marker), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except OSError:
        return
    _say("Changed-file check: shell writes were not checked this session (%s). "
         "Files a shell command or a program writes are not judged against a contract." % reason)


# ---------------------------------------------------------------------------
# The two modes
# ---------------------------------------------------------------------------
def _names(items: list[tuple[str, str]]) -> str:
    return ", ".join(rel.replace("\\", "/") for rel, _reason in items)


def run_turn(raw: bytes) -> int:
    """Turn end: judge what changed during the session."""
    payload = json.loads(raw.decode("utf-8", "replace")) if raw.strip() else {}
    if not isinstance(payload, dict):
        raise ValueError("the Stop payload is not a JSON object")
    session = payload.get("session_id") if isinstance(payload.get("session_id"), str) else ""
    try:
        cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) and payload.get("cwd") else os.getcwd()
        gate = _load_gate()
        if gate.bypass_env():
            return 0
        root = _tree_root(cwd)
        uncommitted = _uncommitted_files(root)
        if not uncommitted:
            return 0
        changed = _changed_in_session(root, uncommitted, _baseline_for(session, root))
        uncovered = _uncovered(gate, root, changed)
        if not uncovered:
            return 0
        generated_paths = _generated(root, [rel for rel, _reason in uncovered])
        generated = [item for item in uncovered if item[0] in generated_paths]
        stoppable = [item for item in uncovered if item[0] not in generated_paths]

        memory_path = _state_path(STOPPED_PREFIX, session)
        record = _read_json_object(memory_path) or {}
        seen = set(record.get("stopped", [])) if isinstance(record.get("stopped"), list) else set()
        new = [item for item in stoppable if _file_key(root, item[0]) not in seen]

        if new and not payload.get("stop_hook_active"):
            seen.update(_file_key(root, rel) for rel, _reason in new)
            _write_json_atomic(memory_path, {"stopped": sorted(seen)})
            _log("block", session, {"files": [rel for rel, _r in new]}, file=new[0][0])
            _write_stderr(_stop_text(gate, FIXED_PARAGRAPH, root, new, len(stoppable) - len(new)))
            return 2

        sentences = []
        if stoppable:
            sentences.append("no approved contract covers %s; this turn is not stopped for %s "
                             "(already reported, or the turn was already continued once)"
                             % (_names(stoppable), "it" if len(stoppable) == 1 else "them"))
        if generated:
            sentences.append("generated files changed and are not judged: %s" % _names(generated))
        _say("Changed-file check: " + "; ".join(sentences) + ".")
        return 0
    except CannotCheck as exc:
        _log("warn", session, {"reason": str(exc)})
        _note_once(session or "unknown", str(exc))
        return 0
    except Exception as exc:  # noqa: BLE001 -- the check must never hold a session
        _log("warn", session, {"reason": "%s: %s" % (type(exc).__name__, exc)})
        _note_once(session or "unknown", "the check hit an error: %s" % type(exc).__name__)
        return 0


def run_staged() -> int:
    """Commit time: judge the staged added, copied, modified and renamed files."""
    try:
        gate = _load_gate()
        if gate.bypass_env():
            return 0
        root = _tree_root(os.getcwd())
        staged = [rel for state, rel in _status(root, untracked=False) if state[0] in STAGED_STATES]
        if not staged:
            return 0
        uncovered = _uncovered(gate, root, staged)
        generated_paths = _generated(root, [rel for rel, _reason in uncovered])
        stoppable = [item for item in uncovered if item[0] not in generated_paths]
        if not stoppable:
            return 0
        _log("block", "", {"files": [rel for rel, _r in stoppable], "mode": "staged"}, file=stoppable[0][0])
        _write_stderr(_stop_text(gate, STAGED_PARAGRAPH, root, stoppable, 0))
        return 2
    except BaseException as exc:  # noqa: BLE001
        if isinstance(exc, KeyboardInterrupt):
            raise
        _log("warn", "", {"reason": "%s: %s" % (type(exc).__name__, exc), "mode": "staged"})
        _write_stderr("[%s] could not check the staged files: %s" % (HOOK_NAME, exc))
        return 3


def main() -> int:
    if "--staged" in sys.argv[1:]:
        return run_staged()
    try:
        raw = sys.stdin.buffer.read()
    except Exception:
        raw = b""
    try:
        return run_turn(raw)
    except BaseException as exc:  # noqa: BLE001 -- unreadable input and the like: fail open, silently
        if isinstance(exc, KeyboardInterrupt):
            raise
        _log("warn", "", {"reason": "%s: %s" % (type(exc).__name__, exc)})
        return 0


if __name__ == "__main__":
    sys.exit(main())
