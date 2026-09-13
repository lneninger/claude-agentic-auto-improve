#!/usr/bin/env python3
"""
critic-verdict-tracker.py -- PostToolUse hook that captures contract-critic
verdicts and updates the accuracy-skip state.

Fires on Edit / Write / MultiEdit. Only acts when the target is a file under
~/.claude/concepts/**/*.md AND its content contains a `## Critique` section
with a recognized `**Verdict:**` line.

State machine:
    Verdict: clean           -> accuracy_update.record_clean(area, contract)  for every derived area
    Verdict: warnings-only   -> accuracy_update.record_failure(area, contract, "critic-warnings-only")
    Verdict: blockers-found  -> accuracy_update.record_failure(area, contract, "critic-blockers-found")
    Verdict: skipped         -> NO state change (non-counting; anti-bootstrap-gaming)

Idempotency: sha1(critique_section_text) is stored at
~/.claude/state/critic-runs-seen.json keyed by absolute contract path.
A subsequent Edit that leaves the Critique section text identical (e.g. a
typo fix elsewhere in the contract) is a no-op.

Hook contract (Claude Code):
    stdin:  { tool_name, tool_input: { file_path | path } }
    exit 0: always (advisory; never blocks)
    stderr: free-form diagnostic (not shown to Claude unless exit != 0)

Bypass:
    CLAUDE_ACCURACY_TRACKER=off  -- disable the hook for a session
"""

from __future__ import annotations

import hashlib
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
SEEN_PATH = STATE_DIR / "critic-runs-seen.json"

# Local imports.
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
    from accuracy_update import record_clean, record_failure  # type: ignore
    _DEPS_OK = True
except Exception as exc:  # pragma: no cover - fail-soft import
    _DEPS_OK = False
    _IMPORT_ERR = exc


VERDICT_PATTERN = re.compile(
    r"^\*\*Verdict:\*\*\s*([A-Za-z][A-Za-z0-9_-]*)",
    re.MULTILINE,
)


def is_disabled() -> bool:
    return os.environ.get("CLAUDE_ACCURACY_TRACKER", "").lower() in {
        "off", "0", "false", "no"
    }


def extract_target_path(tool_input: dict) -> Path | None:
    """Pick the file path out of the tool_input shape Claude Code sends."""
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


def find_last_critique_section(text: str) -> str | None:
    """
    Return the substring covering the LAST `## Critique` section, including
    the heading and ending at EOF or the next top-level / sibling heading.
    Returns None if no section is found.
    """
    # Match `## Critique` (allow trailing whitespace / extra text on the line).
    pattern = re.compile(r"(?im)^##\s+Critique\b.*$")
    last_match = None
    for m in pattern.finditer(text):
        last_match = m
    if last_match is None:
        return None
    start = last_match.start()
    # End at the next `## ` heading of equal or higher level, or EOF.
    tail = text[last_match.end():]
    next_heading = re.search(r"(?m)^#{1,2}\s", tail)
    if next_heading:
        end = last_match.end() + next_heading.start()
    else:
        end = len(text)
    return text[start:end]


def extract_verdict(section: str) -> str | None:
    m = VERDICT_PATTERN.search(section)
    if not m:
        return None
    return m.group(1).strip().lower()


def section_sha1(section: str) -> str:
    return hashlib.sha1(section.encode("utf-8", errors="ignore")).hexdigest()


def load_seen() -> dict:
    if not SEEN_PATH.exists():
        return {}
    try:
        return json.loads(SEEN_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_seen(data: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SEEN_PATH.with_suffix(SEEN_PATH.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.replace(tmp, SEEN_PATH)
    except PermissionError:
        # Best-effort -- leave the tmp alongside the original; next run will reconcile.
        pass


def apply_verdict(contract_path: Path, verdict: str) -> dict:
    """Map verdict to one or more state mutations across the contract's areas."""
    areas = derive_areas(contract_path)
    result = {"verdict": verdict, "areas": areas, "actions": {}}

    if not areas:
        # Unknown area set -- no state mutation, but log so the user can fix mapping.
        log_event(
            hook="accuracy",
            event="no-areas",
            file=str(contract_path),
            details={"verdict": verdict},
        )
        return result

    if verdict == "clean":
        for a in areas:
            result["actions"][a] = record_clean(a, str(contract_path))
    elif verdict in {"warnings-only", "blockers-found"}:
        source = f"critic-{verdict}"
        for a in areas:
            result["actions"][a] = record_failure(a, str(contract_path), source)
    elif verdict == "skipped":
        # Non-counting -- skips are not evidence of accuracy. Log only.
        log_event(
            hook="accuracy",
            event="skip-stub-observed",
            file=str(contract_path),
            details={"areas": areas},
        )
    else:
        log_event(
            hook="accuracy",
            event="unknown-verdict",
            file=str(contract_path),
            details={"verdict": verdict, "areas": areas},
        )

    return result


def main() -> int:
    if is_disabled() or not _DEPS_OK:
        return 0

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, OSError):
        return 0

    tool_name = payload.get("tool_name", "")
    if tool_name not in {"Edit", "Write", "MultiEdit"}:
        return 0

    tool_input = payload.get("tool_input", {}) or {}
    target = extract_target_path(tool_input)
    if target is None or not target.exists():
        return 0
    if not is_concept_contract(target):
        return 0

    try:
        text = target.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0

    section = find_last_critique_section(text)
    if section is None:
        return 0

    verdict = extract_verdict(section)
    if verdict is None:
        return 0

    contract_key = str(target.resolve())
    sha = section_sha1(section)
    seen = load_seen()
    if seen.get(contract_key) == sha:
        # Same Critique section as last hook fire -- no-op (idempotent).
        return 0

    try:
        apply_verdict(target, verdict)
    except Exception as exc:  # pragma: no cover - fail-soft
        log_event(
            hook="accuracy",
            event="tracker-error",
            file=str(target),
            details={"error": str(exc), "verdict": verdict},
        )
        return 0

    seen[contract_key] = sha
    save_seen(seen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
