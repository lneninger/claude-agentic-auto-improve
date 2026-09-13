#!/usr/bin/env python3
"""
contract-status-watcher.py -- PostToolUse hook that fires the accuracy-skip
'rejection' signal when a contract's Status line transitions from an honored
value (approved/implemented) to a non-honored value (rejected/archived/draft).

Plan originally specified PreToolUse; PostToolUse is the cleaner equivalent
because (a) we only react after the edit lands -- never block; (b) parsing
the post-edit file is simpler than handling every tool_input shape variant
(Edit's old_string/new_string, MultiEdit's edits[], Write's content); (c) the
status cache below is what makes transition detection reliable across the
same hook firing on incidental edits.

State machine:
    cache[contract] = approved + current_file = rejected   -> record_failure(source=rejection)
    cache[contract] = approved + current_file = approved   -> no-op (cache refresh only)
    cache[contract] not present + current_file = approved  -> seed cache (no-op)
    cache[contract] = rejected + current_file = approved   -> no-op (re-approval; user is reverting)

Hook contract (Claude Code):
    stdin:  { tool_name, tool_input: { file_path | path } }
    exit 0: always (advisory; never blocks)

Bypass:
    CLAUDE_ACCURACY_TRACKER=off
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HOME = Path.home()
try:  # project-local .claude first, global second
    import _project_paths as _pp
except Exception:  # pragma: no cover - hooks must never crash a tool call
    _pp = None

CONCEPTS_ROOTS = (
    _pp.concepts_roots() if _pp else [HOME / ".claude" / "concepts"]
)
CONCEPTS_ROOT = next(
    (r for r in CONCEPTS_ROOTS if r.exists()), CONCEPTS_ROOTS[0]
)
STATE_DIR = HOME / ".claude" / "state"
CACHE_PATH = STATE_DIR / "contract-status-cache.json"

# Mirror concept-gate.py's vocabulary so we agree on what "honored" means.
HONORED_STATUSES = {"approved", "implemented"}
NON_HONORED_TRANSITION_SIGNALS = {"rejected"}  # the only flip we treat as a bad-plan signal

_HOOKS_DIR = Path(__file__).parent
_SCRIPTS_DIR = _HOOKS_DIR.parent / "scripts"
sys.path.insert(0, str(_HOOKS_DIR))
sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from _error_log import log_event  # type: ignore
except Exception:
    def log_event(*args, **kwargs):
        return

try:
    from derive_area import derive_areas  # type: ignore
    from accuracy_update import record_failure  # type: ignore
    _DEPS_OK = True
except Exception:
    _DEPS_OK = False


STATUS_PATTERN = re.compile(
    r"\*?\*?Status:\*?\*?\s*([A-Za-z][A-Za-z0-9_-]*)",
)


def is_disabled() -> bool:
    return os.environ.get("CLAUDE_ACCURACY_TRACKER", "").lower() in {
        "off", "0", "false", "no"
    }


def extract_target_path(tool_input: dict) -> Path | None:
    for key in ("file_path", "filePath", "path"):
        val = tool_input.get(key)
        if isinstance(val, str) and val:
            return Path(val).expanduser()
    return None


def is_concept_contract(path: Path) -> bool:
    try:
        path_norm = str(path.resolve()).replace("\\", "/").lower()
    except OSError:
        path_norm = str(path).replace("\\", "/").lower()
    if not path_norm.endswith(".md"):
        return False
    for _base in CONCEPTS_ROOTS:
        if path_norm.startswith(str(_base).replace("\\", "/").lower()):
            return True
    return False


def read_status(path: Path) -> str:
    """Mirror concept-gate.contract_status: scan first 60 lines for Status:."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "unknown"
    for line in text.splitlines()[:60]:
        m = STATUS_PATTERN.search(line)
        if m:
            status = m.group(1).lower().strip()
            if status.startswith("superseded"):
                return "superseded"
            return status
    return "unknown"


def load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(data: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_PATH.with_suffix(CACHE_PATH.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.replace(tmp, CACHE_PATH)
    except PermissionError:
        pass


def main() -> int:
    if is_disabled() or not _DEPS_OK:
        return 0

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, OSError):
        return 0

    if payload.get("tool_name") not in {"Edit", "Write", "MultiEdit"}:
        return 0

    target = extract_target_path(payload.get("tool_input", {}) or {})
    if target is None or not target.exists() or not is_concept_contract(target):
        return 0

    contract_key = str(target.resolve())
    current_status = read_status(target)
    cache = load_cache()
    previous_status = cache.get(contract_key)

    # Always refresh cache at the end -- but only fire on a real transition.
    transition_fires = (
        previous_status in HONORED_STATUSES
        and current_status in NON_HONORED_TRANSITION_SIGNALS
    )

    if transition_fires:
        try:
            areas = derive_areas(target)
            for a in areas:
                record_failure(a, contract_key, "rejection")
            log_event(
                hook="accuracy",
                event="rejection-transition",
                file=contract_key,
                details={"from": previous_status, "to": current_status, "areas": areas},
            )
        except Exception as exc:  # pragma: no cover - fail-soft
            log_event(
                hook="accuracy",
                event="status-watcher-error",
                file=contract_key,
                details={"error": str(exc)},
            )

    cache[contract_key] = current_status
    save_cache(cache)
    return 0


if __name__ == "__main__":
    sys.exit(main())
