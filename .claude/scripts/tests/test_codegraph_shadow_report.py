#!/usr/bin/env python3
"""
Tests for codegraph_shadow_report.py -- the read-only report over the CodeGraph guard's measurement log
(contract 2026-11-05-codegraph-hooks-redesign, command "Report the shadow").

One fixture log covers every outcome, a block plus its retry, a block whose "retry" belongs to another turn, blocks per tool,
session_seen, skipped_long_line, malformed lines, torn lines and two log-full lines. The expected numbers are worked out by
hand in FIXTURE_NOTES below, never computed by the code under test.

Run: py -3 .claude/scripts/tests/test_codegraph_shadow_report.py
"""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.pop("CLAUDE_PROJECT_DIR", None)

import codegraph_shadow_report as report  # noqa: E402

SCRIPT = Path(__file__).resolve().parent.parent / "codegraph_shadow_report.py"

BASE = {
    "ts": 1, "session": "s1", "agent": False, "tool": "Read", "target_class": "source",
    "live_decision": "allow", "live_reason": "turn-marker-present", "turn_marker": True,
    "transcript_turn": "open", "session_seen": False,
    "shadow_decision": "allow", "shadow_reason": "transcript-open", "outcome": "agree",
    "fp": "f0", "prompt_key": "p0", "shadow_ms": 5.0, "bytes_read": 0, "skipped_long_line": 0,
}


def rec(**over) -> dict:
    out = dict(BASE)
    out.update(over)
    return out


# Records, in log order. FIXTURE_NOTES: what the report must say about them.
RECORDS = [
    rec(shadow_ms=1.0),                                                                            # R1 agree
    rec(session="s2", agent=True, live_reason="fail-open:subagent", shadow_reason="transcript-unknown",
        transcript_turn="unknown:subagent", shadow_ms=2.0),                                        # R2 agree, subagent
    rec(tool="Read", fp="f1", prompt_key="p1", live_decision="block", live_reason="source-target", turn_marker=False,
        shadow_decision="allow", outcome="shadow-more-open", session_seen=True, shadow_ms=3.0),   # R3 block
    rec(tool="Read", fp="f1", prompt_key="p1", live_reason="retry-escape-used", turn_marker=False,
        shadow_reason="retry-escape-used", transcript_turn="closed", shadow_ms=4.0),               # R4 retry of R3
    rec(session="s2", tool="Grep", fp="f2", prompt_key="p2", live_decision="block", live_reason="ambiguous-target",
        turn_marker=False, shadow_decision="block", shadow_reason="ambiguous-target", transcript_turn="closed",
        shadow_ms=10.0),                                                                           # R5 block, no retry
    rec(session="s3", shadow_decision="block", shadow_reason="source-target", transcript_turn="closed",
        outcome="shadow-more-closed", shadow_ms=20.0),                                             # R6 more-closed
    rec(session="s3", fp="f6", shadow_decision="block", shadow_reason="source-target", transcript_turn="closed",
        outcome="shadow-more-closed", shadow_ms=25.0, skipped_long_line=2),                        # R7 more-closed
    rec(session="s3", live_reason="no-target", shadow_decision="block", shadow_reason="source-target",
        transcript_turn="closed", outcome="shadow-more-closed", shadow_ms=30.0),                   # R8 more-closed
    rec(session="s4", tool="Read", fp="f3", prompt_key="p3", live_decision="block", live_reason="source-target",
        turn_marker=False, shadow_decision="block", shadow_reason="source-target", transcript_turn="closed",
        shadow_ms=6.0),                                                                            # R9 block
    rec(session="s4", tool="Read", fp="f3", prompt_key="p4", live_reason="retry-escape-used", turn_marker=False,
        shadow_reason="retry-escape-used", transcript_turn="closed", shadow_ms=7.0, skipped_long_line=1),  # R10 other turn
    rec(session="s5", tool="Glob", fp="f4", prompt_key="p5", live_decision="block", live_reason="ambiguous-target",
        turn_marker=False, shadow_decision="block", shadow_reason="ambiguous-target", transcript_turn="closed",
        session_seen=True, shadow_ms=8.0),                                                         # R11 block
    rec(session="s5", tool="Glob", fp="f4", prompt_key="p5", live_reason="retry-escape-used", turn_marker=False,
        shadow_reason="retry-escape-used", transcript_turn="closed", shadow_ms=9.0),               # R12 retry of R11
    rec(session="s5", transcript_turn="unknown:no-transcript", shadow_reason="transcript-unknown", shadow_ms=0.5),  # R13
]

FIXTURE_NOTES = """
records 13 over 5 sessions (s1..s5).
outcomes: shadow-more-open 1 (R3); shadow-more-closed 3 (R6, R7, R8); agree 9.
more-closed by (live_reason, transcript_turn): (turn-marker-present, closed) 2; (no-target, closed) 1.
blocks 4 (R3 Read, R5 Grep, R9 Read, R11 Glob). Retried (same session, fp, prompt_key): R3 by R4, R11 by R12 -> 2.
  R9's retry R10 carries another prompt_key, so it is NOT the same turn.
per tool: Read 2 blocks 1 retried 0.5; Grep 1/0/0.0; Glob 1/1/1.0. Q5 (Read, source-target): 2 blocks, 1 retried, 0.5.
session_seen blocks: R3, R11 -> 2.
live reasons main: turn-marker-present 4 (R1 R6 R7 R13), source-target 2, retry-escape-used 3, ambiguous-target 2, no-target 1.
live reasons agent: fail-open:subagent 1.
skipped_long_line total 3 (R7 2 + R10 1).
shadow_ms all, n=13, sorted 0.5 1 2 3 4 6 7 8 9 10 20 25 30: nearest-rank p50 = 7th = 7.0, p95 = 13th = 30.0.
shadow_ms transcript path (not unknown:subagent, not unknown:no-transcript), n=11, sorted 1 3 4 6 7 8 9 10 20 25 30:
  p50 = 6th = 8.0, p95 = 11th = 30.0.
"""

TORN_MID = '{"ts":1,"session":"abc","tool":"Re'      # a write cut short, then the next record on the next line
TORN_TAIL = '{"ts":2,"sess'                          # the last line, no newline
GARBAGE = [b"this is not json", b"[1, 2]", b'{"foo": 1}', b"\xff\xfe{"]   # 4 malformed, none torn
LOG_FULL = '{"event":"log-full","ts":9}'


def fixture_bytes() -> bytes:
    lines: list[bytes] = []
    for i, r in enumerate(RECORDS):
        lines.append(json.dumps(r, separators=(",", ":")).encode("utf-8"))
        if i == 2:
            lines.append(GARBAGE[0])
            lines.append(TORN_MID.encode("utf-8"))
        if i == 5:
            lines.append(b"")                       # a blank line is ignored, not malformed
            lines.append(LOG_FULL.encode("utf-8"))
        if i == 8:
            lines.extend(GARBAGE[1:])
        if i == 10:
            lines.append(LOG_FULL.encode("utf-8"))
    return b"\n".join(lines) + b"\n" + TORN_TAIL.encode("utf-8")      # the file ends inside a record


def make_project(root: Path, content: bytes | None) -> Path:
    project = root / "project"
    logs = project / ".claude" / "logs"
    logs.mkdir(parents=True)
    if content is not None:
        (logs / "codegraph-shadow.jsonl").write_bytes(content)
    return project


def run_main(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = report.main(argv)
    return code, out.getvalue(), err.getvalue()


class BuildReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rep = report.build_report(fixture_bytes().split(b"\n"))

    def test_counts_are_labelled_lower_bounds(self) -> None:
        self.assertTrue(self.rep["lower_bound"])

    def test_records_and_sessions(self) -> None:
        self.assertEqual(self.rep["records"], 13)
        self.assertEqual(self.rep["sessions"], 5)

    def test_every_outcome_is_reported_even_at_zero(self) -> None:
        self.assertEqual(self.rep["outcomes"], {"agree": 9, "shadow-more-open": 1, "shadow-more-closed": 3})
        empty = report.build_report([])
        self.assertEqual(empty["outcomes"], {"agree": 0, "shadow-more-open": 0, "shadow-more-closed": 0})

    def test_more_closed_by_live_reason_and_transcript_turn(self) -> None:
        got = {(row["live_reason"], row["transcript_turn"]): row["count"] for row in self.rep["more_closed"]}
        self.assertEqual(got, {("turn-marker-present", "closed"): 2, ("no-target", "closed"): 1})

    def test_reason_counts_are_split_by_agent(self) -> None:
        live = self.rep["live_reasons"]
        self.assertEqual(live["agent"], {"fail-open:subagent": 1})
        self.assertEqual(live["main"], {"turn-marker-present": 4, "source-target": 2, "retry-escape-used": 3,
                                        "ambiguous-target": 2, "no-target": 1})
        self.assertEqual(self.rep["shadow_reasons"]["agent"], {"transcript-unknown": 1})
        self.assertNotIn("fail-open:subagent", live["main"])

    def test_blocks_and_retries_pair_on_session_fp_and_prompt_key(self) -> None:
        self.assertEqual(self.rep["blocks"], 4)
        self.assertEqual(self.rep["blocks_retried"], 2)

    def test_a_retry_with_another_prompt_key_is_not_the_same_turn(self) -> None:
        self.assertEqual(self.rep["blocks_by_tool"]["Read"], {"blocks": 2, "retried": 1, "retry_rate": 0.5})

    def test_blocks_per_tool(self) -> None:
        by_tool = self.rep["blocks_by_tool"]
        self.assertEqual(by_tool["Grep"], {"blocks": 1, "retried": 0, "retry_rate": 0.0})
        self.assertEqual(by_tool["Glob"], {"blocks": 1, "retried": 1, "retry_rate": 1.0})
        self.assertEqual(set(by_tool), {"Read", "Grep", "Glob"})

    def test_q5_rate_is_read_of_source_blocks_retried(self) -> None:
        self.assertEqual(self.rep["q5_read_source"], {"blocks": 2, "retried": 1, "retry_rate": 0.5})

    def test_one_retry_record_pairs_with_one_block_only(self) -> None:
        block = rec(live_decision="block", live_reason="source-target", shadow_decision="block", outcome="agree")
        retry = rec(live_reason="retry-escape-used")
        got = report.build_report([json.dumps(x).encode() for x in (block, block, retry)])
        self.assertEqual((got["blocks"], got["blocks_retried"]), (2, 1))

    def test_a_retry_before_its_block_does_not_count(self) -> None:
        block = rec(live_decision="block", live_reason="source-target", shadow_decision="block", outcome="agree")
        retry = rec(live_reason="retry-escape-used")
        got = report.build_report([json.dumps(x).encode() for x in (retry, block)])
        self.assertEqual((got["blocks"], got["blocks_retried"]), (1, 0))

    def test_session_seen_counts_blocks_a_per_session_gate_would_have_avoided(self) -> None:
        self.assertEqual(self.rep["session_seen_blocks"], 2)

    def test_skipped_long_line_total(self) -> None:
        self.assertEqual(self.rep["skipped_long_line"], 3)

    def test_shadow_ms_percentiles_are_nearest_rank(self) -> None:
        self.assertEqual(self.rep["shadow_ms"]["all"], {"n": 13, "p50": 7.0, "p95": 30.0})
        self.assertEqual(self.rep["shadow_ms"]["transcript_path"], {"n": 11, "p50": 8.0, "p95": 30.0})

    def test_percentile_edge_cases(self) -> None:
        self.assertIsNone(report.percentile([], 0.5))
        self.assertEqual(report.percentile([4.0], 0.95), 4.0)
        self.assertEqual(report.percentile([4.0, 1.0, 3.0, 2.0], 0.5), 2.0)
        self.assertEqual(report.percentile(list(map(float, range(1, 101))), 0.95), 95.0)

    def test_malformed_and_torn_lines_are_counted_not_fatal(self) -> None:
        # 4 garbage lines + the mid-file torn line + the unterminated last line
        self.assertEqual(self.rep["malformed"], 6)
        self.assertEqual(self.rep["torn"], 2)

    def test_two_log_full_lines(self) -> None:
        self.assertEqual(self.rep["log_full"], 2)

    def test_log_full_lines_are_not_records(self) -> None:
        self.assertEqual(self.rep["records"], 13)

    def test_a_record_with_an_unknown_outcome_is_malformed(self) -> None:
        got = report.build_report([json.dumps(rec(outcome="maybe")).encode()])
        self.assertEqual((got["records"], got["malformed"]), (0, 1))

    def test_missing_optional_numbers_do_not_crash(self) -> None:
        thin = {"outcome": "agree", "session": "s9", "live_decision": "allow", "live_reason": "turn-marker-present"}
        got = report.build_report([json.dumps(thin).encode()])
        self.assertEqual(got["records"], 1)
        self.assertEqual(got["shadow_ms"]["all"]["n"], 0)

    def test_empty_log_reports_zero_records_not_agree(self) -> None:
        got = report.build_report([])
        self.assertEqual(got["records"], 0)
        self.assertEqual(got["outcomes"]["agree"], 0)


class CommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_json_output_is_the_report(self) -> None:
        project = make_project(self.root, fixture_bytes())
        code, out, _err = run_main(["--project", str(project), "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["records"], 13)
        self.assertEqual(data["outcomes"]["shadow-more-closed"], 3)
        self.assertEqual(data["log"], str(project / ".claude" / "logs" / "codegraph-shadow.jsonl"))

    def test_text_output_says_lower_bound_and_names_the_numbers(self) -> None:
        project = make_project(self.root, fixture_bytes())
        code, out, _err = run_main(["--project", str(project)])
        self.assertEqual(code, 0)
        self.assertIn("lower bound", out)
        for needle in ("shadow-more-closed", "shadow-more-open", "agree", "turn-marker-present", "Read", "Grep", "Glob",
                       "log-full", "malformed", "torn", "p50", "p95", "session_seen"):
            self.assertIn(needle, out)

    def test_empty_log_says_no_records(self) -> None:
        project = make_project(self.root, b"")
        code, out, _err = run_main(["--project", str(project)])
        self.assertEqual(code, 0)
        self.assertIn("no records", out)

    def test_missing_log_exits_2(self) -> None:
        project = make_project(self.root, None)
        code, out, err = run_main(["--project", str(project)])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("codegraph-shadow.jsonl", err)

    def test_missing_project_exits_2(self) -> None:
        code, _out, err = run_main(["--project", str(self.root / "nowhere")])
        self.assertEqual(code, 2)
        self.assertTrue(err)

    def test_unreadable_log_exits_2(self) -> None:
        project = make_project(self.root, None)
        (project / ".claude" / "logs" / "codegraph-shadow.jsonl").mkdir()   # a folder where the file should be
        code, _out, err = run_main(["--project", str(project)])
        self.assertEqual(code, 2)
        self.assertTrue(err)

    def test_missing_log_with_json_still_exits_2_and_prints_no_report(self) -> None:
        project = make_project(self.root, None)
        code, out, _err = run_main(["--project", str(project), "--json"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")

    def test_project_defaults_to_the_environment_variable_then_the_current_folder(self) -> None:
        project = make_project(self.root, fixture_bytes())
        old_env, old_cwd = os.environ.get("CLAUDE_PROJECT_DIR"), os.getcwd()
        try:
            os.environ["CLAUDE_PROJECT_DIR"] = str(project)
            self.assertEqual(run_main(["--json"])[0], 0)
            os.environ.pop("CLAUDE_PROJECT_DIR")
            os.chdir(project)
            self.assertEqual(run_main(["--json"])[0], 0)
            os.chdir(self.root)
            self.assertEqual(run_main(["--json"])[0], 2)
        finally:
            os.chdir(old_cwd)
            if old_env is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env

    def test_the_report_is_read_only(self) -> None:
        project = make_project(self.root, fixture_bytes())
        log = project / ".claude" / "logs" / "codegraph-shadow.jsonl"
        before_bytes, before_mtime = log.read_bytes(), log.stat().st_mtime_ns
        before_tree = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*"))
        run_main(["--project", str(project)])
        run_main(["--project", str(project), "--json"])
        self.assertEqual(log.read_bytes(), before_bytes)
        self.assertEqual(log.stat().st_mtime_ns, before_mtime)
        self.assertEqual(sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*")), before_tree)

    def test_script_exit_code_in_a_fresh_process(self) -> None:
        project = make_project(self.root, None)
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
        missing = subprocess.run([sys.executable, str(SCRIPT), "--project", str(project)], capture_output=True, text=True, env=env)
        self.assertEqual(missing.returncode, 2)
        (project / ".claude" / "logs" / "codegraph-shadow.jsonl").write_bytes(fixture_bytes())
        ok = subprocess.run([sys.executable, str(SCRIPT), "--project", str(project), "--json"], capture_output=True, text=True,
                            env=env)
        self.assertEqual(ok.returncode, 0)
        self.assertEqual(json.loads(ok.stdout)["records"], 13)


class MarkerRouteGroupingTests(unittest.TestCase):
    """Issue #295 (contract 2026-11-07-295-codegraph-gate-dropped-mcp, "Shadow (Q5)"): shadow-more-closed rows are also
    grouped by the record's marker_route (mcp / cli / none when the field is absent), and a command-line
    marker is labelled 'explained (command-line route)' in the text report."""

    RECORDS = [
        rec(session="a", shadow_decision="block", shadow_reason="source-target", transcript_turn="closed",
            outcome="shadow-more-closed", marker_route="cli"),
        rec(session="a", fp="g1", shadow_decision="block", shadow_reason="source-target", transcript_turn="closed",
            outcome="shadow-more-closed", marker_route="cli"),
        rec(session="b", shadow_decision="block", shadow_reason="source-target", transcript_turn="closed",
            outcome="shadow-more-closed", marker_route="mcp"),
        rec(session="d", shadow_decision="block", shadow_reason="source-target", transcript_turn="closed",
            outcome="shadow-more-closed"),                                   # an older record: no marker_route
        rec(session="e", marker_route="cli"),                                # agree: not part of the grouping
    ]

    @classmethod
    def setUpClass(cls) -> None:
        lines = [json.dumps(r).encode("utf-8") for r in cls.RECORDS]
        cls.rep = report.build_report(lines)

    def test_more_closed_rows_are_grouped_by_marker_route(self) -> None:
        got = {}
        for row in self.rep["more_closed"]:
            self.assertIn("marker_route", row, "every more_closed row names its marker_route: %r" % (row,))
            got[(row["live_reason"], row["transcript_turn"], row["marker_route"])] = row["count"]
        self.assertEqual(got, {("turn-marker-present", "closed", "cli"): 2, ("turn-marker-present", "closed", "mcp"): 1,
                               ("turn-marker-present", "closed", "none"): 1})

    def test_the_text_report_labels_the_command_line_route_as_explained(self) -> None:
        text = report.render_text(dict(self.rep, log="x"))
        self.assertIn("explained (command-line route)", text)
        self.assertEqual(text.count("explained (command-line route)"), 1, "only the cli group carries the label")

    def test_a_report_without_any_cli_marker_has_no_explained_label(self) -> None:
        rep = report.build_report([json.dumps(r).encode("utf-8") for r in self.RECORDS[2:5]])
        self.assertNotIn("explained (command-line route)", report.render_text(dict(rep, log="x")))

    def test_the_outcome_counts_are_unchanged_by_the_grouping(self) -> None:
        self.assertEqual(self.rep["outcomes"], {"agree": 1, "shadow-more-open": 0, "shadow-more-closed": 4})


if __name__ == "__main__":
    unittest.main()
