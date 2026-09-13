#!/usr/bin/env python3
"""
integration-check.py -- PostToolUse hook for cross-module integration consistency.

Emits WARNINGS (never blocks) when a backend DTO or SignalR event payload is
modified without the paired frontend model being touched in the same session,
or vice versa.

Hook contract (Claude Code):
    stdin:  JSON with { tool_name, tool_input: { file_path | path } }
    exit 0: always (advisory only -- never blocks)
    stdout: JSON with informational warnings if integration pairs are affected

This hook reads ~/.claude/INTEGRATION.md to find DTO<->model pairings.
It maintains a lightweight session state file at $TEMP/claude-integration-check.json
to track which files have been touched in the current session.

Bypass:
    CLAUDE_INTEGRATION_CHECK=off  -- disable the hook for a session
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

HOME = Path.home()
try:  # project-local .claude first, global second
    import _project_paths as _pp
except Exception:  # pragma: no cover - hooks must never crash a tool call
    _pp = None

INTEGRATION_MD = (
    _pp.registry("INTEGRATION.md") if _pp
    else HOME / ".claude" / "INTEGRATION.md"
)
STATE_FILE = Path(tempfile.gettempdir()) / "claude-integration-check.json"

# Known DTO<->Model pairings extracted from INTEGRATION.md patterns.
# These are file-path pattern pairs: (backend glob, frontend glob).
# The hook checks if editing one side has a corresponding edit on the other.
BACKEND_EXTENSIONS = {".cs"}
FRONTEND_EXTENSIONS = {".ts"}

# Directories that indicate backend vs frontend.
#
# These are the only project-shaped facts this hook needs, so they live in
# integration-check.rules.json beside it rather than inline here, and the hook
# itself is generic. See that file for the fail-soft note: this hook only ever
# emits a WARNING, so an absent rules file costs a reminder rather than a
# safety layer. A guard that BLOCKS must fail closed instead.
_IC_RULES_PATH = Path(__file__).resolve().parent / "integration-check.rules.json"


def _load_integration_rules() -> dict:
    try:
        with _IC_RULES_PATH.open(encoding="utf-8") as _f:
            data = json.load(_f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


_IC_RULES = _load_integration_rules()
BACKEND_MARKERS = [str(m) for m in (_IC_RULES.get("backend_markers") or [])]
FRONTEND_MARKERS = [str(m) for m in (_IC_RULES.get("frontend_markers") or [])]

# Specific directories that are integration-sensitive
BACKEND_INTEGRATION_DIRS = [
    "Controllers/",
    "Dtos/",
    "Models/",
    "SignalR/",
    "Hubs/",
]
FRONTEND_INTEGRATION_DIRS = [
    "core/models/",
    "core/services/",
    "core/state/",
]


def is_disabled() -> bool:
    return os.environ.get("CLAUDE_INTEGRATION_CHECK", "").lower() in {
        "off", "0", "false", "no"
    }


def is_backend_file(path: str) -> bool:
    p = Path(path)
    if p.suffix.lower() not in BACKEND_EXTENSIONS:
        return False
    return any(marker in path.replace("\\", "/") for marker in BACKEND_MARKERS)


def is_frontend_file(path: str) -> bool:
    p = Path(path)
    if p.suffix.lower() not in FRONTEND_EXTENSIONS:
        return False
    return any(marker in path.replace("\\", "/") for marker in FRONTEND_MARKERS)


def is_integration_sensitive(path: str) -> bool:
    """Check if a file is in an integration-sensitive directory."""
    normalized = path.replace("\\", "/")
    all_dirs = BACKEND_INTEGRATION_DIRS + FRONTEND_INTEGRATION_DIRS
    return any(d in normalized for d in all_dirs)


def load_session_state() -> dict:
    """Load the set of files touched in this session."""
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"backend_files": [], "frontend_files": [], "warnings_emitted": []}


def save_session_state(state: dict) -> None:
    try:
        STATE_FILE.write_text(
            json.dumps(state, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def extract_file_path(payload: dict) -> str | None:
    tool_input = payload.get("tool_input") or {}
    for key in ("file_path", "filePath", "path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def check_integration_pair(path: str, state: dict) -> str | None:
    """
    Check if the edited file is one side of an integration pair
    and the other side hasn't been touched.
    Returns a warning message or None.
    """
    normalized = path.replace("\\", "/")

    if not is_integration_sensitive(normalized):
        return None

    if is_backend_file(path):
        # Backend file edited -- check if any frontend integration files were touched
        if not state["frontend_files"]:
            # Check if this is a controller/DTO/SignalR file
            for marker in BACKEND_INTEGRATION_DIRS:
                if marker in normalized:
                    filename = Path(path).stem
                    return (
                        f"Backend integration file modified: {Path(path).name}. "
                        f"Check ~/.claude/INTEGRATION.md for paired frontend "
                        f"model/service files that may need updating."
                    )

    elif is_frontend_file(path):
        # Frontend file edited -- check if any backend integration files were touched
        if not state["backend_files"]:
            for marker in FRONTEND_INTEGRATION_DIRS:
                if marker in normalized:
                    filename = Path(path).stem
                    return (
                        f"Frontend integration file modified: {Path(path).name}. "
                        f"Check ~/.claude/INTEGRATION.md for paired backend "
                        f"controller/DTO files that may need updating."
                    )

    return None


def main() -> None:
    if is_disabled():
        sys.exit(0)

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "Write", "MultiEdit"):
        sys.exit(0)

    file_path = extract_file_path(payload)
    if not file_path:
        sys.exit(0)

    # Load session state
    state = load_session_state()

    # Record this file
    normalized = file_path.replace("\\", "/")
    if is_backend_file(file_path) and normalized not in state["backend_files"]:
        state["backend_files"].append(normalized)
    elif is_frontend_file(file_path) and normalized not in state["frontend_files"]:
        state["frontend_files"].append(normalized)

    # Check for integration pair warnings
    warning = check_integration_pair(file_path, state)

    # Save state
    save_session_state(state)

    if warning and warning not in state.get("warnings_emitted", []):
        state.setdefault("warnings_emitted", []).append(warning)
        save_session_state(state)
        # Emit as informational output (not blocking)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": f"[integration-check] WARNING: {warning}"
            }
        }
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
