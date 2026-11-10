#!/usr/bin/env python3
"""
codegraph_shadow_report.py -- read-only report over the CodeGraph guard's measurement log.

Contract: .claude/concepts/2026-11-05-codegraph-hooks-redesign.md, command "Report the shadow", and
.claude/concepts/2026-11-09-codegraph-hooks-cutover.md (the ``enforced`` outcome).

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
none, as an older record does); a ``cli`` group is a turn the command-line route opened, which the transcript rule did not
see in the shadow era, so the text report labels it "explained (command-line route)".
Percentiles are nearest-rank: the value at rank ceil(q * n) of the sorted values.

TWO KINDS OF RECORD. A record written before the cut-over is a shadow record: its ``outcome`` is agree, shadow-more-open or
shadow-more-closed, and it pairs the live decision with the shadow one. A record written after it has ``outcome`` ``enforced``:
the guard decided from the transcript, so it carries no second decision and cannot tell a wrong block from a right one. The
shadow sections count only shadow records. The ``enforced`` section counts only enforced records: how many, the reasons
(main session and subagents apart), the share of gated calls that failed open on the transcript (the rollback number of the
cut-over contract's Q4), the blocks and the blocks followed by an identical retry, the blocks per tool, the transcript states
and the cost. A ``log-full`` line says when the 10 MB cap stopped the log: the report prints "measurement stopped at the 10 MB
cap at <ts>" from the first such line.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

LOG_RELATIVE = Path(".claude") / "logs" / "codegraph-shadow.jsonl"
OUTCOMES = ("agree", "shadow-more-open", "shadow-more-closed")  # the shadow-era outcomes
ENFORCED = "enforced"  # the outcome of a record written after the cut-over
RETRY_REASON = "retry-escape-used"
ROUTES = ("mcp", "cli")
#: Reasons that are not a decision about a source read: the gate had nothing to judge (no target, or only non-source targets).
NOT_GATED_REASONS = ("no-target", "non-source-target")
TRANSCRIPT_FAIL_OPEN_PREFIX = "fail-open:transcript-"
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
    if obj.get("outcome") in OUTCOMES + (ENFORCED,) and isinstance(obj.get("live_decision"), str):
        return "record", obj
    return "malformed", None


def _blocks_and_retries(records: list[dict]) -> tuple[int, int, dict, dict]:
    """(blocks, blocks followed by an identical retry, per-tool counts, the Q5 counts) over ``records``, in log order. A retry
    pairs with the next earlier unpaired block of the same (session, fp, prompt_key); one retry record pairs with one block."""
    blocks, retried_total = 0, 0
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
    return blocks, retried_total, by_tool, q5


def _with_rate(entry: dict) -> dict:
    rate = round(entry["retried"] / entry["blocks"], 4) if entry["blocks"] else None
    return {"blocks": entry["blocks"], "retried": entry["retried"], "retry_rate": rate}


def _enforced_section(records: list[dict]) -> dict:
    """The ``enforced`` section: only records written after the cut-over."""
    reasons = {"main": Counter(), "agent": Counter()}
    states: Counter = Counter()
    routes: Counter = Counter()
    ms: list[float] = []
    sessions = set()
    gated = transcript_fail_open = 0
    for r in records:
        sessions.add(_text(r.get("session")))
        reason = _text(r.get("live_reason"))
        reasons["agent" if r.get("agent") is True else "main"][reason] += 1
        states[_text(r.get("transcript_turn"))] += 1
        route = r.get("turn_route")
        routes[route if route in ("mcp", "cli", "agent") else "none"] += 1
        if reason not in NOT_GATED_REASONS:
            gated += 1
            if reason.startswith(TRANSCRIPT_FAIL_OPEN_PREFIX):
                transcript_fail_open += 1
        value = _number(r.get("shadow_ms"))
        if value is not None:
            ms.append(value)
    blocks, retried, by_tool, _q5 = _blocks_and_retries(records)
    return {
        "records": len(records),
        "sessions": len(sessions),
        "reasons": {side: dict(c.most_common()) for side, c in reasons.items()},
        "gated_calls": gated,
        "fail_open_transcript": transcript_fail_open,
        "fail_open_share": round(transcript_fail_open / gated, 4) if gated else None,
        "blocks": blocks,
        "blocks_retried": retried,
        "blocks_by_tool": {tool: _with_rate(entry) for tool, entry in sorted(by_tool.items())},
        "transcript_turn": dict(states.most_common()),
        "turn_route": dict(routes.most_common()),
        "shadow_ms": _summary(ms),
    }


def _iso(ts) -> str:
    """A log-full line's ``ts`` (epoch seconds) as an ISO 8601 UTC time; the raw value when it is not a number."""
    if isinstance(ts, (int, float)) and not isinstance(ts, bool):
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (OverflowError, OSError, ValueError):
            pass
    return str(ts)


def build_report(lines: Iterable[bytes]) -> dict:
    all_records: list[dict] = []
    malformed = torn = log_full = 0
    cap_ts = None
    for raw in lines:
        kind, obj = _parse(raw)
        if kind == "record":
            all_records.append(obj)  # type: ignore[arg-type]
        elif kind == "log-full":
            log_full += 1
            if cap_ts is None and obj is not None:
                cap_ts = obj.get("ts")
        elif kind == "torn":
            torn += 1
            malformed += 1
        elif kind == "malformed":
            malformed += 1
    records = [r for r in all_records if r["outcome"] != ENFORCED]  # the shadow sections count shadow-era records only
    enforced = [r for r in all_records if r["outcome"] == ENFORCED]

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

    blocks, retried_total, by_tool, q5 = _blocks_and_retries(records)
    session_seen_blocks = sum(1 for r in records if r["live_decision"] == "block" and r.get("session_seen") is True)

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
        "blocks_by_tool": {tool: _with_rate(entry) for tool, entry in sorted(by_tool.items())},
        "q5_read_source": _with_rate(q5),
        "session_seen_blocks": session_seen_blocks,
        "skipped_long_line": skipped,
        "shadow_ms": {"all": _summary(ms_all), "transcript_path": _summary(ms_transcript)},
        "malformed": malformed,
        "torn": torn,
        "log_full": log_full,
        "cap": {"stopped": log_full > 0, "ts": cap_ts},
        "enforced": _enforced_section(enforced),
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
    if report["records"] == 0 and report["enforced"]["records"] == 0:
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
    e = report["enforced"]
    out.append("")
    out.append("ENFORCED (records written after the cut-over; the guard decided from the transcript)")
    out.append(f"enforced records: {e['records']}   sessions: {e['sessions']}")
    for side in ("main", "agent"):
        pairs = ", ".join(f"{reason}: {n}" for reason, n in e["reasons"][side].items()) or "none"
        out.append(f"enforced reasons ({side}): {pairs}")
    share = e["fail_open_share"]
    out.append(f"gated calls: {e['gated_calls']}   failed open on the transcript (fail-open:transcript-*): "
               f"{e['fail_open_transcript']}   share: " + ("n/a" if share is None else "%.1f%%" % (share * 100))
               + " (the rollback rule of the cut-over contract is more than 10%)")
    out.append(f"enforced blocks: {e['blocks']}   followed by an identical retry (same session, fp, prompt_key): {e['blocks_retried']}")
    out.append("enforced blocks per tool:")
    for tool, entry in e["blocks_by_tool"].items():
        out.append(f"  {tool}: {entry['blocks']} blocks, {entry['retried']} retried, retry rate {_fmt(entry['retry_rate'])}")
    if not e["blocks_by_tool"]:
        out.append("  none")
    out.append("transcript states: " + (", ".join(f"{k}: {n}" for k, n in e["transcript_turn"].items()) or "none"))
    out.append("turn routes: " + (", ".join(f"{k}: {n}" for k, n in e["turn_route"].items()) or "none"))
    out.append(f"enforced cost (ms): n {e['shadow_ms']['n']}, p50 {_fmt(e['shadow_ms']['p50'])}, p95 {_fmt(e['shadow_ms']['p95'])}")
    out.append("a block the user judges wrong cannot be found here: an enforced record carries no second decision")
    if report["cap"]["stopped"]:
        out.append(f"measurement stopped at the 10 MB cap at {_iso(report['cap']['ts'])}")
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
