#!/usr/bin/env python3
"""
bench_codegraph_guard.py -- cost per call of the CodeGraph guard, old design against new
(contract 2026-11-05-codegraph-hooks-redesign, block 3).

    py -3 .claude/hooks/tests/bench_codegraph_guard.py [--runs 30] [--old-ref origin/master] [--sizes 1,10,50]
                                                       [--json out.json] [--keep]
    py -3 .claude/hooks/tests/bench_codegraph_guard.py --reset-budget [--runs 30]

``--reset-budget`` (issue #295) measures the Connection notice against its time budget instead; see ``reset_budget``. Since the
cut-over of issue #262 the "new" side is the guard's prompt row (``codegraph-first-guard.py notice``, which took over the notice from
the reset hook) and the baseline is the 0.16.1 reset hook. It never builds the #259 ``Workspace`` and must be run from a Claude
Code session.

Not a test (no ``test_`` prefix): it measures, it asserts nothing about speed. It runs every case ``--runs`` times, each run a
fresh ``python <hook>`` process fed the hook payload on stdin, timed from the parent (interpreter start included, as the host
pays it). Runs are interleaved round by round across all cases, so a slow minute hits old and new alike.

  old   the #259 guard, reset hook and tracker, read with ``git show <old-ref>:<path>`` (default origin/master; the local
        ``master`` branch can be stale) into a temp folder, with the helpers of the same ref
  new   this working tree's guard, copied into a second temp folder (the tracker and the reset hook are disabled since the cut-over
        of issue #262: the new side runs the guard's prompt row where the old side runs the reset hook and the tracker)

Everything the hooks touch lives under one private scratch folder: TMP/TEMP/TMPDIR (the OLD design's Session folders and the
reset hook's pruner never see the real temp folder), LOCALAPPDATA and XDG_CACHE_HOME (and HOME) pointing at ``<scratch>/home``
(the NEW design keeps its Session folders under the Per-user session parent, ``<base>/auto-improve-codegraph``, created 0700
with the same helper the test fixtures use; the bench NEVER writes into the real %LOCALAPPDATA% or ~/.cache),
USERPROFILE/CLAUDE_CONFIG_DIR (so no real settings enable or disable the server), and a throwaway project with a Project index
and a configured server. The folder is removed at the end unless ``--keep``. The OLD design's gate is its Turn marker; the NEW
design's gate is the transcript: "marker present" means a transcript whose turn is open, "marker absent" one whose last entry is
a human prompt.

--old-ref MUST name a PRE-SHADOW ref (for example c8653e3, the #259 guard): the default origin/master now contains the shadow
(and the Per-user session parent), so ``_check_old_is_259`` stops a plain run before it starts. The OLD design keeps its
Session folders in the temp folder; the NEW design (this working tree) keeps them under the Per-user session parent.

Cases (guard): allowlisted target; gated target with the gate open; gated target with the gate closed (a block);
new only: gate open with the transcript open, at each size, warm and cold cursor. Also the reset hook and the tracker (old side)
and the guard's prompt row (new side).
The plain guard cases carry a 64 KB transcript, as an early session would. A case is MEASURED when every one of its runs
exited with the expected code; the transcript states the shadow reached are listed beside it (a cold scan that runs out of the
50 ms budget shows as unknown:time-exceeded, not as a failure).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _addon_fixture as af  # noqa: E402  (session_parent / session_folder / write_marker; import only registers an atexit cleanup)

REPO_ROOT = Path(__file__).resolve().parents[3]
GUARD_REL = ".claude/addons/codegraph/hooks/codegraph-first-guard.py"
RESET_REL = ".claude/addons/codegraph/hooks/codegraph-turn-reset.py"
TRACKER_REL = ".claude/addons/codegraph/hooks/codegraph-turn-tracker.py"
HELPER_RELS = (".claude/hooks/_error_log.py", ".claude/hooks/_project_paths.py")
SESSION_PREFIX = "auto-improve-codegraph-"
MB = 1024 * 1024
SMALL_TRANSCRIPT_BYTES = 64 * 1024
#: The baseline of ``--reset-budget``: the 0.16.1 release, pinned (never origin/master or HEAD, which move).
RESET_BASELINE_REF = "db61fd7"
T1_MARGIN_MS = 150.0   # T1: subprocess p50 of the reset hook <= the baseline's p50 + this
T2_P95_MS = 150.0      # T2: in-process notice-section p95 <= this
T2_RUNS = 20
CALLS_PER_TURN = (5, 10, 20, 50)  # the Q2 "median calls per turn" is unknown until the real sample; shown for these


# --------------------------------------------------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------------------------------------------------
def percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank: the value at rank ceil(q * n) of the sorted values (the same rule as codegraph_shadow_report.py)."""
    ordered = sorted(values)
    if not ordered:
        return None
    return ordered[min(max(1, math.ceil(q * len(ordered))), len(ordered)) - 1]


def summarize(values: list[float]) -> dict:
    return {"n": len(values), "p50": percentile(values, 0.5), "p95": percentile(values, 0.95),
            "min": min(values) if values else None, "max": max(values) if values else None}


# --------------------------------------------------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------------------------------------------------
def _line(obj: dict) -> bytes:
    return json.dumps(obj, separators=(",", ":")).encode("utf-8") + b"\n"


def _filler_cycle() -> bytes:
    """About 3 KB of ordinary transcript: an assistant text, an assistant tool use, and a user tool result (the one that
    holds ``"user"`` and so is parsed by the guard)."""
    pad = "x" * 900
    return (_line({"type": "assistant", "uuid": "a1", "message": {"role": "assistant", "content": [{"type": "text", "text": pad}]}})
            + _line({"type": "assistant", "uuid": "a2", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": pad[:600]}}]}})
            + _line({"type": "user", "uuid": "u1", "sourceToolAssistantUUID": "a2", "toolUseResult": {"stdout": pad[:200]},
                     "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": pad}]}}))


def write_transcript(path: Path, size: int) -> None:
    """A transcript of about ``size`` bytes whose current turn is OPEN: a human prompt then a CodeGraph tool use sit
    ``min(size / 2, 1 MB)`` before the end, so even a cold scan (the last 2 MB) finds the boundary."""
    cycle = _filler_cycle()
    tail = min(size // 2, MB)
    head = size - tail
    boundary = (_line({"type": "user", "uuid": "p1", "promptSource": "sdk", "message": {"role": "user", "content": "investigate the guard"}})
                + _line({"type": "assistant", "uuid": "a9", "message": {"role": "assistant", "content": [
                    {"type": "tool_use", "id": "t9", "name": "mcp__codegraph__bench", "input": {"query": "guard"}}]}}))
    with open(path, "wb") as fh:
        for part in (head, tail):
            for _ in range(max(1, part // len(cycle))):
                fh.write(cycle)
            if part is head:
                fh.write(boundary)


def write_closed_transcript(path: Path, size: int) -> None:
    """A transcript of about ``size`` bytes whose last entry is a human prompt: the turn is CLOSED (the new guard blocks)."""
    cycle = _filler_cycle()
    with open(path, "wb") as fh:
        for _ in range(max(1, size // len(cycle))):
            fh.write(cycle)
        fh.write(_line({"type": "user", "uuid": "p2", "promptSource": "sdk", "message": {"role": "user", "content": "now this"}}))


@dataclass
class Case:
    key: str
    label: str
    design: str                      # old | new | new-nolog | floor
    hook: str                        # guard | reset | tracker | python
    argv: list[str]
    cwd: str
    env: dict
    payload: bytes
    expected_exit: int
    session: str = ""
    prepare: Callable[[], None] = field(default=lambda: None)
    prime: bool = False              # one untimed run first (warm cursor, cached availability, bytecode of the helpers)
    logs: bool = False               # the case writes Shadow records into the project log
    transcript_mb: float | None = None
    cursor: str = ""                 # warm | cold | ""
    times: list[float] = field(default_factory=list)
    exits: list[int] = field(default_factory=list)
    stderr_sample: str = ""


def make_project(project: Path, with_claude: bool) -> None:
    """A throwaway project with a Project index and a configured CodeGraph server."""
    (project / "src").mkdir(parents=True, exist_ok=True)
    (project / "src" / "app.py").write_text("print('x')\n", encoding="utf-8")
    (project / "README.md").write_text("# bench\n", encoding="utf-8")
    (project / ".codegraph").mkdir(exist_ok=True)
    (project / ".codegraph" / "codegraph.db").write_bytes(b"SQLite format 3\x00")
    (project / ".mcp.json").write_text(json.dumps({"mcpServers": {"codegraph": {"command": "codegraph", "args": ["serve", "--mcp"]}}}),
                                       encoding="utf-8")
    if with_claude:
        (project / ".claude").mkdir(exist_ok=True)


def isolated_env(tmp: Path, home: Path, project: Path) -> dict:
    """The environment of a child process: private temp folder, home and config dir, this project."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_")}
    env.update({"CLAUDE_PROJECT_DIR": str(project), "CLAUDE_CONFIG_DIR": str(home / ".claude"),
                "TMP": str(tmp), "TEMP": str(tmp), "TMPDIR": str(tmp), "USERPROFILE": str(home), "HOME": str(home)})
    return env


class Workspace:
    def __init__(self, root: Path, old_ref: str, sizes: list[int]) -> None:
        self.root = root
        self.old_ref = old_ref
        self.sizes = sizes
        self.tmp = root / "tmp"
        self.home = root / "home"
        self.transcripts = root / "transcripts"
        self.project = root / "project"
        self.project_nolog = root / "project_nolog"
        for folder in (self.tmp, self.home / ".claude", self.transcripts):
            folder.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":  # the base is <home>/AppData/Local; af.session_parent creates it (0700) but not its parent
            (self.home / "AppData").mkdir(exist_ok=True)
        self.parent = af.session_parent(self.home)  # the Per-user session parent inside the scratch home (0700 where applicable)
        for project, with_claude in ((self.project, True), (self.project_nolog, False)):
            self._make_project(project, with_claude)
        self.old_dir = self._install(root / "old_hooks", from_ref=old_ref)
        self.new_dir = self._install(root / "new_hooks", from_ref=None)
        self._check_old_is_259()

    # -- fixtures ------------------------------------------------------------------------------------------------
    @staticmethod
    def _make_project(project: Path, with_claude: bool) -> None:
        make_project(project, with_claude)

    def _install(self, target: Path, from_ref: str | None) -> Path:
        target.mkdir(parents=True, exist_ok=True)
        for rel in (GUARD_REL, RESET_REL, TRACKER_REL) + HELPER_RELS:
            if from_ref is None:
                data = (REPO_ROOT / rel).read_bytes()
            else:
                data = subprocess.run(["git", "show", f"{from_ref}:{rel}"], cwd=REPO_ROOT, capture_output=True, check=True).stdout
            (target / Path(rel).name).write_bytes(data)
        return target

    def _check_old_is_259(self) -> None:
        old = (self.old_dir / Path(GUARD_REL).name).read_text(encoding="utf-8")
        if "SESSION_PREFIX" not in old or "shadow_section" in old:
            sys.exit(f"{self.old_ref}: the guard is not the #259 guard (no Session folder, or it already holds the shadow)")

    # -- environment of the child processes ------------------------------------------------------------------------
    def env(self, project: Path) -> dict:
        """The child environment. Both the temp folder (the OLD design's Session folders) and the per-user base
        (LOCALAPPDATA / XDG_CACHE_HOME, the NEW design's) point inside the scratch area, so a run never writes into the
        real %LOCALAPPDATA% or ~/.cache."""
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_")}
        env.update({"CLAUDE_PROJECT_DIR": str(project), "CLAUDE_CONFIG_DIR": str(self.home / ".claude"),
                    "TMP": str(self.tmp), "TEMP": str(self.tmp), "TMPDIR": str(self.tmp),
                    "USERPROFILE": str(self.home), "HOME": str(self.home),
                    "LOCALAPPDATA": str(self.home / "AppData" / "Local"), "XDG_CACHE_HOME": str(self.home / ".cache")})
        return env

    def folder(self, session: str, design: str) -> Path:
        """The Session folder by design: ``old`` (the #259 guard) keeps it in the temp folder; every other design (new,
        new-nolog) keeps it under the Per-user session parent inside the scratch home."""
        if design == "old":
            return self.tmp / (SESSION_PREFIX + session)
        return af.session_folder(self.parent, session)

    def put_marker_file(self, session: str, design: str) -> None:
        """The Turn marker as the tracker of that design writes it (the new one is stamped: writer + session)."""
        if design == "old":
            folder = self.folder(session, design)
            folder.mkdir(exist_ok=True)
            (folder / "turn.json").write_text('{"ts":1,"tool":"mcp__codegraph__bench","summary":"","pid":1}\n')
        else:
            af.write_marker(self.parent, session, tool="mcp__codegraph__bench")

    # -- cases -------------------------------------------------------------------------------------------------------
    def cases(self) -> list[Case]:
        out: list[Case] = []
        small = self.transcripts / "small.jsonl"
        write_transcript(small, SMALL_TRANSCRIPT_BYTES)
        closed = self.transcripts / "closed.jsonl"
        write_closed_transcript(closed, SMALL_TRANSCRIPT_BYTES)
        big: dict[int, Path] = {}
        for mb in self.sizes:
            big[mb] = self.transcripts / f"t{mb}.jsonl"
            write_transcript(big[mb], mb * MB)

        def guard_payload(session: str, project: Path, target: str, transcript: Path) -> bytes:
            return json.dumps({"session_id": session, "cwd": str(project), "hook_event_name": "PreToolUse", "tool_name": "Read",
                               "tool_input": {"file_path": str(project / target)}, "transcript_path": str(transcript),
                               "prompt_id": "bench-prompt"}).encode("utf-8")

        def put_marker(session: str, design: str) -> Callable[[], None]:
            def go() -> None:
                self.put_marker_file(session, design)
            return go

        def drop_tickets(session: str, design: str) -> Callable[[], None]:
            def go() -> None:
                for f in self.folder(session, design).glob("ticket-*"):
                    f.unlink()
            return go

        def drop_cursor(session: str, design: str) -> Callable[[], None]:
            def go() -> None:
                (self.folder(session, design) / "transcript-cursor.json").unlink(missing_ok=True)
            return go

        def guard_case(design: str, key: str, label: str, target: str, expected: int, prepare, *, project: Path | None = None,
                       prime: bool = False, transcript: Path = small, mb: float | None = None, cursor: str = "") -> Case:
            project = project or self.project
            hooks = self.old_dir if design == "old" else self.new_dir
            session = f"bench-{design}-{key}"
            return Case(key=f"{design}:{key}", label=label, design=design, hook="guard",
                        argv=[sys.executable, str(hooks / Path(GUARD_REL).name)], cwd=str(project), env=self.env(project),
                        payload=guard_payload(session, project, target, transcript), expected_exit=expected, session=session,
                        prepare=prepare, prime=prime, logs=(design == "new" and project is self.project),
                        transcript_mb=mb, cursor=cursor)

        for design in ("old", "new"):
            s_marker, s_block = f"bench-{design}-marker-present", f"bench-{design}-marker-absent"
            out.append(guard_case(design, "allowlisted", "allowlisted target (README.md), no marker", "README.md", 0, lambda: None))
            if design == "old":
                put_marker(s_marker, design)()  # the old gate is its Turn marker; the new gate is the transcript
            out.append(guard_case(design, "marker-present", "gated target (src/app.py), gate open (old: marker, new: open transcript)",
                                  "src/app.py", 0, lambda: None))
            out.append(guard_case(design, "marker-absent", "gated target (src/app.py), gate closed: block", "src/app.py", 2,
                                  drop_tickets(s_block, design), prime=True, transcript=(closed if design == "new" else small)))
        # new, shadow cost removed (no <project>/.claude, so no log is written): splits the G-1 saving from the shadow's cost
        for key, label, target, expected in (("allowlisted", "allowlisted target (README.md), no marker", "README.md", 0),
                                             ("marker-present", "gated target (src/app.py), marker present", "src/app.py", 0)):
            case = guard_case("new", key, label, target, expected, lambda: None, project=self.project_nolog)
            case.design, case.key, case.session = "new-nolog", f"new-nolog:{key}", f"bench-new-nolog-{key}"
            case.payload = guard_payload(case.session, self.project_nolog, target, small)
            out.append(case)
        for mb in self.sizes:
            for cursor in ("warm", "cold"):
                key = f"transcript-{mb}mb-{cursor}"
                session = f"bench-new-{key}"
                out.append(guard_case("new", key, f"gate open, transcript open, {mb} MB, {cursor} cursor", "src/app.py", 0,
                                      drop_cursor(session, "new") if cursor == "cold" else (lambda: None),
                                      prime=(cursor == "warm"), transcript=big[mb], mb=mb, cursor=cursor))
        # the guard's prompt row (new): it took over the reset hook's two duties
        s_notice = "bench-new-notice"
        out.append(Case(key="new:notice", label="guard prompt row start (UserPromptSubmit, argument notice)", design="new", hook="reset",
                        argv=[sys.executable, str(self.new_dir / Path(GUARD_REL).name), "notice"], cwd=str(self.project),
                        env=self.env(self.project),
                        payload=json.dumps({"session_id": s_notice, "cwd": str(self.project), "hook_event_name": "UserPromptSubmit",
                                            "prompt": "hello", "prompt_id": "bench-prompt"}).encode("utf-8"),
                        expected_exit=0, session=s_notice, prime=True))
        # reset hook and tracker, the old design only (disabled since the cut-over)
        for design in ("old",):
            hooks = self.old_dir
            s_reset, s_track = f"bench-{design}-reset", f"bench-{design}-tracker"

            def reset_prepare(session=s_reset, design=design) -> None:
                self.put_marker_file(session, design)
                folder = self.folder(session, design)
                (folder / ("ticket-" + "0" * 64)).write_text("{}\n")
            out.append(Case(key=f"{design}:reset", label="reset hook start (UserPromptSubmit)", design=design, hook="reset",
                            argv=[sys.executable, str(hooks / Path(RESET_REL).name)], cwd=str(self.project), env=self.env(self.project),
                            payload=json.dumps({"session_id": s_reset, "cwd": str(self.project), "hook_event_name": "UserPromptSubmit",
                                                "prompt": "hello", "prompt_id": "bench-prompt"}).encode("utf-8"),
                            expected_exit=0, session=s_reset, prepare=reset_prepare, prime=True))
            out.append(Case(key=f"{design}:tracker", label="tracker start (PostToolUse mcp__codegraph__*)", design=design, hook="tracker",
                            argv=[sys.executable, str(hooks / Path(TRACKER_REL).name)], cwd=str(self.project), env=self.env(self.project),
                            payload=json.dumps({"session_id": s_track, "cwd": str(self.project), "hook_event_name": "PostToolUse",
                                                "tool_name": "mcp__codegraph__bench",
                                                "tool_input": {"query": "guard"}}).encode("utf-8"),
                            expected_exit=0, session=s_track, prime=True))
        out.append(Case(key="floor:python", label="python start, no imports (floor)", design="floor", hook="python",
                        argv=[sys.executable, "-c", "pass"], cwd=str(self.project), env=self.env(self.project), payload=b"",
                        expected_exit=0))
        return out

    # -- log ---------------------------------------------------------------------------------------------------------
    def shadow_records(self) -> dict[str, list[dict]]:
        """Shadow records of the main project log, grouped by the 12-hex session hash."""
        path = self.project / ".claude" / "logs" / "codegraph-shadow.jsonl"
        grouped: dict[str, list[dict]] = {}
        if not path.is_file():
            return grouped
        for raw in path.read_bytes().split(b"\n"):
            try:
                obj = json.loads(raw)
            except ValueError:
                continue
            if isinstance(obj, dict) and "session" in obj:
                grouped.setdefault(obj["session"], []).append(obj)
        return grouped


# --------------------------------------------------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------------------------------------------------
def run_once(case: Case) -> tuple[float, int, str]:
    start = time.perf_counter()
    proc = subprocess.run(case.argv, input=case.payload, capture_output=True, env=case.env, cwd=case.cwd)
    elapsed = (time.perf_counter() - start) * 1000.0
    return elapsed, proc.returncode, proc.stderr.decode("utf-8", "replace")[:300]


def run_all(ws: Workspace, runs: int) -> list[Case]:
    cases = ws.cases()
    for case in cases:
        if case.prime:
            case.prepare()
            _t, code, err = run_once(case)
            if code != case.expected_exit:
                case.stderr_sample = f"prime run exited {code}: {err}"
    for round_no in range(runs):
        order = cases[round_no % len(cases):] + cases[:round_no % len(cases)]  # rotate the start so no case always runs first
        for case in order:
            case.prepare()
            elapsed, code, err = run_once(case)
            case.times.append(elapsed)
            case.exits.append(code)
            if code != case.expected_exit and not case.stderr_sample:
                case.stderr_sample = f"run {round_no} exited {code}: {err}"
    return cases


def _hash(session: str) -> str:
    return hashlib.sha256(session.encode("utf-8")).hexdigest()[:12]


def collect(ws: Workspace, cases: list[Case], runs: int) -> list[dict]:
    records = ws.shadow_records()
    rows = []
    for case in cases:
        measured = len(case.times) == runs and all(code == case.expected_exit for code in case.exits)
        row = {"key": case.key, "label": case.label, "design": case.design, "hook": case.hook, "runs": len(case.times),
               "expected_exit": case.expected_exit, "exit_codes": dict(Counter(case.exits)), "measured": measured,
               "wall_ms": summarize(case.times), "transcript_mb": case.transcript_mb, "cursor": case.cursor,
               "stderr_sample": case.stderr_sample}
        if case.logs:
            mine = records.get(_hash(case.session), [])
            if case.prime and len(mine) > runs:
                mine = mine[len(mine) - runs:]  # the untimed priming run wrote the first record: leave it out
            ms = [r["shadow_ms"] for r in mine if isinstance(r.get("shadow_ms"), (int, float))]
            row["shadow"] = {"records": len(mine), "states": dict(Counter(r.get("transcript_turn") for r in mine)),
                             "live_reasons": dict(Counter(r.get("live_reason") for r in mine)),
                             "shadow_ms": summarize([float(x) for x in ms]),
                             "bytes_read": summarize([float(r["bytes_read"]) for r in mine if isinstance(r.get("bytes_read"), int)])}
        rows.append(row)
    return rows


# --------------------------------------------------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------------------------------------------------
def _f(value) -> str:
    return "n/a" if value is None else f"{value:.1f}"


def _row(rows: list[dict], key: str) -> dict | None:
    return next((r for r in rows if r["key"] == key), None)


def deltas(rows: list[dict]) -> list[dict]:
    """old -> new on the allowlisted and marker-present cases, split into the G-1 saving (old -> new with no log) and the
    shadow's added cost (new with no log -> new). p50 and p95 are differenced separately (they do not add up exactly)."""
    out = []
    for name, label in (("allowlisted", "allowlisted target"), ("marker-present", "gated target, marker present")):
        old, nolog, new = _row(rows, f"old:{name}"), _row(rows, f"new-nolog:{name}"), _row(rows, f"new:{name}")
        if not (old and nolog and new):
            continue
        entry = {"case": label}
        for q in ("p50", "p95"):
            o, n0, n1 = old["wall_ms"][q], nolog["wall_ms"][q], new["wall_ms"][q]
            entry[q] = {"old": o, "new_no_log": n0, "new": n1, "total": n1 - o, "g1_saving": n0 - o, "shadow_added": n1 - n0}
        out.append(entry)
    return out


def per_turn(rows: list[dict]) -> dict:
    """Q2's comparison. The old per-turn cost of the reset and tracker starts is p50(reset) + p50(tracker) (the tracker fires
    once per CodeGraph call, at least once in a turn that opens: one start is a FLOOR of the old cost). Amortised over c guard
    calls per turn it is (R + T) / c per call; the criterion needs the transcript path's p95 shadow_ms at or under that."""
    reset, tracker = _row(rows, "old:reset"), _row(rows, "old:tracker")
    base = _row(rows, "new-nolog:marker-present")
    if not (reset and tracker):
        return {}
    rt = reset["wall_ms"]["p50"] + tracker["wall_ms"]["p50"]
    cases = []
    for row in rows:
        if row["design"] != "new" or row.get("transcript_mb") is None:
            continue
        p95 = row.get("shadow", {}).get("shadow_ms", {}).get("p95")
        extra = row["wall_ms"]["p50"] - base["wall_ms"]["p50"] if base else None
        cases.append({"case": row["label"], "shadow_ms_p95": p95, "process_extra_p50": extra,
                      "max_calls_per_turn_for_criterion": (rt / p95) if p95 else None,
                      "by_calls_per_turn": {str(c): {"budget_ms_per_call": rt / c,
                                                     "criterion_met": (p95 is not None and p95 <= rt / c),
                                                     "turn_cost_of_transcript_path_ms": (extra * c if extra is not None else None)}
                                            for c in CALLS_PER_TURN}})
    return {"old_reset_p50": reset["wall_ms"]["p50"], "old_tracker_p50": tracker["wall_ms"]["p50"], "old_per_turn_ms": rt,
            "calls_per_turn": list(CALLS_PER_TURN), "cases": cases}


def environment(old_ref: str) -> dict:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
    return {"python": platform.python_version(), "implementation": platform.python_implementation(), "os": platform.platform(),
            "machine": platform.machine(), "processor": platform.processor(), "cpu_count": os.cpu_count(),
            "old_ref": old_ref, "old_sha": git("rev-parse", "--short", old_ref), "new_sha": git("rev-parse", "--short", "HEAD"),
            "new_dirty": bool(git("status", "--porcelain", "--", ".claude/addons/codegraph", ".claude/hooks")),
            "date": time.strftime("%Y-%m-%d")}


def render_markdown(result: dict) -> str:
    env, rows = result["environment"], result["rows"]
    out = [f"Python {env['python']} ({env['implementation']}), {env['os']}, {env['machine']} / {env['processor']}, "
           f"{env['cpu_count']} logical CPUs. old = {env['old_ref']} @ {env['old_sha']}, new = this branch @ {env['new_sha']}"
           f"{' (working tree has uncommitted hook changes)' if env['new_dirty'] else ''}. {result['runs']} fresh-process runs "
           "per case, wall clock from the parent (interpreter start included), ms.", "",
           "| Case | Design | Hook | Runs | p50 | p95 | in-process shadow_ms p50 / p95 | Transcript states reached | Measured |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        sh = r.get("shadow")
        shadow = f"{_f(sh['shadow_ms']['p50'])} / {_f(sh['shadow_ms']['p95'])}" if sh and sh["shadow_ms"]["n"] else ""
        states = ", ".join(f"{k} {v}" for k, v in sh["states"].items()) if sh else ""
        out.append(f"| {r['label']} | {r['design']} | {r['hook']} | {r['runs']} | {_f(r['wall_ms']['p50'])} | {_f(r['wall_ms']['p95'])} "
                   f"| {shadow} | {states} | {'yes' if r['measured'] else 'NO'} |")
    out += ["", "Old to new on the common cases (ms; p50 and p95 differenced separately). Total = new - old. G-1 saving = new with no "
            "log (no `<project>/.claude`, so no shadow record) - old, negative is a saving. Shadow added = new - new with no log "
            "(transcript read and log append).", "",
            "| Case | Stat | old | new, no log | new | Total | G-1 saving | Shadow added |", "|---|---|---|---|---|---|---|---|"]
    for d in result["deltas"]:
        for q in ("p50", "p95"):
            x = d[q]
            out.append(f"| {d['case']} | {q} | {_f(x['old'])} | {_f(x['new_no_log'])} | {_f(x['new'])} | {x['total']:+.1f} "
                       f"| {x['g1_saving']:+.1f} | {x['shadow_added']:+.1f} |")
    pt = result["per_turn"]
    if pt:
        out += ["", f"Per-turn comparison (Q2). Old per-turn cost of one reset start plus one tracker start (a floor: the tracker "
                f"fires on every CodeGraph call) = {_f(pt['old_reset_p50'])} + {_f(pt['old_tracker_p50'])} = {_f(pt['old_per_turn_ms'])} ms. "
                "Criterion: the transcript path's p95 shadow_ms <= that cost / median guard calls per turn (c). The real c comes "
                "from the cut-over sample; shown for c = " + ", ".join(map(str, pt["calls_per_turn"])) + ".", "",
                "On Windows the guard's time.monotonic() ticks about every 15.6 ms, so shadow_ms is quantised to that step and a "
                "0.0 means 'under one tick'; the process-level extra (case p50 - new with no log, marker present) is the "
                "finer, noisier measure.", "",
                "| Transcript case | shadow_ms p95 | Process extra p50 | Max c that meets the criterion | " +
                " | ".join(f"c={c}: budget / met" for c in pt["calls_per_turn"]) + " |",
                "|---|---|---|---|" + "---|" * len(pt["calls_per_turn"])]
        for c in pt["cases"]:
            cells = " | ".join(f"{_f(v['budget_ms_per_call'])} / {'yes' if v['criterion_met'] else 'no'}"
                               for v in c["by_calls_per_turn"].values())
            max_c = c["max_calls_per_turn_for_criterion"]
            out.append(f"| {c['case']} | {_f(c['shadow_ms_p95'])} | {c['process_extra_p50']:+.1f} "
                       f"| {'above any c (p95 under one tick)' if max_c is None else _f(max_c)} | {cells} |")
    unmeasured = [r["label"] + " (" + r["design"] + ")" for r in rows if not r["measured"]]
    out += ["", "Every case measured." if not unmeasured else "NOT measured: " + "; ".join(unmeasured)]
    return "\n".join(out) + "\n"


def reset_budget(runs: int) -> int:
    """The Connection notice's time budget (contract 2026-11-07-295, "Notice time budget").

    Baseline: the reset hook at ``RESET_BASELINE_REF`` (read with ``git show``). New side: this working tree's guard, whose prompt
    row (``notice``) took the notice over from the reset hook (issue #262).
    Completion check: the notice section is run in process, with natural Host detection, on the fixture and the new-side
    copy; unless its outcome is ``shown`` or ``silent:probe-present`` the run would not measure the probe (an untrusted Host or a
    spent budget ends silent and fast) and it fails. T1: subprocess p50 of the new prompt row <= the
    baseline's p50 + 150 ms. T2: in-process p95 of 20 runs <= 150 ms, every run with that outcome. Exit 1 on an incomplete run,
    a breach, or when the baseline commit is absent. It must run from a Claude Code session (the Host is that session)."""
    ref = RESET_BASELINE_REF
    have = subprocess.run(["git", "cat-file", "-e", f"{ref}^{{commit}}"], cwd=REPO_ROOT, capture_output=True)
    if have.returncode != 0:
        print(f"--reset-budget: the baseline commit {ref} is absent from this checkout: fetch the full history "
              "(this mode fails, it never skips and never uses HEAD or origin/master)", file=sys.stderr)
        return 1
    root = Path(os.path.realpath(tempfile.mkdtemp(prefix="cg-reset-bench-")))
    try:
        tmp, home, project = root / "tmp", root / "home", root / "project"
        for folder in (tmp, home / ".claude"):
            folder.mkdir(parents=True, exist_ok=True)
        make_project(project, True)
        old_dir, new_dir = root / "old_hooks", root / "new_hooks"
        for target, from_ref in ((old_dir, ref), (new_dir, None)):
            target.mkdir(parents=True, exist_ok=True)
            rels = (RESET_REL,) + HELPER_RELS if from_ref else (GUARD_REL,) + HELPER_RELS
            for rel in rels:
                if from_ref is None:
                    data = (REPO_ROOT / rel).read_bytes()
                else:
                    shown = subprocess.run(["git", "show", f"{from_ref}:{rel}"], cwd=REPO_ROOT, capture_output=True)
                    if shown.returncode != 0:
                        print(f"--reset-budget: cannot read {rel} at {from_ref}: fetch the full history", file=sys.stderr)
                        return 1
                    data = shown.stdout
                (target / Path(rel).name).write_bytes(data)

        def payload(session: str) -> dict:
            return {"session_id": session, "cwd": str(project), "hook_event_name": "UserPromptSubmit", "prompt": "hello",
                    "prompt_id": "bench-prompt"}

        # -- completion check and T2: the new-side notice section in process, the real probe -----------------------------
        from contextlib import redirect_stdout
        from importlib import util
        import io
        saved = (tempfile.tempdir, os.getcwd(), dict(os.environ), sys.dont_write_bytecode)
        outcomes: list[str] = []
        times: list[float] = []
        try:
            tempfile.tempdir = str(tmp)
            os.environ.clear()
            os.environ.update(isolated_env(tmp, home, project))
            os.chdir(str(project))
            sys.dont_write_bytecode = True
            spec = util.spec_from_file_location("cg_bench_reset", str(new_dir / Path(GUARD_REL).name))
            reset = util.module_from_spec(spec)
            sys.modules[spec.name] = reset
            spec.loader.exec_module(reset)
            for number in range(max(T2_RUNS, 1) + 1):  # run 0 is the completion check, then T2_RUNS timed runs
                out = io.StringIO()
                start = time.perf_counter()
                with redirect_stdout(out):
                    outcome = reset.notice_section(payload(f"bench-reset-{number}"))
                elapsed = (time.perf_counter() - start) * 1000.0
                outcomes.append(outcome)
                if number:
                    times.append(elapsed)
        finally:
            tempfile.tempdir = saved[0]
            os.chdir(saved[1])
            os.environ.clear()
            os.environ.update(saved[2])
            sys.dont_write_bytecode = saved[3]
            sys.modules.pop("cg_bench_reset", None)
        ok_outcomes = ("shown", "silent:probe-present")
        if outcomes[0] not in ok_outcomes:
            print(f"--reset-budget: the notice section ended {outcomes[0]!r} on the fixture: this run would not measure the "
                  "probe (run it from a Claude Code session)", file=sys.stderr)
            return 1
        bad = [o for o in outcomes[1:] if o not in ok_outcomes]
        if bad:
            print(f"--reset-budget: {len(bad)} of {T2_RUNS} timed runs ended {sorted(set(bad))}: this run would not measure the "
                  "probe", file=sys.stderr)
            return 1
        t2_p95 = percentile(times, 0.95)

        # -- T1: the whole hook as a process, baseline against new -----------------------------------------------------
        def one(hooks: Path, session: str) -> tuple[float, int]:
            # the baseline is the 0.16.1 reset hook; the new side is the guard's prompt row (argument ``notice``)
            argv = [sys.executable, str(hooks / Path(RESET_REL).name)] if hooks is old_dir else \
                [sys.executable, str(hooks / Path(GUARD_REL).name), "notice"]
            start = time.perf_counter()
            proc = subprocess.run(argv, input=json.dumps(payload(session)).encode("utf-8"),
                                  capture_output=True, env=isolated_env(tmp, home, project), cwd=str(project))
            return (time.perf_counter() - start) * 1000.0, proc.returncode

        for hooks in (old_dir, new_dir):
            one(hooks, "bench-reset-prime")  # untimed: bytecode of the hook, the Session folder, the pruner's first run
        old_times: list[float] = []
        new_times: list[float] = []
        exits: list[int] = []
        for round_no in range(runs):
            for design, hooks, bucket in (("old", old_dir, old_times), ("new", new_dir, new_times)):
                elapsed, code = one(hooks, f"bench-reset-{design}")
                bucket.append(elapsed)
                exits.append(code)
        old_p50, new_p50 = percentile(old_times, 0.5), percentile(new_times, 0.5)
        problems: list[str] = []
        if any(code != 0 for code in exits) or not old_times:
            problems.append("a reset hook run exited non-zero")
        if old_p50 is None or new_p50 is None or new_p50 > old_p50 + T1_MARGIN_MS:
            problems.append(f"T1: new p50 {_f(new_p50)} ms > baseline p50 {_f(old_p50)} ms + {T1_MARGIN_MS:.0f} ms")
        if t2_p95 is None or t2_p95 > T2_P95_MS:
            problems.append(f"T2: in-process notice p95 {_f(t2_p95)} ms > {T2_P95_MS:.0f} ms")
        print(f"reset budget: baseline {ref}; completion outcome {outcomes[0]}; T1 baseline p50 {_f(old_p50)} ms, new p50 "
              f"{_f(new_p50)} ms (limit baseline + {T1_MARGIN_MS:.0f}); T2 p95 {_f(t2_p95)} ms (limit {T2_P95_MS:.0f}) over "
              f"{len(times)} runs, outcomes {dict(Counter(outcomes[1:]))}")
        for problem in problems:
            print(f"--reset-budget: {problem}", file=sys.stderr)
        return 1 if problems else 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--reset-budget", action="store_true",
                        help="measure the reset hook's Connection notice against its budget (T1, T2) and exit; run it from a Claude "
                             "Code session")
    parser.add_argument("--runs", type=int, default=30, help="fresh-process runs per case (default 30)")
    parser.add_argument("--old-ref", default="origin/master", help="git ref holding the #259 guard (default origin/master)")
    parser.add_argument("--sizes", default="1,10,50", help="transcript sizes in MB (default 1,10,50)")
    parser.add_argument("--json", dest="json_path", help="also write the raw result as JSON to this path")
    parser.add_argument("--keep", action="store_true", help="keep the temp folder (printed) after the run")
    args = parser.parse_args(argv)
    if args.reset_budget:
        return reset_budget(args.runs)
    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]

    root = Path(os.path.realpath(tempfile.mkdtemp(prefix="cg-bench-")))
    try:
        ws = Workspace(root, args.old_ref, sizes)
        cases = run_all(ws, args.runs)
        rows = collect(ws, cases, args.runs)
        result = {"environment": environment(args.old_ref), "runs": args.runs, "rows": rows}
        result["deltas"] = deltas(rows)
        result["per_turn"] = per_turn(rows)
        result["all_measured"] = all(r["measured"] for r in rows)
        print(render_markdown(result))
        if args.json_path:
            Path(args.json_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
        for r in rows:
            if r["stderr_sample"]:
                print(f"[{r['key']}] {r['stderr_sample']}", file=sys.stderr)
        return 0 if result["all_measured"] else 1
    finally:
        if args.keep:
            print(f"kept: {root}", file=sys.stderr)
        else:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
