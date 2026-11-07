#!/usr/bin/env python3
"""
journal-post-approval-tracker.py -- PostToolUse hook, a thin wrapper around
``accuracy_update.process_journal_change``.

It fires the accuracy-skip 'post-approval-journal' signal when a new journal entry whose Trigger is a
post-approval one (post-approval, post-impl) is added. All of the logic -- parsing the entries, the machine-wide
seen cache, the per-file seeding keyed by checkout-equivalent path (I-14), the firing -- lives in
``accuracy_update.process_journal_change(files, fresh=())``, so ``registry_append.py`` and this hook share one
implementation.

What the hook itself does:
    - fires on Edit/Write/MultiEdit
    - matches EVERY journal file, resolved at call time: the root ``JOURNAL.md`` and every
      ``JOURNAL/<domain>.md`` beside it (``registry_files("JOURNAL.md")``)
    - hands that one file to ``process_journal_change``

Hook contract (Claude Code):
    stdin:  { tool_name, tool_input: { file_path | path } }
    exit 0: always (advisory; never blocks). One stderr line if the ``accuracy_update`` entry point is missing.

Bypass:
    CLAUDE_ACCURACY_TRACKER=off
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).parent
_SCRIPTS_DIR = _HOOKS_DIR.parent / "scripts"
sys.path.insert(0, str(_HOOKS_DIR))
sys.path.insert(0, str(_SCRIPTS_DIR))

try:  # project-local .claude first, global second
    import _project_paths as _pp
except Exception:  # pragma: no cover - hooks must never crash a tool call
    _pp = None

try:
    from _error_log import log_event  # type: ignore
except Exception:
    def log_event(*args, **kwargs):
        return

_ENTRY_POINT_ERROR = ""
try:
    from accuracy_update import process_journal_change  # type: ignore
except Exception as exc:  # the scripts folder is missing or too old: say so once, never fail the edit
    process_journal_change = None  # type: ignore
    _ENTRY_POINT_ERROR = "%s: %s" % (type(exc).__name__, exc)


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


def _same_file(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def is_journal(path: Path) -> bool:
    """True for the root JOURNAL.md or any domain file beside it, as the resolver lists them right now."""
    if _pp is not None:
        try:
            return any(_same_file(path, candidate) for candidate in _pp.registry_files("JOURNAL.md"))
        except Exception as exc:
            if path.name == "JOURNAL.md" or (path.parent.name == "JOURNAL" and path.suffix == ".md"):
                # A hooks folder older than the scripts (no registry_files): the edit goes untracked. Say so once
                # and log it under the event name the default branch's tracker used; any other path stays silent.
                try:
                    sys.stderr.write("[journal-post-approval-tracker] registry_files is unavailable in %s (%s); "
                                     "the journal edit was not tracked\n"
                                     % (getattr(_pp, "__file__", "_project_paths.py"), type(exc).__name__))
                except Exception:
                    pass
                log_event(hook="journal-post-approval-tracker", event="journal-tracker-reader-missing",
                          file=str(path), details={"reason": "_project_paths.registry_files is unavailable",
                                                   "error": "%s: %s" % (type(exc).__name__, exc)},
                          log_name="accuracy")
            return False
    # No resolver (a partial copy of the hooks folder): fall back to the names, so the missing
    # entry point below is still reported once instead of the edit being silently ignored.
    return path.name == "JOURNAL.md" or (path.parent.name == "JOURNAL" and path.suffix == ".md")


def main() -> int:
    if is_disabled():
        return 0

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, OSError, ValueError):
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") not in {"Edit", "Write", "MultiEdit"}:
        return 0

    tool_input = payload.get("tool_input", {})
    target = extract_target_path(tool_input if isinstance(tool_input, dict) else {})
    if target is None or not target.exists() or not is_journal(target):
        return 0

    if process_journal_change is None:
        try:
            sys.stderr.write("[journal-post-approval-tracker] accuracy_update.process_journal_change is "
                             "unavailable (%s); the edit was not tracked\n" % (_ENTRY_POINT_ERROR or "missing"))
        except Exception:
            pass
        return 0

    try:
        process_journal_change([target])
    except Exception as exc:  # never fail a tool call
        log_event(hook="accuracy", event="journal-tracker-error", file=str(target),
                  details={"error": str(exc)}, log_name="accuracy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
