#!/usr/bin/env python3
"""
journal-post-approval-tracker.py -- PostToolUse hook that fires the
accuracy-skip 'post-approval-journal' signal when a new JOURNAL.md entry
with `Trigger: post-approval` is appended.

Logic:
    - Fires on Edit/Write/MultiEdit when target is ~/.claude/JOURNAL.md
    - Parses every `### YYYY-MM-DD — <title>` block
    - Computes a stable per-entry signature: sha1(date + title)
    - Maintains a cache of seen signatures at
      ~/.claude/state/journal-entries-seen.json
    - For each NEW entry whose Trigger contains 'post-approval', extracts
      'Source contract:' and fires record_failure on every area of that
      contract.
    - On first run (cache empty), seeds the cache with all existing
      signatures WITHOUT firing -- no retroactive failures on pre-existing
      history.

Hook contract (Claude Code):
    stdin:  { tool_name, tool_input: { file_path | path } }
    exit 0: always (advisory; never blocks)

Bypass:
    CLAUDE_ACCURACY_TRACKER=off
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

JOURNAL_PATH = (
    _pp.registry("JOURNAL.md") if _pp else HOME / ".claude" / "JOURNAL.md"
)
STATE_DIR = HOME / ".claude" / "state"
SEEN_PATH = STATE_DIR / "journal-entries-seen.json"

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


ENTRY_HEADER = re.compile(r"^###\s+(\d{4}-\d{2}-\d{2})\s+(?:—|--|-)\s+(.+?)\s*$", re.MULTILINE)
TRIGGER_LINE = re.compile(r"^\s*-\s*\*\*Trigger:\*\*\s*(.+?)\s*$", re.MULTILINE)
SOURCE_LINE = re.compile(r"^\s*-\s*\*\*Source contract:\*\*\s*`?([^\s`]+)`?", re.MULTILINE)


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


def is_journal(path: Path) -> bool:
    try:
        return path.resolve() == JOURNAL_PATH.resolve()
    except OSError:
        return False


def parse_entries(text: str) -> list[dict]:
    """
    Walk the journal and return a list of dicts:
        {sig, date, title, trigger, source_contract, body}
    Body is the text from the entry's `###` heading to the next `###` (or
    next top-level heading), inclusive of the header.
    """
    headers = list(ENTRY_HEADER.finditer(text))
    entries: list[dict] = []
    for i, h in enumerate(headers):
        start = h.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        # Stop at the next `## ` heading if it comes before the next `### `
        tail = text[h.end():end]
        ss_break = re.search(r"(?m)^##\s", tail)
        if ss_break:
            end = h.end() + ss_break.start()
        body = text[start:end]
        date = h.group(1)
        title = h.group(2).strip()
        sig = hashlib.sha1(f"{date}|{title}".encode("utf-8", errors="ignore")).hexdigest()
        trig_m = TRIGGER_LINE.search(body)
        src_m = SOURCE_LINE.search(body)
        entries.append({
            "sig": sig,
            "date": date,
            "title": title,
            "trigger": (trig_m.group(1).strip().lower() if trig_m else ""),
            "source_contract": (src_m.group(1).strip() if src_m else ""),
            "body": body,
        })
    return entries


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
        pass


def resolve_contract_path(raw: str) -> Path | None:
    """Source contract is often written as `~/.claude/concepts/...` or absolute."""
    if not raw or raw.upper() == "N/A":
        return None
    p = Path(raw).expanduser()
    return p if p.exists() else None


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
    if target is None or not target.exists() or not is_journal(target):
        return 0

    try:
        text = target.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0

    entries = parse_entries(text)
    seen = load_seen()
    first_run = seen.get("_initialized") is not True

    if first_run:
        # Seed -- never fire on pre-existing history. Mark every current entry as seen.
        seen = {"_initialized": True, "sigs": {e["sig"]: True for e in entries}}
        save_seen(seen)
        log_event(
            hook="accuracy",
            event="journal-tracker-seeded",
            file=str(target),
            details={"entries_seeded": len(entries)},
        )
        return 0

    known = seen.get("sigs", {})
    new_sigs = [e for e in entries if e["sig"] not in known]
    fired: list[dict] = []

    # Both 'post-approval' (explicit manual entries) and 'post-impl' (reviewer-
    # divergence entries) imply the contract was already approved when the
    # issue surfaced -- same accuracy signal.
    POST_APPROVAL_TOKENS = ("post-approval", "post-impl", "post-implementation")

    for entry in new_sigs:
        # Mark as seen regardless of whether it fires (avoid duplicate-fires).
        known[entry["sig"]] = True
        if not any(tok in entry["trigger"] for tok in POST_APPROVAL_TOKENS):
            continue
        cpath = resolve_contract_path(entry["source_contract"])
        if cpath is None:
            log_event(
                hook="accuracy",
                event="journal-post-approval-no-contract",
                file=str(target),
                details={"entry_title": entry["title"], "raw_source": entry["source_contract"]},
            )
            continue
        try:
            areas = derive_areas(cpath)
            for a in areas:
                record_failure(a, str(cpath), "post-approval-journal")
            fired.append({"title": entry["title"], "contract": str(cpath), "areas": areas})
        except Exception as exc:  # pragma: no cover
            log_event(
                hook="accuracy",
                event="journal-tracker-error",
                file=str(target),
                details={"error": str(exc), "entry_title": entry["title"]},
            )

    seen["sigs"] = known
    save_seen(seen)

    if fired:
        log_event(
            hook="accuracy",
            event="journal-post-approval-fired",
            file=str(target),
            details={"count": len(fired), "fired": fired},
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
