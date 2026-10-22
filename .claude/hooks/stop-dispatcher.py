#!/usr/bin/env python3
"""
stop-dispatcher.py -- ONE Stop hook in place of two.

This is the single Stop seam. The Changed-file check (../scripts/concept_changed_check.py) is its
only member today. A later Stop member added to CHECKS costs no extra program start (a second start
would add 90 to 120 milliseconds to every turn): this dispatcher starts one process and runs the
members one after another inside it, in the order of CHECKS, through the in-process runner
(_inprocess_hook.py). Each member gets the same input bytes it would have been given on its own.

It follows post-edit-dispatcher.py. It differs in two ways, both forced by the Stop event:

  * It is NOT asynchronous: a Stop hook can hold the turn, so its exit code matters.
  * It exits 2 when ANY member exits 2, and writes EVERY member's error text, in member order.
    A member that exits 2 never stops the next member from running. Any other member exit code
    (0, 1, a raised exception) is ignored: the dispatcher fails open.

What the members do is unchanged. They read their own off switches, keep their own state and
print what they printed before. This file only gathers the pieces:

  * Error text is passed through byte for byte, so a member's text is identical
    to running it alone.
  * Output is passed through byte for byte when one member spoke. When several spoke and every
    one printed a JSON object, the objects are merged into one (their systemMessage texts are
    joined with a newline); otherwise the texts are written one after another.
  * Its own failure exits 0. A dispatcher that cannot work must never hold a session.
  * A member whose file is missing is "could not check", never a crash. It adds nothing to the exit
    code, writes one error-log line (hook ``stop-dispatcher``, event ``member-missing``, the member
    string as written in CHECKS) and says so at most once per session: a ``systemMessage`` on exit 0,
    or one trailing line on stderr after every member's unchanged text on exit 2 (on exit 2 the line
    reaches the model, not the operator). The once-per-session marker is a file named
    ``auto-improve-stop-member-missing-<session_id>`` in the system temporary folder, written once
    the notice is written. The other members still run.

Hook contract (Claude Code Stop):
    stdin:  JSON with { session_id, cwd, transcript_path, stop_hook_active, ... }
    stdout: whatever the members printed (for example a JSON systemMessage)
    stderr: the members' error text
    exit 2: a member stopped the turn; otherwise 0
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

#: The Stop members, in the order they run. A hook file that is neither registered in hooks.json
#: nor named here is a file nothing runs (the manifest suite checks this).
CHECKS = [
    "../scripts/concept_changed_check.py",
]

#: The exit code that stops the turn.
STOP_EXIT = 2

#: Prefix of the once-per-session marker for the "a member is missing" notice.
MISSING_MARKER_PREFIX = "auto-improve-stop-member-missing-"


def _write_stream(stream_name: str, data: bytes) -> None:
    """Write raw bytes to stdout or stderr without re-encoding them."""
    if not data:
        return
    try:
        stream = getattr(sys, stream_name)
        buffer = getattr(stream, "buffer", None)
        if buffer is not None:
            buffer.write(data)
        else:
            stream.write(data.decode("utf-8", errors="replace"))
        stream.flush()
    except Exception:
        pass


def _merged_output(pieces: list[bytes]) -> bytes:
    """One output from the members that spoke: verbatim for one, merged JSON for several."""
    if len(pieces) == 1:
        return pieces[0]
    objects: list[dict] = []
    for piece in pieces:
        try:
            parsed = json.loads(piece.decode("utf-8", errors="replace"))
        except ValueError:
            return b"".join(pieces)
        if not isinstance(parsed, dict):
            return b"".join(pieces)
        objects.append(parsed)
    merged: dict = {}
    messages: list[str] = []
    for obj in objects:
        message = obj.get("systemMessage")
        if isinstance(message, str) and message.strip():
            messages.append(message)
        for key, value in obj.items():
            if key != "systemMessage":
                merged.setdefault(key, value)
    if messages:
        merged["systemMessage"] = "\n".join(messages)
    return json.dumps(merged).encode("utf-8")


def _session_id(data: bytes) -> str:
    """The session id in the Stop payload, made safe for a file name; ``unknown`` when absent."""
    try:
        payload = json.loads(data.decode("utf-8", errors="replace"))
        session = payload.get("session_id") if isinstance(payload, dict) else None
    except Exception:
        session = None
    text = session if isinstance(session, str) and session else "unknown"
    return re.sub(r"[^A-Za-z0-9_.-]", "_", text)[:128]


def _log_missing(name: str, session: str) -> None:
    """One error-log line for a missing member. Never raises."""
    try:
        from _error_log import log_event  # beside this file

        log_event(hook="stop-dispatcher", event="member-missing", session_id=session or None,
                  details={"member": name})
    except Exception:
        pass


def main() -> int:
    try:
        data = sys.stdin.buffer.read()
    except Exception:
        data = b""

    try:
        import _inprocess_hook  # beside this file; hooks run as standalone scripts
    except Exception as exc:  # no runner, no dispatch -- but never a held session
        try:
            sys.stderr.write("[stop-dispatcher] cannot load the in-process runner: %r\n" % (exc,))
        except Exception:
            pass
        return 0

    here = Path(__file__).resolve().parent
    stop = False
    errors: list[bytes] = []
    spoken: list[bytes] = []
    missing: list[str] = []
    session = _session_id(data)
    for name in CHECKS:
        if not (here / name).is_file():  # could not check: skip it, run the rest, never a traceback
            missing.append(name)
            _log_missing(name, session)
            continue
        try:
            code, out, err = _inprocess_hook.run_script(here / name, data)
        except Exception as exc:  # the runner itself failed: skip this member, run the next
            errors.append(("[stop-dispatcher] %s could not run: %r\n" % (name, exc)).encode("utf-8"))
            continue
        if err:
            errors.append(err)
        if out and out.strip():
            spoken.append(out)
        if code == STOP_EXIT:
            stop = True

    notice = ""
    marker = Path(tempfile.gettempdir()) / (MISSING_MARKER_PREFIX + session)
    if missing and not marker.exists():
        notice = ("Stop check not run: %s %s missing, so it did not run. Files a shell command wrote "
                  "were not checked against a contract." % (", ".join(missing),
                                                           "is" if len(missing) == 1 else "are"))
        if not stop:
            spoken.append(json.dumps({"systemMessage": notice}).encode("utf-8"))

    _write_stream("stderr", b"".join(errors))
    if notice and stop:
        _write_stream("stderr", ("[stop-dispatcher] " + notice + "\n").encode("utf-8"))
    if spoken:
        _write_stream("stdout", _merged_output(spoken))
    if notice:  # spent once it is written, so the session hears it at most once
        try:
            marker.touch(exist_ok=False)
        except OSError:
            pass
    return STOP_EXIT if stop else 0


if __name__ == "__main__":
    try:
        code = main()
    except BaseException:  # last resort: a Stop dispatcher that fails must not hold the session
        code = 0
    sys.exit(code)
