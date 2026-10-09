#!/usr/bin/env python3
"""
post-edit-dispatcher.py -- ONE asynchronous PostToolUse hook in place of four (INV-O4).

Each edit used to start four interpreters, one per post-edit check. This dispatcher starts one and
runs the checks one after another inside it, in the order of CHECKS, through the in-process runner
(_inprocess_hook.py). Each check gets the same input bytes it would have been given on its own.

What the checks do is unchanged. They read their own off switches, write their own state files and
print what they printed before; this file only gathers the pieces.

  * One check's failure never stops the next. A check that raises exits 1 with its traceback on the
    error stream, and the dispatcher carries on.
  * The single output joins each check's context and plain output, in order, each prefixed with the
    check's file name. Streams are decoded as UTF-8 with replacement.
  * Error output passes through to this process's own error stream.
  * It exits 0 whatever happens. A PostToolUse hook is advisory and must never fail an edit.

Hook contract (Claude Code PostToolUse):
    stdin:  JSON with { tool_name, tool_input }
    stdout: JSON { hookSpecificOutput: { hookEventName, additionalContext } } when any check spoke
    exit 0: always
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

#: The four post-edit checks, in the order they have always run. A hook file that is neither
#: registered in hooks.json nor named here is a file nothing runs (the manifest suite checks this).
CHECKS = [
    "integration-check.py",
    "critic-verdict-tracker.py",
    "contract-status-watcher.py",
    "journal-post-approval-tracker.py",
]

HOOK_EVENT = "PostToolUse"


def _decode(raw: bytes) -> str:
    return (raw or b"").decode("utf-8", errors="replace")


def _spoken(stdout: str) -> str:
    """The text one check said: its context if it printed hook JSON, else what it printed."""
    text = stdout.strip()
    if not text:
        return ""
    if text.startswith("{"):
        try:
            obj = json.loads(text)
        except ValueError:
            return text
        if isinstance(obj, dict):
            parts: list[str] = []
            specific = obj.get("hookSpecificOutput")
            if isinstance(specific, dict) and isinstance(specific.get("additionalContext"), str):
                parts.append(specific["additionalContext"])
            if isinstance(obj.get("systemMessage"), str):
                parts.append(obj["systemMessage"])
            if parts:
                return "\n".join(p for p in parts if p.strip())
    return text


def main() -> int:
    try:
        data = sys.stdin.buffer.read()
    except Exception:
        data = b""

    try:
        import _inprocess_hook  # beside this file; hooks run as standalone scripts
    except Exception as exc:  # no runner, no dispatch -- but never a failed edit
        try:
            sys.stderr.write("[post-edit-dispatcher] cannot load the in-process runner: %r\n" % (exc,))
        except Exception:
            pass
        return 0

    here = Path(__file__).resolve().parent
    pieces: list[str] = []
    for name in CHECKS:
        try:
            _code, out, err = _inprocess_hook.run_script(here / name, data)
        except Exception as exc:  # the runner itself failed: skip this check, run the next
            try:
                sys.stderr.write("[post-edit-dispatcher] %s could not run: %r\n" % (name, exc))
            except Exception:
                pass
            continue
        error_text = _decode(err)
        if error_text:
            try:
                sys.stderr.write(error_text)
            except Exception:
                pass
        said = _spoken(_decode(out))
        if said:
            pieces.append("%s: %s" % (name, said))

    if pieces:
        payload = {
            "hookSpecificOutput": {
                "hookEventName": HOOK_EVENT,
                "additionalContext": "\n".join(pieces),
            }
        }
        try:
            sys.stdout.write(json.dumps(payload))
            sys.stdout.flush()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except BaseException:  # last resort: an advisory hook never fails open into a crash
        code = 0
    sys.exit(code)
