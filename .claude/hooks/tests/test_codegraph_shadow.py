#!/usr/bin/env python3
"""
test_codegraph_shadow.py -- the CodeGraph guard's shadow decision and cheaper hot path (issue #261, block 2).

Contract: .claude/concepts/2026-11-05-codegraph-hooks-redesign.md (G-1, G-2, S-1..S-4, Read limits, Measurement log).

House style: plain runnable script, NO pytest. check(name, cond, detail) accumulator, PASS/FAIL/SKIP summary,
non-zero exit on any failure.

    py -3 .claude/hooks/tests/test_codegraph_shadow.py

ISOLATION: every row runs with HOME, USERPROFILE and CLAUDE_CONFIG_DIR at a fixture home folder and TMP, TEMP at a
fixture temp folder (the developer's real home and temp folder are never read or written).

WHAT THIS PINS DOWN
  SH-C*   the Transcript turn state: open, closed, each unknown cause, subagent, allowlisted, not-computed
  SH-K*   the Transcript cursor: warm read, corrupt cursor, rescan on rewrite or shrink, partial last line, link folder
  SH-R*   the Read limits: true tail read, hit limit with a boundary, cold window, a line over 2 MB
  SH-E*   the entry classifier, over the committed t1 fixtures too
  SH-L*   the Measurement log: location, log-full, no path or prompt text, two concurrent writers
  SH-G2*  plan, shadow, effects: ticket, availability.json, blocked call, forced raise, byte identity
  SH-G1*  the lazy imports and the reorder; decide() keeps its signature and effects
  SH-P*   the reset hook's pruner knows the cursor and its temp file
"""

from __future__ import annotations

import contextlib
import importlib.util
import inspect
import io
import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _addon_fixture as af  # noqa: E402

ADD_ON = "codegraph"
HOOK_FILE = "codegraph-first-guard.py"
RESET_FILE = "codegraph-turn-reset.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "codegraph-transcripts"
CURSOR_NAME = "transcript-cursor.json"
LIMIT = 2 * 1024 * 1024
MB = 1024 * 1024

PASSED: list[str] = []
FAILED: list[str] = []
SKIPPED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASSED.append(name)
        print(f"PASS  {name}")
    else:
        FAILED.append(name)
        print(f"FAIL  {name}" + (f"\n        -> {detail}" if detail else ""))


def skip(name: str, reason: str) -> None:
    SKIPPED.append(name)
    print(f"SKIP  {name}\n        -> {reason}")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sid() -> str:
    return "s" + uuid.uuid4().hex


# --------------------------------------------------------------------------------------------------------------
# transcript builders (the shapes the t1 artefact fixed)
# --------------------------------------------------------------------------------------------------------------
def human_line(n: int = 0) -> str:
    return json.dumps({"type": "user", "isSidechain": False, "promptId": "p%d" % n, "promptSource": "sdk",
                       "turnOrigin": "sdk", "message": {"role": "user", "content": "x"}})


def use_line() -> str:
    return json.dumps({"type": "assistant", "isSidechain": False, "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "t1", "name": "mcp__codegraph__codegraph_explore", "input": {}}]}})


def result_line() -> str:
    return json.dumps({"type": "user", "isSidechain": False, "toolUseResult": {}, "sourceToolAssistantUUID": "u",
                       "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "x"}]}})


def filler_line(size: int = 1000) -> str:
    return json.dumps({"type": "attachment", "attachment": {"type": "x", "content": "x" * size}})


def filler_bytes(total: int) -> bytes:
    line = (filler_line(1000) + "\n").encode("utf-8")
    return line * (total // len(line) + 1)


def write_lines(path: Path, lines: list[str]) -> None:
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def append_bytes(path: Path, data: bytes) -> None:
    with open(path, "ab") as fh:
        fh.write(data)


# --------------------------------------------------------------------------------------------------------------
# world and harness
# --------------------------------------------------------------------------------------------------------------
class World:
    def __init__(self) -> None:
        self.sb = af.Sandbox("cgshadow-")
        installed = {p.name: p for p in af.install(ADD_ON, self.sb.root / "installed")}
        self.guard = installed[HOOK_FILE]
        self.reset = installed[RESET_FILE]
        self.count = 0

    def close(self) -> None:
        self.sb.remove()

    def project(self, tag: str | None = None, index: bool = True, server: bool = True, claude_dir: bool = True) -> Path:
        """A fresh project folder under the sandbox: a Project index and a configured server (so the live gate blocks)."""
        self.count += 1
        project = self.sb.root / ("p%d" % self.count if tag is None else tag) / "proj"
        (project / "src").mkdir(parents=True, exist_ok=True)
        if claude_dir:
            (project / ".claude").mkdir(exist_ok=True)
        if index:
            af.plant_index(project)
        if server:
            af.plant_server(project)
        return project

    def folder(self, session: str, create: bool = True) -> Path:
        folder = af.session_folder(af.session_parent(self.sb.home), session)
        if create:
            folder.mkdir(parents=True, exist_ok=True)
        return folder

    def env(self, project: Path | None, extra: dict | None = None) -> dict:
        return af.isolated_env(self.sb.home, self.sb.tmp, project, extra)

    def run(self, project: Path, session: str, transcript: Path | str | None, tool: str = "Read",
            tool_input: dict | None = None, extra_payload: dict | None = None, project_env: bool = True,
            hook: Path | None = None) -> subprocess.CompletedProcess:
        payload = {"session_id": session, "cwd": str(project), "hook_event_name": "PreToolUse", "tool_name": tool,
                   "tool_input": tool_input if tool_input is not None else {"file_path": str(project / "src" / "Thing.cs")}}
        if transcript is not None:
            payload["transcript_path"] = str(transcript)
        if extra_payload:
            payload.update(extra_payload)
        return subprocess.run([sys.executable, "-B", str(hook or self.guard)], input=json.dumps(payload),
                              capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(project),
                              env=self.env(project if project_env else None), timeout=60)


def records(project: Path) -> list[dict]:
    path = project / ".claude" / "logs" / "codegraph-shadow.jsonl"
    out = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def last_record(project: Path) -> dict:
    found = records(project)
    return found[-1] if found else {}


def cursor_of(folder: Path) -> dict:
    try:
        return json.loads((folder / CURSOR_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def describe(proc: subprocess.CompletedProcess) -> str:
    return "exit=%s stdout=%r stderr=%r" % (proc.returncode, proc.stdout[:200], proc.stderr[:400])


@contextmanager
def inproc(w: World, project: Path | None):
    """In-process rows: the fixture environment, the fixture temp folder, and the helper modules forgotten afterwards."""
    saved_temp, saved_cwd = tempfile.tempdir, os.getcwd()
    tempfile.tempdir = str(w.sb.tmp)
    for name in ("_error_log", "_project_paths", "_claude_paths"):
        sys.modules.pop(name, None)
    try:
        with mock.patch.dict(os.environ, w.env(project), clear=True):
            if project is not None:
                os.chdir(str(project))
            yield
    finally:
        os.chdir(saved_cwd)
        tempfile.tempdir = saved_temp
        for name in ("_error_log", "_project_paths", "_claude_paths"):
            sys.modules.pop(name, None)


def run_main(guard, payload: dict) -> tuple:
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), contextlib.redirect_stdout(out), \
            contextlib.redirect_stderr(err):
        try:
            guard.main()
        except SystemExit as exc:
            code = exc.code if exc.code is not None else 0
    return code, out.getvalue(), err.getvalue()


def payload_for(project: Path, session: str, transcript: Path | None, path: Path | None = None, **extra) -> dict:
    payload = {"session_id": session, "cwd": str(project), "tool_name": "Read",
               "tool_input": {"file_path": str(path or (project / "src" / "Thing.cs"))}}
    if transcript is not None:
        payload["transcript_path"] = str(transcript)
    payload.update(extra)
    return payload


# --------------------------------------------------------------------------------------------------------------
# SH-C: the Transcript turn state
# --------------------------------------------------------------------------------------------------------------
def run_states(w: World) -> None:
    project = w.project()
    tdir = w.sb.root / "tr"
    tdir.mkdir()

    # closed: the last human prompt has no CodeGraph use after it. Live and shadow both block.
    t = tdir / "closed.jsonl"
    write_lines(t, [filler_line(), human_line(1)])
    s = sid()
    proc = w.run(project, s, t)
    rec = last_record(project)
    check("SH-C1 closed: the live call is blocked (exit 2)", proc.returncode == 2 and "BLOCKED" in proc.stderr, describe(proc))
    check("SH-C1 closed: transcript_turn closed, shadow blocks too, outcome agree, target_class source",
          rec.get("transcript_turn") == "closed" and rec.get("shadow_decision") == "block"
          and rec.get("live_decision") == "block" and rec.get("outcome") == "agree" and rec.get("target_class") == "source", rec)
    check("SH-C1 closed: the record carries the live reason and the paired fp",
          rec.get("live_reason") == "source-target" and isinstance(rec.get("fp"), str) and len(rec["fp"]) == 12, rec)

    # open: a CodeGraph use follows the last human prompt. The live gate (no marker) blocks; the shadow allows.
    t = tdir / "open.jsonl"
    write_lines(t, [human_line(1), use_line(), result_line()])
    proc = w.run(project, sid(), t)
    rec = last_record(project)
    check("SH-C2 open: the live call is still blocked (the shadow enforces nothing)", proc.returncode == 2, describe(proc))
    check("SH-C2 open: transcript_turn open, shadow allow transcript-open, outcome shadow-more-open",
          rec.get("transcript_turn") == "open" and rec.get("shadow_decision") == "allow"
          and rec.get("shadow_reason") == "transcript-open" and rec.get("outcome") == "shadow-more-open", rec)
    check("SH-C3 not-computed: with the state open the target is not classified",
          rec.get("target_class") == "not-computed", rec)

    # a use before the last human prompt does not open the new turn
    t = tdir / "twoturns.jsonl"
    write_lines(t, [human_line(1), use_line(), human_line(2), filler_line()])
    proc = w.run(project, sid(), t)
    rec = last_record(project)
    check("SH-C4 a use before the last human prompt leaves the new turn closed",
          rec.get("transcript_turn") == "closed" and rec.get("outcome") == "agree", rec)

    # unknown causes
    causes = [
        ("no transcript_path in the payload", None, "unknown:no-transcript"),
        ("a missing file", tdir / "missing.jsonl", "unknown:no-transcript"),
        ("a folder (not a regular file)", tdir, "unknown:no-transcript"),
    ]
    for label, path, want in causes:
        proc = w.run(project, sid(), path)
        rec = last_record(project)
        check(f"SH-C5 {label}: transcript_turn {want}, the shadow allows (transcript-unknown), the live call is unchanged",
              rec.get("transcript_turn") == want and rec.get("shadow_decision") == "allow"
              and rec.get("shadow_reason") == "transcript-unknown" and proc.returncode == 2, "%s %s" % (rec, describe(proc)))

    # parse-error and a CORRUPT transcript
    t = tdir / "corrupt.jsonl"
    t.write_bytes(b'{"type": "user", "message": {broken\n\xff\xfe\x00garbage\n' + human_line(1).encode() + b"\n")
    proc = w.run(project, sid(), t)
    rec = last_record(project)
    check("SH-C6 a CORRUPT transcript: exit and block unchanged, transcript_turn unknown:parse-error, shadow allows",
          proc.returncode == 2 and rec.get("transcript_turn") == "unknown:parse-error"
          and rec.get("shadow_decision") == "allow" and "internal error" not in proc.stderr, "%s %s" % (rec, describe(proc)))
    t = tdir / "binary.jsonl"
    t.write_bytes(bytes(range(256)) * 40)
    proc = w.run(project, sid(), t)
    rec = last_record(project)
    check("SH-C6 a binary file with no newline: the call still ends as without the shadow (exit 2, no internal error)",
          proc.returncode == 2 and "internal error" not in proc.stderr, describe(proc))

    # subagent: no transcript is read
    t = tdir / "sub.jsonl"
    write_lines(t, [human_line(1), filler_line()])
    s = sid()
    proc = w.run(project, s, t, extra_payload={"agent_id": "agent-1", "agent_type": "general-purpose"})
    rec = last_record(project)
    check("SH-C7 subagent: transcript_turn unknown:subagent, nothing read, shadow allows at the transcript step",
          rec.get("transcript_turn") == "unknown:subagent" and rec.get("bytes_read") == 0 and rec.get("agent") is True
          and rec.get("shadow_reason") == "transcript-unknown", rec)
    check("SH-C7 subagent: live allows at step 3 (fail-open:subagent) and the outcome is agree",
          proc.returncode == 0 and rec.get("live_reason") == "fail-open:subagent" and rec.get("outcome") == "agree",
          "%s %s" % (rec, describe(proc)))

    # allowlisted target, state closed -> the shadow classifies and allows at the same step as live
    t = tdir / "closed2.jsonl"
    write_lines(t, [human_line(1)])
    proc = w.run(project, sid(), t, tool_input={"file_path": str(project / "docs" / "notes.md")})
    rec = last_record(project)
    check("SH-C8 allowlisted target: live non-source-target, shadow non-source-target, target_class allowed, agree",
          proc.returncode == 0 and rec.get("live_reason") == "non-source-target" and rec.get("shadow_reason") == "non-source-target"
          and rec.get("target_class") == "allowed" and rec.get("outcome") == "agree", "%s %s" % (rec, describe(proc)))
    # the Turn marker is read (turn_marker bool) once step 0 passed
    check("SH-C8 turn_marker is false when no marker exists", rec.get("turn_marker") is False, rec)
    s = sid()
    af.write_marker(af.session_parent(w.sb.home), s)
    proc = w.run(project, s, t)
    rec = last_record(project)
    check("SH-C9 marker present: live turn-marker-present, turn_marker true, shadow (closed) blocks -> shadow-more-closed",
          proc.returncode == 0 and rec.get("live_reason") == "turn-marker-present" and rec.get("turn_marker") is True
          and rec.get("shadow_decision") == "block" and rec.get("outcome") == "shadow-more-closed", "%s %s" % (rec, describe(proc)))

    # step 0 found the Session state unusable (a Session folder that is a link; the live gate blocks, issue #271): no cursor read or written, turn_marker null
    s = sid()
    target = w.sb.root / "linktarget"
    target.mkdir()
    folder = w.folder(s, create=False)
    t = tdir / "linked.jsonl"
    write_lines(t, [human_line(1), use_line()])
    if af.make_dir_link(folder, target):
        planted = json.dumps({"path": os.path.normcase(os.path.normpath(str(t))), "identity": "x", "scanned_to": t.stat().st_size,
                              "skipping": False, "turn": "closed", "session_seen": False, "updated_at": 1})
        (target / CURSOR_NAME).write_text(planted, encoding="utf-8")
        before = sorted(p.name for p in target.iterdir())
        proc = w.run(project, s, t)
        rec = last_record(project)
        after = sorted(p.name for p in target.iterdir())
        check("SH-K1 link folder: live blocks (session-state-unusable, issue #271) and turn_marker is null (not read)",
              proc.returncode == 2 and rec.get("live_reason") == "session-state-unusable" and rec.get("turn_marker") is None,
              "%s %s" % (rec, describe(proc)))
        check("SH-K1 link folder: the planted cursor was not read (a cold scan answered open, not the planted closed)",
              rec.get("transcript_turn") == "open", rec)
        check("SH-K1 link folder: nothing was written through the link (same names, cursor bytes unchanged)",
              before == after and (target / CURSOR_NAME).read_text(encoding="utf-8") == planted, "%s -> %s" % (before, after))
        af.is_link(folder) and os.rmdir(str(folder))
    else:
        skip("SH-K1 link folder", "a folder link could not be created here")


# --------------------------------------------------------------------------------------------------------------
# SH-K: the Transcript cursor
# --------------------------------------------------------------------------------------------------------------
def run_cursor(w: World) -> None:
    project = w.project()
    tdir = w.sb.root / "trk"
    tdir.mkdir()

    s = sid()
    folder = w.folder(s)
    t = tdir / "t.jsonl"
    write_lines(t, [human_line(1), use_line()])
    size1 = t.stat().st_size
    w.run(project, s, t)
    cur = cursor_of(folder)
    check("SH-K2 a first call writes the cursor: path, identity, scanned_to, skipping, turn, session_seen, updated_at",
          set(cur) >= {"path", "identity", "scanned_to", "skipping", "turn", "session_seen", "updated_at"}
          and cur.get("scanned_to") == size1 and cur.get("turn") == "open" and cur.get("session_seen") is True, cur)
    check("SH-K2 the cursor stores no transcript text", "mcp__codegraph__" not in json.dumps(cur) and '"x"' not in json.dumps(cur), cur)
    check("SH-K2 only the cursor was added to the Session folder (the shadow leaves no temp file)",
          sorted(p.name for p in folder.iterdir() if not p.name.startswith("ticket-") and p.name != "availability.json")
          == [CURSOR_NAME], sorted(p.name for p in folder.iterdir()))

    # warm: only the new bytes are read
    extra = (human_line(2) + "\n").encode("utf-8")
    append_bytes(t, extra)
    w.run(project, s, t)
    rec = last_record(project)
    check("SH-K3 warm call reads only the bytes appended since the cursor, and the state follows (closed)",
          rec.get("bytes_read") == len(extra) and rec.get("transcript_turn") == "closed", rec)
    # no new bytes: nothing read, same answer
    w.run(project, s, t)
    rec = last_record(project)
    check("SH-K3 a call with no new bytes reads nothing", rec.get("bytes_read") == 0 and rec.get("transcript_turn") == "closed", rec)

    # a corrupt cursor reads as absent
    for label, junk in (("not JSON", "}{ not json"), ("JSON of the wrong shape", json.dumps({"scanned_to": "7", "path": 3})),
                        ("a JSON list", "[1, 2]")):
        s2 = sid()
        f2 = w.folder(s2)
        (f2 / CURSOR_NAME).write_text(junk, encoding="utf-8")
        proc = w.run(project, s2, t)
        rec = last_record(project)
        cur = cursor_of(f2)
        check(f"SH-K4 corrupt cursor ({label}): cold scan answers closed, the cursor is rewritten valid",
              proc.returncode == 2 and rec.get("transcript_turn") == "closed" and cur.get("scanned_to") == t.stat().st_size
              and isinstance(cur.get("turn"), str), "%s %s" % (rec, cur))

    # rewrite: identity differs; shrink: file shorter than scanned_to
    s3 = sid()
    f3 = w.folder(s3)
    t3 = tdir / "rw.jsonl"
    write_lines(t3, [human_line(1), use_line()])
    w.run(project, s3, t3)
    cur = cursor_of(f3)
    cur["identity"] = "some-other-file"
    (f3 / CURSOR_NAME).write_text(json.dumps(cur), encoding="utf-8")
    w.run(project, s3, t3)
    rec = last_record(project)
    cur2 = cursor_of(f3)
    check("SH-K5 a different identity: rescan, transcript_turn unknown:rewritten, the cursor is rebuilt",
          rec.get("transcript_turn") == "unknown:rewritten" and cur2.get("identity") != "some-other-file"
          and cur2.get("scanned_to") == t3.stat().st_size, "%s %s" % (rec, cur2))
    w.run(project, s3, t3)
    check("SH-K5 the next call is definite again (open)", last_record(project).get("transcript_turn") == "open", last_record(project))
    write_lines(t3, [human_line(9)])  # shorter than scanned_to
    w.run(project, s3, t3)
    rec = last_record(project)
    cur3 = cursor_of(f3)
    check("SH-K6 a file shorter than scanned_to: rescan, unknown:rewritten, the cursor follows the new size",
          rec.get("transcript_turn") == "unknown:rewritten" and cur3.get("scanned_to") == t3.stat().st_size, "%s %s" % (rec, cur3))
    w.run(project, s3, t3)
    check("SH-K6 and then closed from the new file", last_record(project).get("transcript_turn") == "closed", last_record(project))
    cur = cursor_of(f3)
    cur["path"] = "elsewhere.jsonl"
    (f3 / CURSOR_NAME).write_text(json.dumps(cur), encoding="utf-8")
    w.run(project, s3, t3)
    check("SH-K6 a different path: rescan (unknown:rewritten)", last_record(project).get("transcript_turn") == "unknown:rewritten",
          last_record(project))

    # partial last line waits
    s4 = sid()
    f4 = w.folder(s4)
    t4 = tdir / "partial.jsonl"
    complete = (human_line(1) + "\n" + use_line() + "\n").encode("utf-8")
    part = human_line(2).encode("utf-8")
    t4.write_bytes(complete + part[:30])
    w.run(project, s4, t4)
    rec = last_record(project)
    check("SH-K7 a partial last line is not parsed: state open, scanned_to stops after the last complete line",
          rec.get("transcript_turn") == "open" and cursor_of(f4).get("scanned_to") == len(complete), "%s %s" % (rec, cursor_of(f4)))
    append_bytes(t4, part[30:] + b"\n")
    w.run(project, s4, t4)
    rec = last_record(project)
    check("SH-K7 once completed, the line is read (closed) and only its bytes are read",
          rec.get("transcript_turn") == "closed" and rec.get("bytes_read") == len(part) + 1, rec)

    # cold start keeps nothing when the Session folder does not exist yet: no folder is created by the shadow
    s5 = sid()
    folder5 = w.folder(s5, create=False)
    proc = w.run(project, s5, t)
    check("SH-K8 the shadow does not create the Session folder (the live block creates it by writing the ticket)",
          not (folder5 / CURSOR_NAME).exists() and last_record(project).get("transcript_turn") in ("closed", "open"),
          sorted(p.name for p in folder5.iterdir()) if folder5.exists() else "absent")


# --------------------------------------------------------------------------------------------------------------
# SH-R: the Read limits
# --------------------------------------------------------------------------------------------------------------
def run_limits(w: World) -> None:
    project = w.project()
    tdir = w.sb.root / "trl"
    tdir.mkdir()

    # true tail read of a large transcript
    s = sid()
    w.folder(s)
    big = tdir / "big.jsonl"
    big.write_bytes(filler_bytes(8 * MB) + (human_line(1) + "\n" + use_line() + "\n").encode("utf-8"))
    proc = w.run(project, s, big)
    rec = last_record(project)
    check("SH-R1 true tail read: a transcript over 8 MB reads at most the 2 MB limit, and still answers open",
          0 < rec.get("bytes_read", 0) <= LIMIT and rec.get("transcript_turn") == "open", rec)

    # a cold window without a boundary
    s = sid()
    w.folder(s)
    nob = tdir / "noboundary.jsonl"
    nob.write_bytes(filler_bytes(3 * MB))
    w.run(project, s, nob)
    rec = last_record(project)
    check("SH-R2 a cold window with no boundary answers unknown:window-exceeded",
          rec.get("transcript_turn") == "unknown:window-exceeded" and rec.get("bytes_read", 0) <= LIMIT, rec)

    # a hit limit WITH a boundary found still answers window-exceeded; the cursor advances; later calls finish
    s = sid()
    f = w.folder(s)
    t = tdir / "grow.jsonl"
    write_lines(t, [human_line(1)])
    w.run(project, s, t)
    append_bytes(t, (human_line(2) + "\n").encode("utf-8") + filler_bytes(3 * MB))
    w.run(project, s, t)
    rec = last_record(project)
    c1 = cursor_of(f).get("scanned_to", 0)
    check("SH-R3 a hit limit with a boundary found answers unknown:window-exceeded (never a stale closed)",
          rec.get("transcript_turn") == "unknown:window-exceeded" and 0 < rec.get("bytes_read", 0) <= LIMIT, rec)
    check("SH-R3 the cursor advanced over what was parsed, but not to the end of the file",
          0 < c1 < t.stat().st_size, "%s of %s" % (c1, t.stat().st_size))
    w.run(project, s, t)
    rec = last_record(project)
    check("SH-R3 the next call reaches the end of the file and answers closed",
          rec.get("transcript_turn") == "closed" and cursor_of(f).get("scanned_to") == t.stat().st_size, rec)

    # a line over 2 MB is skipped and counted
    s = sid()
    f = w.folder(s)
    t = tdir / "longline.jsonl"
    write_lines(t, [human_line(1)])
    w.run(project, s, t)
    long_line = b'{"type":"attachment","a":"' + b"x" * (int(2.6 * MB)) + b'"}\n'
    append_bytes(t, long_line + (human_line(2) + "\n").encode("utf-8"))
    seen: list[dict] = []
    for _ in range(6):
        w.run(project, s, t)
        seen.append(last_record(project))
        if seen[-1].get("transcript_turn") == "closed" and cursor_of(f).get("scanned_to") == t.stat().st_size:
            break
    total_skipped = sum(r.get("skipped_long_line", 0) for r in seen)
    check("SH-R4 a line over 2 MB is skipped and counted once in skipped_long_line", total_skipped == 1, [r.get("skipped_long_line") for r in seen])
    check("SH-R4 the first call over it answers window-exceeded, no call reads more than the limit",
          seen[0].get("transcript_turn") == "unknown:window-exceeded" and all(r.get("bytes_read", 0) <= LIMIT for r in seen), seen[0])
    check("SH-R4 the cursor moves past the long line and the state becomes closed",
          seen[-1].get("transcript_turn") == "closed" and cursor_of(f).get("scanned_to") == t.stat().st_size, seen[-1])


# --------------------------------------------------------------------------------------------------------------
# in-process rows: unreadable, time-exceeded, the entry classifier
# --------------------------------------------------------------------------------------------------------------
def run_inproc_states(w: World) -> None:
    project = w.project()
    t = w.sb.root / "inproc.jsonl"
    write_lines(t, [human_line(1)])
    with inproc(w, project):
        guard = load_module(w.guard, "cg_shadow_states")
        session = guard.Session({"session_id": sid(), "cwd": str(project)})
        far = guard.time.monotonic() + 60
        payload = {"transcript_path": str(t)}
        real_open = open

        def deny(path, *a, **k):
            if str(path) == str(t):
                raise PermissionError("denied")
            return real_open(path, *a, **k)

        with mock.patch("builtins.open", deny):
            res = guard.read_transcript(payload, session, False, far)
        check("SH-C10 unreadable: open() raises -> unknown:unreadable", res["state"] == "unknown:unreadable", res)
        res = guard.read_transcript(payload, session, False, guard.time.monotonic() - 1)
        check("SH-C11 time-exceeded: a spent deadline -> unknown:time-exceeded and no cursor to write",
              res["state"] == "unknown:time-exceeded" and not res.get("cursor"), res)

        # the full call: a spent budget still ends as without the shadow, the record says time-exceeded, no cursor
        s = sid()
        folder = w.folder(s)
        guard.SHADOW_TIME_BUDGET_S = -1.0
        code, out, err = run_main(guard, payload_for(project, s, t))
        rec = last_record(project)
        check("SH-C11 time-exceeded end to end: the live block stands (exit 2), the record says unknown:time-exceeded, no cursor written",
              code == 2 and rec.get("transcript_turn") == "unknown:time-exceeded" and not (folder / CURSOR_NAME).exists()
              and rec.get("shadow_decision") == "allow", "%s %s" % (code, rec))


def run_classifier(w: World) -> None:
    with inproc(w, None):
        guard = load_module(w.guard, "cg_shadow_classify")

        def kind(obj) -> str:
            return guard.classify_entry(obj)

        base = json.loads(human_line(1))
        check("SH-E1 a plain human prompt is human-prompt", kind(base) == "human-prompt")
        list_prompt = dict(base, message={"role": "user", "content": [{"type": "text", "text": "x"}]})
        check("SH-E1 a human prompt with list content and no tool_result is human-prompt", kind(list_prompt) == "human-prompt")
        negatives = {
            "a tool result entry": json.loads(result_line()),
            "a sidechain prompt": dict(base, isSidechain=True),
            "an isMeta reminder": dict(base, isMeta=True),
            "a compaction summary": dict(base, isCompactSummary=True),
            "a task notification (origin)": dict(base, origin={"kind": "task"}),
            "a system promptSource": dict(base, promptSource="system"),
            "a prompt with no promptSource": {k: v for k, v in base.items() if k != "promptSource"},
            "a prompt with toolUseResult": dict(base, toolUseResult={}),
            "a prompt with sourceToolAssistantUUID": dict(base, sourceToolAssistantUUID="u"),
            "an attachment": {"type": "attachment", "attachment": {"type": "hook_additional_context"}},
            "an unknown type": {"type": "banana"},
            "a non-dict": ["user"],
        }
        for label, obj in negatives.items():
            check(f"SH-E2 {label} is other (never a boundary)", kind(obj) == "other", kind(obj))
        use = json.loads(use_line())
        check("SH-E3 an assistant mcp__codegraph__* tool_use is codegraph-use", kind(use) == "codegraph-use")
        check("SH-E3 a sidechain assistant entry is other", kind(dict(use, isSidechain=True)) == "other")
        other_use = json.loads(use_line())
        other_use["message"]["content"][0]["name"] = "Read"
        check("SH-E3 a tool_use of another tool is other", kind(other_use) == "other")
        text_only = json.loads(use_line())
        text_only["message"]["content"] = [{"type": "text", "text": "mcp__codegraph__x"}]
        check("SH-E3 an assistant text block naming the tool is other", kind(text_only) == "other")

        # the t1 fixtures: the line indices the t1 artefact recorded (0-based)
        expected = {"sequential-turns.jsonl": [3, 27, 43], "parallel-calls.jsonl": [3, 27], "compaction.jsonl": [3, 28],
                    "injected-messages.jsonl": [3, 28], "subagent.jsonl": [3]}
        for name, want in expected.items():
            path = FIXTURES / name
            if not path.is_file():
                check(f"SH-E4 fixture {name} exists", False, str(path))
                continue
            got = []
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines()):  # noqa: E501
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if guard.classify_entry(obj) != "other":
                    got.append(number)
            check(f"SH-E4 {name}: the boundary and use lines are {want}", got == want, got)


# --------------------------------------------------------------------------------------------------------------
# SH-L: the Measurement log
# --------------------------------------------------------------------------------------------------------------
def tree_has_log(root: Path) -> list[Path]:
    return [p for p in root.rglob("codegraph-shadow.jsonl")]


def run_log(w: World) -> None:
    tdir = w.sb.root / "trlog"
    tdir.mkdir()
    t = tdir / "t.jsonl"
    write_lines(t, [human_line(1)])

    # CLAUDE_PROJECT_DIR unset: no record, nothing under the home folder
    project = w.project()
    before = set(tree_has_log(w.sb.root))
    proc = w.run(project, sid(), t, project_env=False)
    found = set(tree_has_log(w.sb.root)) - before
    check("SH-L1 CLAUDE_PROJECT_DIR unset: the live call is unchanged (blocked as before), no record anywhere",
          not found and proc.returncode == 2 and "internal error" not in proc.stderr, "%s %s" % (found, describe(proc)))
    # The live gate keeps its Session state in the Per-user session parent, which sits inside the fixture home
    # (LOCALAPPDATA / XDG_CACHE_HOME): that subtree is the gate's, not the shadow's. Everything else must stay empty.
    parent = af.session_parent(w.sb.home, create=False)
    own_state = {parent, *parent.parents}
    outside = [p for p in w.sb.home.rglob("*") if p not in own_state and parent not in p.parents]
    check("SH-L1 CLAUDE_PROJECT_DIR unset: nothing was written under the home folder (outside the Per-user session parent)",
          not outside, [str(p) for p in outside][:5])

    # <project>/.claude absent: no record and no .claude created
    bare = w.project(claude_dir=False)
    proc = w.run(bare, sid(), t)
    check("SH-L2 <project>/.claude absent: no record and no .claude folder is created",
          not (bare / ".claude").exists() and not tree_has_log(bare), describe(proc))

    # a record carries no path or prompt text
    project = w.project()
    secret_prompt = "SECRET-PROMPT-TEXT-91"
    named = project / "src" / "UniqueFileNameXyz.cs"
    w.run(project, sid(), t, tool_input={"file_path": str(named)}, extra_payload={"prompt": secret_prompt, "prompt_id": "pid-77"})
    log_text = (project / ".claude" / "logs" / "codegraph-shadow.jsonl").read_text(encoding="utf-8")
    needles = [secret_prompt, "UniqueFileNameXyz", str(project), str(t), str(w.sb.tmp), str(w.sb.home), "pid-77", "Thing.cs"]
    check("SH-L3 no path, file name, prompt text or raw prompt_id in the log",
          not any(n in log_text for n in needles), [n for n in needles if n in log_text])
    rec = last_record(project)
    check("SH-L3 the record is one line of at most 1 KB with the contract fields",
          len(log_text.splitlines()) == 1 and len(log_text.encode("utf-8")) <= 1024
          and set(rec) >= {"ts", "session", "agent", "tool", "target_class", "live_decision", "live_reason", "turn_marker",
                           "transcript_turn", "session_seen", "shadow_decision", "shadow_reason", "outcome", "fp", "prompt_key",
                           "shadow_ms", "bytes_read", "skipped_long_line"}, rec)
    check("SH-L3 session and prompt_key are 12 hex digits", len(rec.get("session", "")) == 12 and len(rec.get("prompt_key", "")) == 12
          and all(c in "0123456789abcdef" for c in rec.get("session", "") + rec.get("prompt_key", "")), rec)
    w.run(project, sid(), t)
    check("SH-L3 a payload with no prompt_id has prompt_key none", last_record(project).get("prompt_key") == "none", last_record(project))

    # log-full: at 10 MB one {"event":"log-full"} line is written and writing stops
    project = w.project()
    logs = project / ".claude" / "logs"
    logs.mkdir()
    full = logs / "codegraph-shadow.jsonl"
    full.write_bytes(b"\n" * (10 * MB))
    w.run(project, sid(), t)
    w.run(project, sid(), t)
    text = full.read_bytes().decode("utf-8", "replace")
    check("SH-L4 at 10 MB a single log-full line is written and writing stops",
          text.count('"log-full"') == 1 and len(records(project)) == 1 and records(project)[0].get("event") == "log-full",
          "%d log-full lines, %d bytes" % (text.count('"log-full"'), len(text)))


def _writer(guard_path, barrier, rounds, who, project, session, transcript_dir, results) -> None:
    """One writer process of the two-process test: round after round, behind a barrier, a cold shadow section."""
    guard = load_module(Path(guard_path), "cg_shadow_writer_%d" % who)
    raised = 0
    for n in range(rounds):
        transcript = Path(transcript_dir) / ("r%d-w%d.jsonl" % (n, who))  # a new path every round: a cold scan, a cursor write
        write_lines(transcript, [human_line(n), use_line()])
        payload = {"session_id": session, "cwd": project, "tool_name": "Read",
                   "tool_input": {"file_path": str(Path(project) / "src" / "Thing.cs")}, "transcript_path": str(transcript)}
        try:
            barrier.wait(timeout=60)
        except Exception:  # noqa: BLE001
            results.put((who, raised, -1))
            return
        try:
            live = guard._plan("Read", payload["tool_input"], payload, None, None)
            guard.shadow_section("Read", payload["tool_input"], payload, live)
        except BaseException:  # noqa: BLE001
            raised += 1
    results.put((who, raised, rounds))


def run_two_writers(w: World) -> None:
    project = w.project()
    s = sid()
    folder = w.folder(s)
    tdir = w.sb.root / "tw"
    tdir.mkdir()
    rounds = 40
    env = w.env(project)
    ctx = multiprocessing.get_context("spawn")
    barrier = ctx.Barrier(2)
    saved = {k: os.environ.get(k) for k in env}
    try:
        os.environ.clear()
        os.environ.update(env)
        results = ctx.Queue()
        procs = [ctx.Process(target=_writer, args=(str(w.guard), barrier, rounds, who, str(project), s, str(tdir), results))
                 for who in (0, 1)]
        for proc in procs:
            proc.start()
        outcomes = [results.get(timeout=120) for _ in procs]
        for proc in procs:
            proc.join(timeout=60)
    except Exception as exc:  # noqa: BLE001
        check("SH-L5 two writers ran", False, repr(exc))
        return
    finally:
        os.environ.clear()
        os.environ.update({k: v for k, v in saved.items() if v is not None})
    writes = 2 * rounds
    path = project / ".claude" / "logs" / "codegraph-shadow.jsonl"
    text = path.read_bytes().decode("utf-8", "replace") if path.exists() else ""
    parsed = malformed = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            json.loads(line)
            parsed += 1
        except ValueError:
            malformed += 1
    cur = cursor_of(folder)
    check("SH-L5 two concurrent writers: neither raised out of the shadow section", all(o[1] == 0 and o[2] == rounds for o in outcomes), outcomes)
    check("SH-L5 two concurrent writers: the cursor parses and has the cursor shape",
          set(cur) >= {"path", "identity", "scanned_to", "turn"}, cur)
    check("SH-L5 two concurrent writers: every log line is whole or counted malformed, and records never exceed writes",
          parsed + malformed >= parsed and parsed <= writes, "parsed=%d malformed=%d writes=%d" % (parsed, malformed, writes))
    check("SH-L5 no cursor temp file is left behind", not [p.name for p in folder.iterdir() if p.name.endswith(".tmp")],
          [p.name for p in folder.iterdir()])


# --------------------------------------------------------------------------------------------------------------
# SH-G2: plan, shadow, effects
# --------------------------------------------------------------------------------------------------------------
def folder_snapshot(folder: Path) -> dict:
    """File names and contents of a Session folder, minus the ticket ts, availability checked_at and the cursor files."""
    snap: dict = {}
    if not folder.exists():
        return snap
    for p in sorted(folder.iterdir()):
        if p.name == CURSOR_NAME or (p.name.startswith("transcript-cursor.") and p.name.endswith(".tmp")):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            snap[p.name] = None
            continue
        if p.name.startswith("ticket-") or p.name == "availability.json":
            try:
                obj = json.loads(text)
                obj.pop("ts", None)
                obj.pop("checked_at", None)
                text = json.dumps(obj, sort_keys=True)
            except ValueError:
                pass
        snap[p.name] = text
    return snap


def run_g2(w: World) -> None:
    tdir = w.sb.root / "g2"
    tdir.mkdir()
    closed = tdir / "closed.jsonl"
    write_lines(closed, [human_line(1)])

    # a matching ticket is consumed exactly once, by the live path; the record shows retry-escape-used
    project = w.project()
    s = sid()
    folder = w.folder(s)
    with inproc(w, project):
        guard = load_module(w.guard, "cg_shadow_g2a")
        first = run_main(guard, payload_for(project, s, closed))
        tickets = [p.name for p in folder.iterdir() if p.name.startswith("ticket-")]
        seen_at_shadow: list = []
        real_shadow = guard.shadow_section

        def watching(*a, **k):
            seen_at_shadow.append(sorted(p.name for p in folder.iterdir() if p.name.startswith("ticket-")))
            try:
                return real_shadow(*a, **k)
            finally:
                seen_at_shadow.append(sorted(p.name for p in folder.iterdir() if p.name.startswith("ticket-")))

        removed: list = []
        real_remove = os.remove

        def spy(path, *a, **k):
            if os.path.basename(str(path)).startswith("ticket-"):
                removed.append(str(path))
            return real_remove(path, *a, **k)

        with mock.patch.object(guard, "shadow_section", watching), mock.patch.object(os, "remove", spy):
            second = run_main(guard, payload_for(project, s, closed))
    rec = last_record(project)
    check("SH-G2a the first identical call blocks and issues one ticket", first[0] == 2 and len(tickets) == 1, "%s %s" % (first[0], tickets))
    check("SH-G2a the retry is allowed (retry-escape-used) and the ticket is gone afterwards",
          second[0] == 0 and "retry-escape-used" in second[2] and not [p for p in folder.iterdir() if p.name.startswith("ticket-")],
          second)
    check("SH-G2a the ticket existed through the whole shadow section (the shadow consumed nothing)",
          seen_at_shadow == [tickets, tickets], seen_at_shadow)
    check("SH-G2a the ticket was removed exactly once, by the live path", len(removed) == 1, removed)
    check("SH-G2a the record shows retry-escape-used for live and for the shadow, outcome agree",
          rec.get("live_reason") == "retry-escape-used" and rec.get("shadow_reason") == "retry-escape-used"
          and rec.get("outcome") == "agree", rec)

    # a ticket gone at apply keeps the planned allow
    project = w.project()
    s = sid()
    folder = w.folder(s)
    with inproc(w, project):
        guard = load_module(w.guard, "cg_shadow_g2b")
        run_main(guard, payload_for(project, s, closed))
        real_shadow = guard.shadow_section

        def steal(*a, **k):
            try:
                return real_shadow(*a, **k)
            finally:
                for p in list(folder.iterdir()):
                    if p.name.startswith("ticket-"):
                        p.unlink()  # an identical parallel call consumed it after the plan

        with mock.patch.object(guard, "shadow_section", steal):
            code, out, err = run_main(guard, payload_for(project, s, closed))
    check("SH-G2b a ticket gone at apply keeps the planned allow (exit 0, retry-escape-used)",
          code == 0 and "retry-escape-used" in err, (code, err))

    # the shadow writes no availability.json: live allows at step 2 (marker), the shadow (closed) computes it read-only
    project = w.project()
    s = sid()
    folder = w.folder(s)
    af.write_marker(af.session_parent(w.sb.home), s)
    proc = w.run(project, s, closed)
    rec = last_record(project)
    check("SH-G2c the shadow computed a block from the availability verdicts (shadow-more-closed)...",
          rec.get("shadow_decision") == "block" and rec.get("outcome") == "shadow-more-closed", "%s %s" % (rec, describe(proc)))
    check("SH-G2c ...and wrote no availability.json and no ticket", not (folder / "availability.json").exists()
          and not [p for p in folder.iterdir() if p.name.startswith("ticket-")], sorted(p.name for p in folder.iterdir()))

    # a blocked call (exit 2) still writes its record
    project = w.project()
    proc = w.run(project, sid(), closed)
    check("SH-G2d a blocked call (exit 2) still writes its record", proc.returncode == 2 and len(records(project)) == 1 and
          records(project)[0].get("live_decision") == "block", describe(proc))

    # forced raise: byte-identical exit, stdout, stderr; equal Session folder
    for label, indexed in (("a blocked call", True), ("an allowed call (fail-open:no-index)", False)):
        results = {}
        project = w.project(index=indexed)  # one project for the three runs: availability.json keys on the cwd
        for mode in ("reference", "exception", "systemexit"):
            s = "sfixed" + ("b" if indexed else "a")
            sandbox = af.Sandbox("cgshadow-g2-")
            try:
                saved = (w.sb.home, w.sb.tmp)
                w.sb.home, w.sb.tmp = sandbox.home, sandbox.tmp
                try:
                    with inproc(w, project):
                        guard = load_module(w.guard, "cg_shadow_g2_%s_%s" % (mode, indexed))
                        if mode == "reference":
                            patch = mock.patch.object(guard, "shadow_section", lambda *a, **k: None)
                        elif mode == "exception":
                            patch = mock.patch.object(guard, "shadow_section", mock.Mock(side_effect=Exception("forced")))
                        else:
                            patch = mock.patch.object(guard, "shadow_section", mock.Mock(side_effect=SystemExit(7)))
                        with patch:
                            run = run_main(guard, payload_for(project, s, closed))
                        results[mode] = (run, folder_snapshot(af.session_folder(af.session_parent(sandbox.home), s)))
                finally:
                    w.sb.home, w.sb.tmp = saved
            finally:
                sandbox.remove()
        ref = results["reference"]
        for mode in ("exception", "systemexit"):
            got = results[mode]
            check(f"SH-G2e {label}, shadow raising {mode}: exit code, stdout and stderr are byte-identical to a run without it",
                  got[0] == ref[0], "%r vs %r" % (got[0], ref[0]))
            check(f"SH-G2e {label}, shadow raising {mode}: the Session folder is equal (names and contents, minus ts/checked_at/cursor files)",
                  got[1] == ref[1] and bool(ref[1]), "%r vs %r" % (got[1], ref[1]))
        check(f"SH-G2e {label}: the reference run really {'blocked' if indexed else 'allowed'}",
              ref[0][0] == (2 if indexed else 0), ref[0])

    # a real shadow (not forced) leaves the live outcome and the folder as without it too
    project = w.project()
    s = sid()
    real = w.run(project, s, closed)
    other_project = w.project()
    # the same call without a project log location (the shadow is skipped): same exit and same stderr
    quiet = w.run(other_project, sid(), closed, project_env=False)
    check("SH-G2f a run with the shadow and a run without a log location give the same exit code and the same stderr",
          real.returncode == quiet.returncode and real.stderr == quiet.stderr and real.stdout == quiet.stdout,
          "%s | %s" % (describe(real), describe(quiet)))


# --------------------------------------------------------------------------------------------------------------
# SH-G1: lazy imports, reorder
# --------------------------------------------------------------------------------------------------------------
PROBE = r"""
import importlib.util, io, sys
path, payload = sys.argv[1], sys.argv[2]
sys.stdin = io.StringIO(payload)
spec = importlib.util.spec_from_file_location("guard_under_probe", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
try:
    mod.main()
except SystemExit:
    pass
print("RESULT", "_project_paths" in sys.modules, "_error_log" in sys.modules)
"""


def probe(w: World, project: Path, session: str, tool_input: dict) -> tuple:
    payload = {"session_id": session, "cwd": str(project), "tool_name": "Read", "tool_input": tool_input}
    proc = subprocess.run([sys.executable, "-B", "-c", PROBE, str(w.guard), json.dumps(payload)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=str(project), env=w.env(project), timeout=60)
    line = [ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT")]
    if not line:
        return None, None, proc
    parts = line[-1].split()
    return parts[1] == "True", parts[2] == "True", proc


def run_g1(w: World) -> None:
    project = w.project()
    source = {"file_path": str(project / "src" / "Thing.cs")}
    s = sid()
    af.write_marker(af.session_parent(w.sb.home), s)
    pp, el, proc = probe(w, project, s, source)
    check("SH-G1a marker present, a source Read: allowed and _project_paths is left unimported", pp is False and proc.returncode == 0, describe(proc))
    check("SH-G1a marker present, a source Read: _error_log is left unimported too", el is False, describe(proc))
    pp, el, proc = probe(w, project, sid(), source)
    check("SH-G1a control: with no marker the same Read is classified/blocked and _project_paths IS imported (the probe bites)",
          pp is True, describe(proc))
    s = sid()
    af.write_marker(af.session_parent(w.sb.home), s)
    pp, el, proc = probe(w, project, s, {"file_path": str(project / "docs" / "n.md")})
    check("SH-G1a marker present, a non-source Read: _project_paths is left unimported", pp is False, describe(proc))

    # the reorder: the marker is checked before classification; the outcome of both allows is the same
    with inproc(w, project):
        guard = load_module(w.guard, "cg_shadow_g1")
        s2 = sid()
        af.write_marker(af.session_parent(w.sb.home), s2)
        both = guard.decide("Read", {"file_path": str(project / "docs" / "n.md")}, {"session_id": s2, "cwd": str(project)})
        check("SH-G1b marker present and a non-source target: allowed, reason is the marker's (checked first)",
              both == ("allow", "turn-marker-present"), both)

        sig = inspect.signature(guard.decide)
        check("SH-G1c decide() keeps its signature (tool_name, tool_input, payload=None)",
              list(sig.parameters) == ["tool_name", "tool_input", "payload"] and sig.parameters["payload"].default is None, sig)
        s3 = sid()
        folder = af.session_folder(af.session_parent(w.sb.home), s3)
        payload = {"session_id": s3, "cwd": str(project)}
        first = guard.decide("Read", {"file_path": str(project / "src" / "Thing.cs")}, payload)
        tickets = [p.name for p in folder.iterdir() if p.name.startswith("ticket-")]
        check("SH-G1c decide() still returns (decision, reason) and still issues the ticket and caches availability.json",
              first == ("block", "source-target") and len(tickets) == 1 and (folder / "availability.json").is_file(), (first, tickets))
        second = guard.decide("Read", {"file_path": str(project / "src" / "Thing.cs")}, payload)
        check("SH-G1c decide() still consumes the ticket on the identical retry",
              second == ("allow", "retry-escape-used") and not [p for p in folder.iterdir() if p.name.startswith("ticket-")], second)
        four = guard.evaluate("Read", {"file_path": str(project / "src" / "Thing.cs")}, payload)
        check("SH-G1c evaluate() still returns (decision, reason, session, fingerprint)",
              len(four) == 4 and four[0] == "block" and isinstance(four[3], str) and len(four[3]) == 64, four[:2])

        # lazy module-level names resolve, and stay patchable
        names = ("_pp", "_pp_checkout_equivalent_path", "_pp_worktree_own_root", "_pp_tree_kind", "_pp_main_checkout_root", "log_event")
        check("SH-G1d every module-level helper name still resolves on the module",
              all(hasattr(guard, n) for n in names), [n for n in names if not hasattr(guard, n)])
        check("SH-G1d _pp is the _project_paths module and log_event is callable",
              getattr(guard._pp, "__name__", "") == "_project_paths" and callable(guard.log_event))
        guard2 = load_module(w.guard, "cg_shadow_g1_patch")
        with mock.patch.object(guard2, "_pp_checkout_equivalent_path", None):
            code, out, err = run_main(guard2, payload_for(project, sid(), None))
        check("SH-G1d patching _pp_checkout_equivalent_path to None shows the fallback-mode banner",
              code == 2 and "could not be imported" in err, (code, err[:300]))
        guard3 = load_module(w.guard, "cg_shadow_g1_patch2")
        logged: list = []
        with mock.patch.object(guard3, "log_event", lambda *a, **k: logged.append(k.get("event"))):
            run_main(guard3, payload_for(project, sid(), None))
        check("SH-G1d patching log_event is honoured by the block path", "block" in logged, logged)


# --------------------------------------------------------------------------------------------------------------
# SH-P: the reset hook's pruner
# --------------------------------------------------------------------------------------------------------------
def run_pruner(w: World) -> None:
    reset = load_module(w.reset, "cg_shadow_reset")
    root = w.sb.root / "prune"
    root.mkdir()

    def old_folder(name: str, files: list) -> Path:
        folder = root / (reset.SESSION_PREFIX + name)
        folder.mkdir()
        for fname in files:
            (folder / fname).write_text("{}", encoding="utf-8")
            os.utime(folder / fname, (1, 1))
        os.utime(folder, (1, 1))
        return folder

    f1 = old_folder("known", [CURSOR_NAME, "transcript-cursor.12345.tmp", "turn.json"])
    f2 = old_folder("unknown-tmp", [CURSOR_NAME, "transcript-cursor.abc.tmp"])
    removed = reset.prune_session_folders(root)
    check("SH-P1 an old folder holding the cursor and its temp file is pruned (both names are known)",
          reset.SESSION_PREFIX + "known" in removed and not f1.exists(), removed)
    check("SH-P1 a folder holding a temp file with a non-digit name is kept whole", f2.exists() and CURSOR_NAME in os.listdir(f2), removed)

    # the reset hook on a prompt leaves the cursor alone
    s = sid()
    folder = w.folder(s)
    (folder / CURSOR_NAME).write_text("{}", encoding="utf-8")
    (folder / "turn.json").write_text("{}", encoding="utf-8")
    proc = subprocess.run([sys.executable, "-B", str(w.reset)], input=json.dumps({"session_id": s, "cwd": str(w.sb.root)}),
                          capture_output=True, text=True, env=w.env(None), timeout=60)
    check("SH-P2 the reset hook deletes the marker but keeps the cursor", proc.returncode == 0 and not (folder / "turn.json").exists()
          and (folder / CURSOR_NAME).exists(), describe(proc))


# --------------------------------------------------------------------------------------------------------------
def main() -> int:
    w = World()
    try:
        for fn in (run_states, run_cursor, run_limits, run_inproc_states, run_classifier, run_log, run_two_writers, run_g2, run_g1,
                   run_pruner):
            try:
                fn(w)
            except Exception:  # noqa: BLE001
                check("%s ran to the end" % fn.__name__, False, traceback.format_exc())
    finally:
        w.close()
    print("\n%d passed, %d failed, %d skipped, %d total" % (len(PASSED), len(FAILED), len(SKIPPED),
                                                          len(PASSED) + len(FAILED) + len(SKIPPED)))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
