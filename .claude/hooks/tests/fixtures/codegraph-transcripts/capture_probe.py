#!/usr/bin/env python3
"""Throwaway capture probe for the CodeGraph hooks redesign live checks (issue #261, block 1).

NOT a shipped hook. It must be registered ONLY in a throwaway folder outside every repository
(for example a folder under the system temp directory), never in this repository or in ~/.claude.

Registered for PreToolUse, PostToolUse and UserPromptSubmit. At each event it copies the hook
payload and the tail of the session transcript into <capture dir>/<seq>-<event>-<tool>.json.

Controls, read from files next to this script (so no environment variable is needed):
  probe-mode.txt   one word:
                     capture  (default) record and exit 0
                     timeout  record, then on PreToolUse sleep 3 s and exit 2 (point f: the row has a 1 s timeout)
                     inject   record, and on UserPromptSubmit print hookSpecificOutput.additionalContext
  probe-out        capture folder (default: <script dir>/captures)
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

TAIL_LINES = 400
SLEEP_SECONDS = 3.0
INJECT_TEXT = "PROBE-INJECTED-CONTEXT-MARKER"


def read_mode(here: Path) -> str:
    try:
        return (here / "probe-mode.txt").read_text(encoding="utf-8").strip() or "capture"
    except OSError:
        return "capture"


def next_seq(out: Path) -> int:
    # Parallel hook processes can race on the sequence; the timestamp and pid disambiguate.
    return len([p for p in out.iterdir() if p.suffix == ".json"]) + 1


def transcript_tail(path_text: object) -> dict[str, object]:
    if not isinstance(path_text, str) or not path_text:
        return {"readable": False, "reason": "no transcript_path"}
    path = Path(path_text)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return {"readable": False, "reason": f"{type(exc).__name__}: {exc}"}
    lines = raw.decode("utf-8", errors="replace").splitlines()
    return {
        "readable": True,
        "size_bytes": len(raw),
        "line_count": len(lines),
        "tail": lines[-TAIL_LINES:],
    }


def main() -> int:
    here = Path(__file__).resolve().parent
    mode = read_mode(here)
    started = time.time()
    try:
        payload = json.load(sys.stdin)
    except (OSError, ValueError) as exc:
        payload = {"_unparseable": f"{type(exc).__name__}: {exc}"}
    event = str(payload.get("hook_event_name", "unknown")) if isinstance(payload, dict) else "unknown"
    tool = str(payload.get("tool_name", "")) if isinstance(payload, dict) else ""

    out_file = here / "probe-out"
    out = Path(out_file.read_text(encoding="utf-8").strip()) if out_file.exists() else here / "captures"
    out.mkdir(parents=True, exist_ok=True)

    record = {
        "captured_at": started,
        "pid": os.getpid(),
        "mode": mode,
        "payload": payload,
        "transcript": transcript_tail(payload.get("transcript_path") if isinstance(payload, dict) else None),
    }
    safe_tool = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in tool)
    name = f"{next_seq(out):04d}-{event}-{safe_tool}-{os.getpid()}.json"
    (out / name).write_text(json.dumps(record, indent=1), encoding="utf-8")

    if mode == "timeout" and event == "PreToolUse":
        time.sleep(SLEEP_SECONDS)
        # Written after the sleep: if this file exists the probe was not killed at the 1 s timeout.
        (out / (name + ".survived-sleep")).write_text(str(time.time() - started), encoding="utf-8")
        sys.stderr.write("probe would block (exit 2)\n")
        return 2
    if mode == "inject" and event == "UserPromptSubmit":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                  "additionalContext": INJECT_TEXT}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
