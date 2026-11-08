#!/usr/bin/env python3
"""
codegraph_shadow_report.py -- read-only report over the CodeGraph guard's measurement log.

Contract: .claude/concepts/2026-11-05-codegraph-hooks-redesign.md, command "Report the shadow".

    py -3 .claude/scripts/codegraph_shadow_report.py [--project <dir>] [--json]

Reads only ``<project>/.claude/logs/codegraph-shadow.jsonl`` (``--project`` defaults to CLAUDE_PROJECT_DIR, then the current
folder) and writes nothing. Exit 0 with the report; exit 2 when the log is missing or unreadable (never an empty "agree").
A zero-byte log is readable: it reports "no records".

EVERY COUNT IS A LOWER BOUND. The guard appends with one write and no lock; on Windows two concurrent appends can overwrite
each other unseen, and a cold transcript scan sees only the last 2 MB. Malformed lines (a torn write, garbage, an unknown
shape) are counted, never fatal. ``malformed`` includes ``torn`` (a line that starts like a record and stops short).

Pairing a block with its retry (Q5): the next later record with the same ``session``, ``fp`` and ``prompt_key`` whose live
decision is the retry escape. One retry record pairs with one block. A ``prompt_key`` of ``none`` only matches ``none``.
A shadow-more-closed row is also grouped by the record's ``marker_route`` (``mcp`` or ``cli``; ``none`` when the record has
none, as an older record does); a ``cli`` group is a turn the command-line route opened, which the transcript rule does not
see yet, so the text report labels it "explained (command-line route)".
Percentiles are nearest-rank: the value at rank ceil(q * n) of the sorted values.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

LOG_RELATIVE = Path(".claude") / "logs" / "codegraph-shadow.jsonl"
OUTCOMES = ("agree", "shadow-more-open", "shadow-more-closed")
RETRY_REASON = "retry-escape-used"
ROUTES = ("mcp", "cli")
NON_TRANSCRIPT_STATES = ("unknown:subagent", "unknown:no-transcript")  # no transcript was read: not the transcript path


def percentile(values: Iterable[float], q: float) -> float | None:
    """Nearest-rank percentile: the value at rank ceil(q * n) of the sorted values; None when there are none."""
    ordered = sorted(values)
    if not ordered:
        return None
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def _summary(values: list[float]) -> dict:
    return {"n": len(values), "p50": percentile(values, 0.5), "p95": percentile(values, 0.95)}


def _number(value) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _text(value, default: str = "none") -> str:
    return value if isinstance(value, str) and value else default


def _is_torn(text: str) -> bool:
    """A line that starts like a record and stops short of a closing brace (a write cut short, or the file's last line)."""
    stripped = text.strip()
    return stripped.startswith("{") and not stripped.endswith("}")


def _parse(raw: bytes) -> tuple[str, dict | None]:
    """('blank'|'record'|'log-full'|'malformed'|'torn', object)."""
    text = raw.decode("utf-8", errors="replace").strip("\r\n \t")
    if not text:
        return "blank", None
    try:
        obj = json.loads(text)
    except ValueError:
        return ("torn" if _is_torn(text) else "malformed"), None
    if not isinstance(obj, dict):
        return "malformed", None
    if obj.get("event") == "log-full":
        return "log-full", obj
    if obj.get("outcome") in OUTCOMES and isinstance(obj.get("live_decision"), str):
        return "record", obj
    return "malformed", None


def build_report(lines: Iterable[bytes]) -> dict:
    records: list[dict] = []
    malformed = torn = log_full = 0
    for raw in lines:
        kind, obj = _parse(raw)
        if kind == "record":
            records.append(obj)  # type: ignore[arg-type]
        elif kind == "log-full":
            log_full += 1
        elif kind == "torn":
            torn += 1
            malformed += 1
        elif kind == "malformed":
            malformed += 1

    outcomes = {name: 0 for name in OUTCOMES}
    more_closed: Counter = Counter()
    live_reasons = {"main": Counter(), "agent": Counter()}
    shadow_reasons = {"main": Counter(), "agent": Counter()}
    skipped = 0
    ms_all: list[float] = []
    ms_transcript: list[float] = []
    sessions = set()

    for r in records:
        outcomes[r["outcome"]] += 1
        sessions.add(_text(r.get("session")))
        side = "agent" if r.get("agent") is True else "main"
        live_reasons[side][_text(r.get("live_reason"))] += 1
        shadow_reasons[side][_text(r.get("shadow_reason"))] += 1
        if r["outcome"] == "shadow-more-closed":
            route = r.get("marker_route")
            more_closed[(_text(r.get("live_reason")), _text(r.get("transcript_turn")),
                         route if route in ROUTES else "none")] += 1
        skipped_here = r.get("skipped_long_line")
        if isinstance(skipped_here, int) and not isinstance(skipped_here, bool) and skipped_here > 0:
            skipped += skipped_here
        ms = _number(r.get("shadow_ms"))
        if ms is not None:
            ms_all.append(ms)
            if _text(r.get("transcript_turn")) not in NON_TRANSCRIPT_STATES:
                ms_transcript.append(ms)

    blocks, retried_total, session_seen_blocks = 0, 0, 0
    by_tool: dict[str, dict] = {}
    q5 = {"blocks": 0, "retried": 0}
    open_blocks: dict[tuple, list[tuple[str, bool]]] = {}  # (session, fp, prompt_key) -> unpaired blocks (tool, is Q5), in order
    paired: list[tuple[str, bool]] = []
    for r in records:
        key = (_text(r.get("session")), _text(r.get("fp")), _text(r.get("prompt_key")))
        if r["live_decision"] == "block":
            tool = _text(r.get("tool"), "unknown")
            is_q5 = tool == "Read" and r.get("live_reason") == "source-target"
            blocks += 1
            if r.get("session_seen") is True:
                session_seen_blocks += 1
            by_tool.setdefault(tool, {"blocks": 0, "retried": 0})["blocks"] += 1
            if is_q5:
                q5["blocks"] += 1
            open_blocks.setdefault(key, []).append((tool, is_q5))
        elif r.get("live_reason") == RETRY_REASON and open_blocks.get(key):
            paired.append(open_blocks[key].pop(0))
    for tool, is_q5 in paired:
        retried_total += 1
        by_tool[tool]["retried"] += 1
        if is_q5:
            q5["retried"] += 1

    def with_rate(entry: dict) -> dict:
        rate = round(entry["retried"] / entry["blocks"], 4) if entry["blocks"] else None
        return {"blocks": entry["blocks"], "retried": entry["retried"], "retry_rate": rate}

    return {
        "lower_bound": True,
        "records": len(records),
        "sessions": len(sessions),
        "outcomes": outcomes,
        "more_closed": [{"live_reason": lr, "transcript_turn": tt, "marker_route": mr, "count": n}
                        for (lr, tt, mr), n in sorted(more_closed.items(), key=lambda kv: (-kv[1], kv[0]))],
        "live_reasons": {side: dict(c.most_common()) for side, c in live_reasons.items()},
        "shadow_reasons": {side: dict(c.most_common()) for side, c in shadow_reasons.items()},
        "blocks": blocks,
        "blocks_retried": retried_total,
        "blocks_by_tool": {tool: with_rate(entry) for tool, entry in sorted(by_tool.items())},
        "q5_read_source": with_rate(q5),
        "session_seen_blocks": session_seen_blocks,
        "skipped_long_line": skipped,
        "shadow_ms": {"all": _summary(ms_all), "transcript_path": _summary(ms_transcript)},
        "malformed": malformed,
        "torn": torn,
        "log_full": log_full,
    }


def read_log(path: Path) -> list[bytes]:
    """The log's lines as bytes (split on LF only). Raises OSError when it is missing or unreadable."""
    with open(path, "rb") as fh:
        data = fh.read()
    return data.split(b"\n")


def _fmt(value) -> str:
    return "n/a" if value is None else ("%g" % value)


def render_text(report: dict) -> str:
    out = [f"CodeGraph shadow report -- {report.get('log', '')}",
           "Every count below is a lower bound (appends are lock-free; a cold scan sees only 2 MB)."]
    if report["records"] == 0:
        out.append("no records in the log")
    out.append(f"records: {report['records']}   sessions: {report['sessions']}")
    out.append("outcomes: " + "   ".join(f"{name}: {report['outcomes'][name]}" for name in OUTCOMES))
    out.append("shadow-more-closed by (live_reason, transcript_turn, marker_route):")
    out.extend([f"  {row['live_reason']} / {row['transcript_turn']} / {row.get('marker_route', 'none')}: {row['count']}"
                + (" -- explained (command-line route)" if row.get("marker_route") == "cli" else "")
                for row in report["more_closed"]] or ["  none"])
    for title, key in (("live reasons", "live_reasons"), ("shadow reasons", "shadow_reasons")):
        for side in ("main", "agent"):
            pairs = ", ".join(f"{reason}: {n}" for reason, n in report[key][side].items()) or "none"
            out.append(f"{title} ({side}): {pairs}")
    out.append(f"blocks: {report['blocks']}   followed by an identical retry (same session, fp, prompt_key): {report['blocks_retried']}")
    out.append("blocks per tool:")
    for tool, e in report["blocks_by_tool"].items():
        out.append(f"  {tool}: {e['blocks']} blocks, {e['retried']} retried, retry rate {_fmt(e['retry_rate'])}")
    if not report["blocks_by_tool"]:
        out.append("  none")
    q5 = report["q5_read_source"]
    out.append(f"Q5 Read-of-source blocks: {q5['blocks']}, retried {q5['retried']}, retry rate {_fmt(q5['retry_rate'])} "
               "(the criterion is more than 0.5 over the Q2 sample)")
    out.append(f"blocks a per-session gate would have avoided (session_seen): {report['session_seen_blocks']}")
    out.append(f"skipped_long_line total: {report['skipped_long_line']}")
    for label, key in (("all records", "all"), ("transcript path only", "transcript_path")):
        s = report["shadow_ms"][key]
        out.append(f"shadow_ms ({label}): n {s['n']}, p50 {_fmt(s['p50'])}, p95 {_fmt(s['p95'])}")
    out.append(f"malformed lines: {report['malformed']} (torn: {report['torn']})   log-full lines: {report['log_full']}")
    return "\n".join(out) + "\n"


def resolve_project(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env) if env else Path.cwd()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only report over <project>/.claude/logs/codegraph-shadow.jsonl")
    parser.add_argument("--project", help="project folder (default: CLAUDE_PROJECT_DIR, then the current folder)")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)

    log_path = resolve_project(args.project) / LOG_RELATIVE
    try:
        lines = read_log(log_path)
    except OSError as exc:
        print(f"codegraph_shadow_report: cannot read {log_path}: {exc}", file=sys.stderr)
        return 2
    report = build_report(lines)
    report["log"] = str(log_path)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        sys.stdout.write(render_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
