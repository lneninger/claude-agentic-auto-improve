"""
accuracy_update.py -- single state-mutation entrypoint for the contract-critic
accuracy-skip system.

Every bad-plan signal funnels through this script:
    - contract-rejection-detector hook  (Status: approved -> rejected)
    - post-approval-journal-tracker hook (JOURNAL.md entry, Trigger: post-approval)
    - fullstack-code-reviewer agent      (writes divergence to reviewer-verdicts.jsonl)
    - /critique-now skill                (forced BLOCKER on a skipped contract)

The clean-run path (verdict: clean from contract-critic) also funnels through here
via 'record-clean'. /design-first Step 2.5a never calls record-clean on a skip
itself -- skips are non-counting (anti-bootstrap-gaming).

State file: the git-tracked <project>/.claude/contract-accuracy.json,
            resolved at call time via accuracy_state_path()
Audit log:  <project>/.claude/logs/errors.jsonl when CLAUDE_PROJECT_DIR is set,
            ~/.claude/logs/errors.jsonl otherwise (logs_dir() has no cwd
            fallback, unlike claude_roots()).  hook="accuracy",
            event="clean"|"failure"

CLI:
    accuracy_update.py record-clean <area> <contract>
    accuracy_update.py record-failure <area> <contract> <source>
    accuracy_update.py query <area>
    accuracy_update.py dump-table
    accuracy_update.py record-from-contract <contract> <verdict|failure-source>

The 'record-from-contract' form derives areas via derive_area.derive_areas and
applies the verdict/failure to ALL matched areas in one call -- convenient for
hooks that don't want to shell out per-area.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

# Local imports.
sys.path.insert(0, str(Path(__file__).parent))
from derive_area import derive_areas

# The bridge resolves the sibling hooks/ directory from __file__ and appends
# it to sys.path, which is what makes `_error_log` importable below. It used
# to be reached through a home-rooted hooks directory -- one the 2026-08-25
# migration removed -- so this import silently fell through to the no-op stub
# and the audit trail went dark without anyone noticing.
#
# Do not restore the literal home-rooted form, even in a comment: the INV-1
# guard in the test suite is a source-text scan and will flag it (#35).
from _claude_paths import accuracy_state_path

# Passive error logging (fail-soft import) -- prefer the hooks logger so audit
# events land in the same errors.jsonl as concept-gate etc. That resolves to
# <project>/.claude/logs/ when CLAUDE_PROJECT_DIR is set (Claude Code launching
# a hook) and to ~/.claude/logs/ otherwise (a plain shell) -- logs_dir() has no
# cwd fallback, unlike claude_roots().
try:
    from _error_log import log_event  # type: ignore
except Exception:
    def log_event(*args, **kwargs):
        return


def state_path() -> Path:
    """The contract-accuracy ledger, resolved at CALL time.

    Exactly one copy is authoritative: the git-tracked repo copy. Binding this
    as a module-level constant is what produced the split brain -- signal
    accumulating into a one-bucket file on the workstation while 15 areas of
    real history sat stranded in the repo (work item #35, INV-2/INV-7).
    """
    return accuracy_state_path()


WARMUP_THRESHOLD = 5
HISTORY_CAP = 50  # cap per-area history to avoid unbounded growth


# ---------------------------------------------------------------------------
# Locking + atomic IO
# ---------------------------------------------------------------------------

@contextmanager
def _file_lock(path: Path, timeout: float = 5.0):
    """
    Cross-platform sentinel-file lock. Spins on FileExistsError until either
    the sentinel disappears or `timeout` elapses. The state JSON is small
    (sub-kilobyte) so the read-modify-write window is microseconds; this is
    sufficient for the expected concurrency.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lockfile = path.with_suffix(path.suffix + ".lock")
    start = time.monotonic()
    while True:
        try:
            fd = os.open(str(lockfile), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                yield
            finally:
                try:
                    os.close(fd)
                except OSError:
                    pass
                try:
                    lockfile.unlink()
                except OSError:
                    pass
            return
        except FileExistsError:
            if time.monotonic() - start > timeout:
                # Stale lock? Force-remove and proceed (best-effort).
                try:
                    lockfile.unlink()
                except OSError:
                    pass
                # One more try; if it still fails, propagate.
                fd = os.open(str(lockfile), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    yield
                finally:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                    try:
                        lockfile.unlink()
                    except OSError:
                        pass
                return
            time.sleep(0.05)


def _load_state() -> dict:
    sp = state_path()
    if not sp.exists():
        return {"schema_version": 1, "areas": {}}
    try:
        data = json.loads(sp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Corrupt -- start clean. The old file is preserved as .corrupt for diagnosis.
        backup = sp.with_suffix(sp.suffix + f".corrupt.{int(time.time())}")
        try:
            sp.rename(backup)
        except OSError:
            pass
        return {"schema_version": 1, "areas": {}}
    if "areas" not in data:
        data["areas"] = {}
    return data


def _save_state(data: dict, retries: int = 8, retry_delay: float = 0.05) -> None:
    """
    Write the state file atomically. On Windows, os.replace can transiently
    fail with PermissionError when OneDrive/Defender is scanning the file;
    we retry with a short backoff so a 6th write doesn't crash a long-running
    /design-first session. The retry budget is small (~0.4s total) so a
    genuinely stuck target still fails fast.
    """
    sp = state_path()
    sp.parent.mkdir(parents=True, exist_ok=True)
    tmp = sp.with_suffix(sp.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    last_err: Exception | None = None
    for _ in range(retries):
        try:
            os.replace(tmp, sp)
            return
        except PermissionError as e:
            last_err = e
            time.sleep(retry_delay)
    # Last attempt -- let the exception propagate if it still fails.
    try:
        os.replace(tmp, sp)
    except Exception:
        # Tmp file is stranded; clean up so we don't litter the directory.
        try:
            tmp.unlink()
        except OSError:
            pass
        raise last_err if last_err else Exception("state save failed")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_area(state: dict, area: str) -> dict:
    areas = state["areas"]
    if area not in areas:
        areas[area] = {
            "clean_streak": 0,
            "skip_eligible": False,
            "total_runs": 0,
            "last_updated": None,
            "last_contract": None,
            "last_verdict": None,
            "history": [],
        }
    return areas[area]


def _trim_history(entry: dict) -> None:
    if len(entry["history"]) > HISTORY_CAP:
        entry["history"] = entry["history"][-HISTORY_CAP:]


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

def record_clean(area: str, contract: str) -> dict:
    """
    Apply a clean critic verdict to one area. Increments clean_streak and
    flips skip_eligible when the warmup threshold is reached. Returns the
    updated area entry.
    """
    with _file_lock(state_path()):
        state = _load_state()
        entry = _ensure_area(state, area)
        entry["clean_streak"] += 1
        entry["total_runs"] += 1
        entry["skip_eligible"] = entry["clean_streak"] >= WARMUP_THRESHOLD
        entry["last_updated"] = _now_iso()
        entry["last_contract"] = contract
        entry["last_verdict"] = "clean"
        entry["history"].append({
            "date": entry["last_updated"],
            "contract": contract,
            "verdict": "clean",
            "source": "critic",
        })
        _trim_history(entry)
        _save_state(state)
        result = dict(entry)
    log_event(
        hook="accuracy",
        event="clean",
        file=contract,
        details={"area": area, "clean_streak": result["clean_streak"], "skip_eligible": result["skip_eligible"]},
    )
    return result


def record_failure(area: str, contract: str, source: str) -> dict:
    """
    Apply a bad-plan signal to one area. Resets clean_streak to 0 and
    flips skip_eligible to False. 'source' is one of:
        rejection · reviewer-divergence · critique-now-blocker · post-approval-journal
    Returns the updated area entry.
    """
    with _file_lock(state_path()):
        state = _load_state()
        entry = _ensure_area(state, area)
        entry["clean_streak"] = 0
        entry["skip_eligible"] = False
        entry["total_runs"] += 1
        entry["last_updated"] = _now_iso()
        entry["last_contract"] = contract
        entry["last_verdict"] = f"failed:{source}"
        entry["history"].append({
            "date": entry["last_updated"],
            "contract": contract,
            "verdict": "failed",
            "source": source,
        })
        _trim_history(entry)
        _save_state(state)
        result = dict(entry)
    log_event(
        hook="accuracy",
        event="failure",
        file=contract,
        details={"area": area, "source": source},
    )
    return result


def query(area: str) -> dict | None:
    state = _load_state()
    return state["areas"].get(area)


def dump_table() -> list[dict]:
    state = _load_state()
    rows = []
    for slug in sorted(state["areas"].keys()):
        e = state["areas"][slug]
        rows.append({
            "area": slug,
            "clean_streak": e.get("clean_streak", 0),
            "skip_eligible": e.get("skip_eligible", False),
            "total_runs": e.get("total_runs", 0),
            "last_updated": e.get("last_updated"),
            "last_verdict": e.get("last_verdict"),
            "last_contract": e.get("last_contract"),
        })
    return rows


def record_from_contract(contract_path: str, verdict_or_source: str, is_failure: bool) -> dict:
    """
    Convenience: derive areas from a contract and apply the same action to
    every matched area. 'verdict_or_source' is 'clean' (for success) or the
    failure source slug (rejection / reviewer-divergence / etc.).
    """
    path = Path(contract_path).expanduser()
    if not path.exists():
        return {"error": "contract-not-found", "path": str(path), "areas": []}
    areas = derive_areas(path)
    if not areas:
        return {"error": "no-files-to-touch-section", "path": str(path), "areas": []}
    results = {}
    for area in areas:
        if is_failure:
            results[area] = record_failure(area, str(path), verdict_or_source)
        else:
            results[area] = record_clean(area, str(path))
    return {"path": str(path), "areas": areas, "results": results}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("record-clean")
    pc.add_argument("area")
    pc.add_argument("contract")

    pf = sub.add_parser("record-failure")
    pf.add_argument("area")
    pf.add_argument("contract")
    pf.add_argument("source")

    pq = sub.add_parser("query")
    pq.add_argument("area")

    sub.add_parser("dump-table")

    pr = sub.add_parser("record-from-contract")
    pr.add_argument("contract")
    pr.add_argument("verdict_or_source", help="'clean' or a failure source slug")
    pr.add_argument("--failure", action="store_true", help="Treat verdict_or_source as a failure")

    args = p.parse_args(argv)

    if args.cmd == "record-clean":
        out = record_clean(args.area, args.contract)
    elif args.cmd == "record-failure":
        out = record_failure(args.area, args.contract, args.source)
    elif args.cmd == "query":
        out = query(args.area)
    elif args.cmd == "dump-table":
        out = dump_table()
    elif args.cmd == "record-from-contract":
        out = record_from_contract(args.contract, args.verdict_or_source, args.failure)
    else:
        p.error(f"unknown command: {args.cmd}")
        return 2

    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
