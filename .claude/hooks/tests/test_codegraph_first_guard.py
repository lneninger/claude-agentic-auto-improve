#!/usr/bin/env python3
"""
test_codegraph_first_guard.py -- the CodeGraph-first gate: issue #612 (a read of a non-source file outside the
project is not gated) and issue #259 (the gate fails open when CodeGraph is provably unavailable, has a
single-use retry escape, keys its turn marker to the session, and never advises the shell).

House style: plain runnable script, NO pytest. check(name, cond, detail) accumulator,
PASS/FAIL/SKIP summary, non-zero exit on any failure (a skip never fails the run and is never a pass).

    py -3 .claude/hooks/tests/test_codegraph_first_guard.py

ISOLATION (contracts 2026-11-05-codegraph-guard-fail-open FM 1 and 2026-11-06-session-folder-owner-and-tool-named FM 1):
every row that reads server state or writes a Session folder runs with HOME, USERPROFILE and CLAUDE_CONFIG_DIR at a
fixture home folder, LOCALAPPDATA at <home>/AppData/Local, XDG_CACHE_HOME at <home>/.cache (so the Per-user session
parent, the only place the hooks keep Session folders since issue #271, is inside the fixture) and TMP, TEMP at a
fixture temp folder, and a fresh session_id. The developer's real home, real Per-user session parent and real temp
folder are never read or written: the closing checks fail on any new auto-improve-codegraph-* entry in the last two.

WHAT THIS PINS DOWN
  #612-A/B/C/D   unchanged (the in-process rows run under the same isolation)
  K-4            no kill switch; the block message is plain text: it names the uninstall skill, the retry escape,
                 the sync commands; it carries no references/ path, no CLAUDE_SKIP_CG, no shell route, no
                 individual CodeGraph tool name
  R-*            each fail-open reason (no-index, server-not-configured, server-disabled, subagent,
                 index-other-tree) on Read/Grep/Glob x .cs/.ts, one log record per session per reason, and the
                 positive controls that keep the gate shut when an index and a server exist
  E-*            the retry escape: single use, per call, per session, keyed to its prompt (issue #262)
  T-*            the Transcript turn state opens the gate for explore / search / an unknown future tool name and for a
                 subagent dispatch, follows the transcript across a directory change, and closes at the next human prompt
  CO-*, PR-*     the cut-over (issue #262): the three routes, the fail-open causes, tickets keyed to the prompt, the
                 cli-fallback record, the Measurement record, late effects forced to raise, and the prompt row
  O-*            index ownership over real and fixture git layouts, in three helper modes (bound, missing, older)
  P-*            parity between the guard and the installer (server rule, index ownership)
  U-*            worktree_own_root unit rows
  X-*            the session-folder pruner (now in the guard, C-5), through the before_remove seam (X-2b and X-4 bite without
                 file-symlink rights); it lists the Per-user session parent only and never the system temp folder (issue #271,
                 criterion 3)
  Q-*  (#271)    a planted folder in the shared temp folder opens no gate; the Per-user session parent rule (pure table,
                 every OS) and its problems on disk; fail closed (session-state-unusable, check-failed, announce,
                 retry-ticket-unwritten, link swap); the Foreign marker; the banner by reason; hook parity; the Hop proof
  U-H            review round: a hostile gitdir line (UNC, device path, no /.git/worktrees|modules/, 4096-byte cap) is
                 undecidable in the helper, the guard's inline copy, the bridge's inline copy and _git_file_kind
  S-*            review round: index verdict cached per cwd, the logged-<reason> flag after the record, 'X.' vs 'X'
  L-*            review round: no state write (availability.json, ticket-*, turn.json) goes through a hard link or symlink
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import inspect
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import types
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

# The hook is an ADD-ON file: it is found, and installed into a fixture project with its helpers, by the
# shared add-on fixture (beside this hooks folder first, else the plugin's add-on folder). A missing add-on
# FAILS this suite; it never skips.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _addon_fixture as af  # noqa: E402

ADD_ON = "codegraph"
HOOK_FILE = "codegraph-first-guard.py"
TRACKER_FILE = "codegraph-turn-tracker.py"
RESET_FILE = "codegraph-turn-reset.py"
SCRIPTS_DIR = af.PROJECT_ROOT / ".claude" / "scripts"

PASSED: list[str] = []
FAILED: list[str] = []
SKIPPED: list[str] = []

FILE_SYMLINK_REFUSED = "SKIP: file symlink refused by the OS (needs Developer Mode or admin)"


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASSED.append(name)
        print(f"PASS  {name}")
    else:
        FAILED.append(name)
        print(f"FAIL  {name}" + (f"\n        -> {detail}" if detail else ""))


def skip(name: str, reason: str) -> None:
    """A third outcome: not run here, for a stated reason. Never a failure, never counted as a pass."""
    SKIPPED.append(name)
    print(f"SKIP  {name}\n        -> {reason}")


def load_hook():
    """The installed guard, loaded in-process (for the #612 rows). The run's TMP/TEMP are already the fixture's."""
    hook = {p.name: p for p in af.install(ADD_ON)}[HOOK_FILE]
    spec = importlib.util.spec_from_file_location("codegraph_first_guard_under_test", hook)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_module(path: Path, name: str):
    """Any hook or helper file, loaded in-process under a unique module name."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------------------------------------------
# harness
# --------------------------------------------------------------------------------------------------------------
def sid() -> str:
    """A fresh session id (matches the Session key grammar): no two rows share a Session folder."""
    return "s" + uuid.uuid4().hex


def pfolder(sb: af.Sandbox, session: str, create: bool = False) -> Path:
    """The Session folder of ``session`` under the sandbox's Per-user session parent (created only when ``create``)."""
    return af.session_folder(af.session_parent(sb.home, create=create), session)


def blocked(proc: subprocess.CompletedProcess) -> bool:
    return proc.returncode == 2 and "[codegraph-first-guard] BLOCKED" in proc.stderr


def allowed(proc: subprocess.CompletedProcess, reason: str | None = None) -> bool:
    ok = proc.returncode == 0 and "internal error" not in proc.stderr
    if reason is not None:
        ok = ok and "[codegraph-first-guard] allowed" in proc.stderr and reason in proc.stderr
    return ok


def silent_allow(proc: subprocess.CompletedProcess) -> bool:
    """An allow with NO `allowed (<reason>)` line: the marker path (step 2) and the paths before it print nothing,
    while a fail-open and the retry escape always print one."""
    return allowed(proc) and "allowed (" not in proc.stderr


def describe(proc: subprocess.CompletedProcess) -> str:
    return "exit=%s stdout=%r stderr=%r" % (proc.returncode, proc.stdout[:200], proc.stderr[:600])


#: The default ``transcript`` of ``run_hook``: a CLOSED transcript (a human prompt and nothing after it). Since the
#: cut-over (issue #262) the guard decides from the transcript, so a row that expects a block must carry one (a payload
#: with no ``transcript_path`` fails open). Pass a Path for another state, or None for a payload with no transcript_path.
CLOSED = "closed"


def run_hook(hook: Path, sb: af.Sandbox, project: Path, tool: str, tool_input: dict, session: str,
             cwd: Path | None = None, payload_extra: dict | None = None, extra_env: dict | None = None,
             raw: str | None = None, event: str = "PreToolUse", transcript=CLOSED,
             argv: list | None = None) -> subprocess.CompletedProcess:
    """Run a hook as Claude Code does: JSON on stdin, the isolated environment, cwd = the payload cwd."""
    where = Path(cwd or project)
    where.mkdir(parents=True, exist_ok=True)
    payload = {"session_id": session, "cwd": str(where), "hook_event_name": event, "tool_name": tool,
               "tool_input": tool_input}
    if event == "PreToolUse" and transcript is not None:
        payload["transcript_path"] = str(af.closed_transcript(sb.root / "transcripts") if transcript is CLOSED else transcript)
    if payload_extra:
        payload.update(payload_extra)
    return subprocess.run([sys.executable, "-B", str(hook), *(argv or [])], input=raw if raw is not None else json.dumps(payload),
                          capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(where),
                          env=af.isolated_env(sb.home, sb.tmp, project, extra_env), timeout=60)


def calls(root: Path) -> list[tuple[str, str, dict]]:
    """Read, Grep and Glob on a .cs and a .ts target under ``root``/src."""
    src = root / "src"
    return [
        ("Read .cs", "Read", {"file_path": str(src / "Thing.cs")}),
        ("Read .ts", "Read", {"file_path": str(src / "thing.ts")}),
        ("Grep .cs", "Grep", {"pattern": "Thing", "path": str(src), "glob": "*.cs"}),
        ("Grep .ts", "Grep", {"pattern": "thing", "path": str(src), "glob": "*.ts"}),
        ("Glob .cs", "Glob", {"pattern": "**/*.cs", "path": str(src)}),
        ("Glob .ts", "Glob", {"pattern": "**/*.ts", "path": str(src)}),
    ]


def read_cs(root: Path) -> dict:
    return {"file_path": str(root / "src" / "Thing.cs")}


def events(project: Path, event: str | None = None) -> list[dict]:
    path = project / ".claude" / "logs" / "errors.jsonl"
    found = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return found
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("hook") == "codegraph-first-guard" and (event is None or rec.get("event") == event):
            found.append(rec)
    return found


def make_logs(project: Path) -> None:
    (project / ".claude" / "logs").mkdir(parents=True, exist_ok=True)


def clean_above(label: str, root: Path) -> bool:
    """Each no-index test first asserts that no ancestor of its fixture root holds a REAL codegraph.db."""
    found = af.ancestors_holding(root, *af.CODEGRAPH_INDEX)
    check(label + ": no ancestor of the fixture root holds a real " + "/".join(af.CODEGRAPH_INDEX), not found,
          "ancestor folders holding a real index: " + ", ".join(str(f) for f in found))
    return not found


STALE_HELPER = '''"""An older _project_paths.py: it has the functions the guard needed in release 0.15.1 and none of
tree_kind, main_checkout_root or worktree_own_root."""
import os
import re
from pathlib import Path

HOME = Path.home()


def project_dir():
    raw = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(raw).resolve() if raw else None


def logs_dir():
    proj = project_dir()
    return (proj / ".claude" / "logs") if proj else HOME / ".claude" / "logs"


def checkout_equivalent_path(path_str):
    return re.sub(r"/\\.claude/worktrees/[^/]+", "", str(path_str).replace("\\\\", "/"))


def enclosing_worktree_root(path_str):
    return None
'''


class World:
    """The guard installed three ways: with the shared helper (bound), without it (fallback mode) and beside an
    older helper that lacks the tree functions (stale)."""

    def __init__(self) -> None:
        self.sb = af.Sandbox("cghooks-")
        installed = {p.name: p for p in af.install(ADD_ON, self.sb.root / "installed")}
        self.guard = installed[HOOK_FILE]
        # The tracker and the reset hook are Disabled add-on hooks since the cut-over (issue #262): no install copies them. A
        # row that still looks at one of them (a parity row, a byte-identity row) installs them through the fixture's disabled path.
        disabled = {p.name: p for p in af.install_disabled(ADD_ON, self.sb.root / "installed")}
        self.tracker = disabled[TRACKER_FILE]
        self.reset = disabled[RESET_FILE]
        hooks_dir = self.guard.parent
        self.fallback = self.sb.root / "fallback" / HOOK_FILE
        self.stale = self.sb.root / "stale" / HOOK_FILE
        for target in (self.fallback, self.stale):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.guard, target)
            shutil.copyfile(hooks_dir / "_error_log.py", target.parent / "_error_log.py")
        (self.stale.parent / "_project_paths.py").write_text(STALE_HELPER, encoding="utf-8")
        self.modes = {"bound": self.guard, "fallback": self.fallback, "stale": self.stale}

    def close(self) -> None:
        self.sb.remove()


# --------------------------------------------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------------------------------------------
def project_of(sb: af.Sandbox, tag: str, git: str = "none", index: bool = True, server: bool = True) -> Path:
    """A project under its own fixture root. ``git``: none (a non-git project), undecidable (a .git FILE pointing
    nowhere), main (a .git FOLDER)."""
    project = sb.root / tag / "proj"
    (project / "src").mkdir(parents=True, exist_ok=True)
    if git == "undecidable":
        (project / ".git").write_text("gitdir: ../.git/worktrees/dummy\n", encoding="utf-8")
    elif git == "main":
        af.make_main_checkout(project)
    if index:
        af.plant_index(project)
    if server:
        af.plant_server(project)
    return project


# --------------------------------------------------------------------------------------------------------------
# K-4 and the message (I-2, I-3)
# --------------------------------------------------------------------------------------------------------------
LEGACY_NAME_RE = re.compile(r"\bcodegraph_(search|node|callers|callees|impact|files|status|context|explore)\b")


def run_k4(w: World) -> None:
    with af.Sandbox("cgk4-") as sb:
        project = project_of(sb, "k4")
        control = run_hook(w.guard, sb, project, "Read", read_cs(project), sid())
        check("K-4 control: with no switch set, a Read of a project source file is blocked (exit 2)",
              blocked(control), describe(control))
        for value in ("1", "on", "true", "yes", "off"):
            done = run_hook(w.guard, sb, project, "Read", read_cs(project), sid(), extra_env={"CLAUDE_SKIP_CG": value})
            check(f"K-4: CLAUDE_SKIP_CG={value} no longer bypasses the gate (exit 2)", blocked(done), describe(done))
        message = control.stderr
        for needle in ("mcp__codegraph__*", "/auto-improve-codegraph-uninstall", "new session",
                       "repeat this exact call once", "codegraph sync", "codegraph init -i",
                       "/auto-improve-codegraph-install"):
            check(f"K-4: the block message names {needle!r}", needle.lower() in message.lower(), message)
        retry_phrases = re.findall(r"if no [^\n.;,]{0,40}tool is available", message, re.IGNORECASE)
        check("K-4: the retry sentence states its condition ('if no ... tool is available') exactly once",
              len(retry_phrases) == 1, "found %d: %r in %s" % (len(retry_phrases), retry_phrases, message))
        check("K-4: the block message carries no references/ path", "references/" not in message, message)
        check("K-4: the block message does not name CLAUDE_SKIP_CG", "CLAUDE_SKIP_CG" not in message, message)
        check("K-4: the hook text does not name CLAUDE_SKIP_CG",
              "CLAUDE_SKIP_CG" not in w.guard.read_text(encoding="utf-8"))
        # I-2: no shell route, no individual tool name, for each of the three gated tools
        for label, tool, tool_input in calls(project)[::2]:
            done = run_hook(w.guard, sb, project, tool, tool_input, sid())
            text = done.stderr
            check(f"I-2 [{label}]: the block message advises no shell route (no `cat <path>`, no `sed`, no 'through the shell')",
                  blocked(done) and re.search(r"\b(cat|sed)\s", text) is None and "through the shell" not in text, text)
            check(f"I-2 [{label}]: the block message names no individual CodeGraph tool, prefixed or bare",
                  blocked(done) and "mcp__codegraph__codegraph_" not in text and LEGACY_NAME_RE.search(text) is None,
                  text)


# --------------------------------------------------------------------------------------------------------------
# #612 in-process rows (same assertions as before, under the isolated environment)
# --------------------------------------------------------------------------------------------------------------
def run_612() -> None:
    with af.Sandbox("cg612-") as sb, mock.patch.dict(os.environ, af.isolated_env(sb.home, sb.tmp), clear=True):
        saved_temp, saved_cwd = tempfile.tempdir, os.getcwd()
        tempfile.tempdir = str(sb.tmp)
        try:
            project = project_of(sb, "p612")
            outside = sb.root / "outside"
            outside.mkdir()
            os.chdir(str(project))
            try:
                guard = load_hook()
            except af.AddonFixtureError as exc:
                check("the codegraph add-on is available to this suite (hook, manifest and helpers exist)", False,
                      str(exc))
                return
            os.environ["CLAUDE_PROJECT_DIR"] = str(project)
            out_file = str(outside / "claude" / "tasks" / "abc123.output")
            out_text = str(outside / "notes" / "result.dat")

            check("#612-A: an extensionless-class file outside the project is allowed",
                  guard.classify_path(out_text) == "allowed", repr(guard.classify_path(out_text)))
            check("#612-B: a `.output` file outside the project is allowed",
                  guard.classify_path(out_file) == "allowed", repr(guard.classify_path(out_file)))
            decision, why = guard.decide("Read", {"file_path": out_file})
            check("#612-A: a Read of a background `.output` file is allowed with no CodeGraph call this turn",
                  decision == "allow", f"{decision}: {why}")

            # Positive controls: the gate must still be able to fire.
            inside_src = str(project / "src" / "Thing.cs")
            check("#612-C control: a source file inside the project is still gated",
                  guard.classify_path(inside_src) == "source", repr(guard.classify_path(inside_src)))
            closed_payload = {"session_id": sid(), "cwd": str(project),
                              "transcript_path": str(af.closed_transcript(sb.root / "tr612"))}
            decision, why = guard.decide("Read", {"file_path": inside_src}, closed_payload)
            check("#612-C control: a Read of a source file inside the project is blocked with no CodeGraph call",
                  decision == "block", f"{decision}: {why}")
            sibling_src = str(project / ".claude" / "worktrees" / "w2" / "src" / "Thing.cs")
            check("#612-C control: a source file inside a sibling worktree is still gated",
                  guard.classify_path(sibling_src) == "source", repr(guard.classify_path(sibling_src)))
            inside_unknown = str(project / "data" / "result.dat")
            check("#612-C control: an unknown extension inside the project stays gated (unknown)",
                  guard.classify_path(inside_unknown) == "unknown", repr(guard.classify_path(inside_unknown)))
            sibling_unknown = str(project / ".claude" / "worktrees" / "w2" / "data" / "result.dat")
            check("#612-C control: an unknown extension inside a sibling worktree stays gated (unknown)",
                  guard.classify_path(sibling_unknown) == "unknown", repr(guard.classify_path(sibling_unknown)))

            # A session started inside a worktree: the project dir is that worktree, a sibling worktree
            # is still inside the same main checkout and stays gated.
            wt = project / ".claude" / "worktrees" / "w1"
            wt.mkdir(parents=True)
            os.environ["CLAUDE_PROJECT_DIR"] = str(wt)
            check("#612-C control: with the project dir set to a worktree, a sibling worktree's unknown file stays gated",
                  guard.classify_path(sibling_unknown) == "unknown", repr(guard.classify_path(sibling_unknown)))
            check("#612-A: with the project dir set to a worktree, a file outside the whole checkout is allowed",
                  guard.classify_path(out_file) == "allowed", repr(guard.classify_path(out_file)))

            # #612-D a source extension outside the project stays gated.
            os.environ["CLAUDE_PROJECT_DIR"] = str(project)
            outside_src = str(outside / "other-repo" / "Thing.py")
            check("#612-D: a source-code file outside the project stays gated",
                  guard.classify_path(outside_src) == "source", repr(guard.classify_path(outside_src)))

            # Fail toward gating when the project root is unknown.
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
            check("#612-C control: with no project root known, the outside `.dat` file is NOT widened (unknown)",
                  guard.classify_path(out_text) == "unknown", repr(guard.classify_path(out_text)))
        finally:
            os.chdir(saved_cwd)
            tempfile.tempdir = saved_temp


# --------------------------------------------------------------------------------------------------------------
# R-*: the five fail-open reasons, and the positive controls
# --------------------------------------------------------------------------------------------------------------
def run_reasons(w: World) -> None:
    with af.Sandbox("cgr-") as sb:
        # R-1 no-index: an undecidable tree, a non-git folder, and the twin with an index for each
        for git in ("none", "undecidable", "main"):
            tag = "noidx-" + git
            project = project_of(sb, tag, git=git, index=False)
            if not clean_above("R-1 no-index (%s project)" % git, project):
                continue
            for label, tool, tool_input in calls(project):
                proc = run_hook(w.guard, sb, project, tool, tool_input, sid())
                check(f"R-1 no-index ({git} project): {label} is allowed, reason fail-open:no-index",
                      allowed(proc, "fail-open:no-index"), describe(proc))
            twin = project_of(sb, tag + "-twin", git=git, index=True)
            for label, tool, tool_input in calls(twin):
                proc = run_hook(w.guard, sb, twin, tool, tool_input, sid())
                check(f"R-1 twin with codegraph.db ({git} project): {label} stays BLOCKED [control]",
                      blocked(proc), describe(proc))

        # R-1b one log record per session per reason
        project = project_of(sb, "noidx-log", index=False)
        make_logs(project)
        session = sid()
        for _ in range(2):
            run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        got = events(project, "fail-open")
        check("R-1b: two fail-open calls in one session write exactly ONE fail-open log record",
              len(got) == 1, "records: %r" % got)
        check("R-1b: the record names the reason no-index", bool(got) and "no-index" in json.dumps(got[0]), repr(got))
        run_hook(w.guard, sb, project, "Read", read_cs(project), sid())
        check("R-1b: a second session logs its own record (one per session per reason)",
              len(events(project, "fail-open")) == 2, repr(events(project, "fail-open")))

        # R-1c the decoy: ~/.codegraph-shaped folder (no codegraph.db) in a PARENT does not count as an index
        parent = sb.root / "decoyparent"
        proj = parent / "proj"
        (proj / "src").mkdir(parents=True)
        af.plant_server(proj)
        af.plant_decoy(parent)
        if clean_above("R-1c decoy", parent):
            proc = run_hook(w.guard, sb, proj, "Read", read_cs(proj), sid())
            check("R-1c: a .codegraph folder WITHOUT codegraph.db (daemons/, telemetry.json) in a parent: no-index still fires",
                  allowed(proc, "fail-open:no-index"), describe(proc))
            af.plant_index(parent)
            proc = run_hook(w.guard, sb, proj, "Read", read_cs(proj), sid())
            check("R-1c: the same decoy folder WITH codegraph.db: the gate stays [control]", blocked(proc), describe(proc))
        proj2 = sb.root / "decoyin" / "proj"
        (proj2 / "src").mkdir(parents=True)
        af.plant_server(proj2)
        af.plant_decoy(proj2)
        if clean_above("R-1c decoy in the project", proj2):
            proc = run_hook(w.guard, sb, proj2, "Read", read_cs(proj2), sid())
            check("R-1c: a decoy .codegraph INSIDE the project (no codegraph.db): no-index fires",
                  allowed(proc, "fail-open:no-index"), describe(proc))

        # R-2 server not configured
        project = project_of(sb, "noserver", server=False)
        for label, tool, tool_input in calls(project):
            proc = run_hook(w.guard, sb, project, tool, tool_input, sid())
            check(f"R-2 no server: {label} is allowed, reason fail-open:server-not-configured",
                  allowed(proc, "fail-open:server-not-configured"), describe(proc))
        # R-3 server disabled
        project = project_of(sb, "disabled")
        af.plant_server(project, disabled=True)
        for label, tool, tool_input in calls(project):
            proc = run_hook(w.guard, sb, project, tool, tool_input, sid())
            check(f"R-3 disabled server: {label} is allowed, reason fail-open:server-disabled",
                  allowed(proc, "fail-open:server-disabled"), describe(proc))
        # R-3b a decoy disabledMcpjsonServers outside the read layers is ignored
        project = project_of(sb, "decoydisabled")
        decoys = [project / ".claude" / "settings.decoy.json", sb.home / "decoy" / "settings.json"]
        for decoy in decoys:
            decoy.parent.mkdir(parents=True, exist_ok=True)
            decoy.write_text(json.dumps({"disabledMcpjsonServers": ["codegraph"]}), encoding="utf-8")
        proc = run_hook(w.guard, sb, project, "Read", read_cs(project), sid())
        check("R-3b: a disabledMcpjsonServers entry in a file outside the read layers is ignored: the gate stays [control]",
              blocked(proc), describe(proc))

        # R-4 subagent
        project = project_of(sb, "subagent")
        extra = {"agent_id": "agent-" + uuid.uuid4().hex[:8], "agent_type": "general-purpose"}
        for label, tool, tool_input in calls(project):
            proc = run_hook(w.guard, sb, project, tool, tool_input, sid(), payload_extra=extra)
            check(f"R-4 subagent (agent_id + agent_type): {label} is allowed, reason fail-open:subagent",
                  allowed(proc, "fail-open:subagent"), describe(proc))
            proc = run_hook(w.guard, sb, project, tool, tool_input, sid())
            check(f"R-4 the same call WITHOUT agent_id is BLOCKED [control]: {label}", blocked(proc), describe(proc))
        proc = run_hook(w.guard, sb, project, "Read", read_cs(project), sid(), payload_extra={"agent_id": ""})
        check("R-4 an EMPTY agent_id is not a subagent: BLOCKED [control]", blocked(proc), describe(proc))

        # I-1 positive controls: index + server, no agent_id, no marker
        for git in ("none", "undecidable", "main"):
            project = project_of(sb, "i1-" + git, git=git)
            proc = run_hook(w.guard, sb, project, "Read", read_cs(project), sid())
            check(f"I-1 positive control ({git} project): index + configured server + no agent_id + no marker -> BLOCKED",
                  blocked(proc), describe(proc))

        # step 2 (was step 0, issue #271): an unusable Session folder FAILS CLOSED with session-state-unusable, says why,
        # and offers no retry. Each row has a positive control: the same fixture with a usable folder blocks as
        # source-target and then allows its retry.
        project = project_of(sb, "step0")
        make_logs(project)
        session = sid()
        target = sb.root / "step0-link-target"
        target.mkdir()
        af.session_parent(sb.home)  # a usable Per-user session parent
        link = pfolder(sb, session)
        if af.make_dir_link(link, target):
            proc = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
            check("step 2: a Session folder that is a link BLOCKS (session-state-unusable), problem session-link",
                  blocked(proc) and "session-state-unusable" in json.dumps(events(project, "block")) + proc.stderr
                  and names_problem(proc.stderr, project, "session-link"), describe(proc))
            check("step 2: and the block offers no retry line", "repeat this exact call" not in proc.stderr, describe(proc))
            check("step 2: and nothing was written through the link", not any(target.iterdir()),
                  "target holds: %s" % [p.name for p in target.iterdir()])
            try:
                os.rmdir(str(link))
            except OSError:
                pass
        else:
            skip("step 2: a Session folder that is a link", "the OS refused to create a folder link")
        # review fix round T-M3: this row has its OWN project (and so its own log), so the link row's record above can
        # never satisfy it, and the record's problem FIELD is compared exactly
        file_project = project_of(sb, "step0-file")
        make_logs(file_project)
        session = sid()
        pfolder(sb, session).write_text("not a folder\n", encoding="utf-8")
        proc = run_hook(w.guard, sb, file_project, "Read", read_cs(file_project), session)
        check("step 2: a Session folder path that is a plain FILE BLOCKS (session-state-unusable), problem "
              "session-not-a-folder", blocked(proc) and names_problem(proc.stderr, file_project, "session-not-a-folder"),
              describe(proc))
        check("step 2: and the block is logged once per call with reason session-state-unusable and the exact problem "
              "field session-not-a-folder", unusable_records(file_project) == ["session-not-a-folder"],
              repr(events(file_project, "block")))
        usable = sid()
        first = run_hook(w.guard, sb, project, "Read", read_cs(project), usable)
        retry = run_hook(w.guard, sb, project, "Read", read_cs(project), usable)
        check("step 2 [control]: with a usable Session folder the same call blocks as source-target and its retry is "
              "allowed", blocked(first) and "session-state-unusable" not in first.stderr
              and allowed(retry, "retry-escape-used"), describe(first) + " / " + describe(retry))

        # I-4: an internal error / unreadable payload allows
        proc = run_hook(w.guard, sb, project, "Read", {}, sid(), raw="{not json")
        check("I-4 [control]: an unparsable payload allows (exit 0)", proc.returncode == 0, describe(proc))
        # I-4 on the TOP-LEVEL catch-all (not the explicit JSON-decode branch): an exception that escapes main() must
        # still allow, with the `internal error (failing open)` line. Two ways to make one escape.
        proc = run_hook(w.guard, sb, project, "Read", {}, sid(),
                        raw=json.dumps({"session_id": sid(), "cwd": str(project), "tool_name": ["Read"],
                                        "tool_input": {"file_path": str(project / "src" / "Thing.cs")}}))
        check("I-4: an unhashable tool_name raises inside main(); the catch-all allows (exit 0, 'internal error (failing open)')",
              proc.returncode == 0 and "internal error (failing open)" in proc.stderr, describe(proc))
        hostile = project_of(sb, "i4-hostile")
        (hostile / ".claude").mkdir(exist_ok=True)
        (hostile / ".claude" / "settings.json").write_text("[" * 200000, encoding="utf-8")
        proc = run_hook(w.guard, sb, hostile, "Read", read_cs(hostile), sid())
        check("I-4: a hostile settings file (nesting deep enough to raise RecursionError) escapes evaluate; the catch-all allows",
              proc.returncode == 0 and "internal error (failing open)" in proc.stderr, describe(proc))
        twin = project_of(sb, "i4-hostile-twin")
        proc = run_hook(w.guard, sb, twin, "Read", read_cs(twin), sid())
        check("I-4 [control]: the same project without the hostile file is BLOCKED", blocked(proc), describe(proc))

        # step 8 (was step 7, issue #271): a ticket that cannot be written BLOCKS with retry-ticket-unwritten, never
        # allows (a folder sits in the ticket's place, so the Session folder stays usable and only the ticket write fails)
        project = project_of(sb, "step7")
        make_logs(project)
        guard_mod = load_module(w.guard, "codegraph_first_guard_step7")
        session = sid()
        folder = pfolder(sb, session, True)
        folder.mkdir()
        (folder / ("ticket-" + guard_mod.call_fingerprint("Read", read_cs(project)))).mkdir()
        proc = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        check("step 8: a ticket that cannot be written BLOCKS (retry-ticket-unwritten) and does not allow",
              blocked(proc) and not allowed(proc) and "fail-open:state-unwritable" not in proc.stderr, describe(proc))
        check("step 8: and the block is logged with reason retry-ticket-unwritten",
              any("retry-ticket-unwritten" in json.dumps(rec) for rec in events(project, "block")),
              repr(events(project, "block")))
        project = project_of(sb, "step7-twin")
        proc = run_hook(w.guard, sb, project, "Read", read_cs(project), sid())
        check("step 8 [control]: the same call with a writable Session folder is BLOCKED as source-target, with its "
              "retry line", blocked(proc) and "repeat this exact call once; it will be allowed and logged" in proc.stderr,
              describe(proc))


# --------------------------------------------------------------------------------------------------------------
# E-*: the retry escape
# --------------------------------------------------------------------------------------------------------------
def run_escape(w: World) -> None:
    with af.Sandbox("cge-") as sb:
        project = project_of(sb, "esc")
        make_logs(project)
        session = sid()
        first = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        check("E-1: the first call is BLOCKED and issues a ticket [control]", blocked(first), describe(first))
        other = run_hook(w.guard, sb, project, "Read", {"file_path": str(project / "src" / "Other.cs")}, session)
        check("E-2: a DIFFERENT call is not covered by the ticket: BLOCKED [control]", blocked(other), describe(other))
        retry = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        check("E-3: the identical retry is allowed (retry-escape-used)",
              allowed(retry) and "retry-escape-used" in retry.stderr, describe(retry))
        check("E-3b: the use is logged as event retry-escape", len(events(project, "retry-escape")) == 1,
              repr(events(project)))
        again = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        check("E-4: the escape is SINGLE USE: the third identical call is BLOCKED again", blocked(again), describe(again))
        # a ticket is scoped to its session
        s1, s2 = sid(), sid()
        run_hook(w.guard, sb, project, "Read", read_cs(project), s1)
        cross = run_hook(w.guard, sb, project, "Read", read_cs(project), s2)
        check("E-5: a ticket issued in one session does not open another session: BLOCKED [control]",
              blocked(cross), describe(cross))
        # a ticket is keyed to its prompt (issue #262): the next prompt cannot use it, and its fresh block overwrites it
        s3 = sid()
        run_hook(w.guard, sb, project, "Read", read_cs(project), s3, payload_extra={"prompt_id": "prompt-one"})
        after = run_hook(w.guard, sb, project, "Read", read_cs(project), s3, payload_extra={"prompt_id": "prompt-two"})
        check("E-6: a ticket does not survive into the next prompt: the identical call under another prompt_id is BLOCKED again",
              blocked(after), describe(after))
        tickets = list(pfolder(sb, s3).glob("ticket-*")) if pfolder(sb, s3).is_dir() else []
        check("E-6b: only the fresh block's ticket remains (it overwrote the stale one; no hook deletes tickets at a prompt)",
              len(tickets) == 1, "tickets: %s" % [t.name for t in tickets])
        retry = run_hook(w.guard, sb, project, "Read", read_cs(project), s3, payload_extra={"prompt_id": "prompt-two"})
        check("E-6c: and the identical retry inside that second prompt is allowed", allowed(retry, "retry-escape-used"), describe(retry))
        # the ticket name carries a 64 hex call fingerprint
        s4 = sid()
        run_hook(w.guard, sb, project, "Read", read_cs(project), s4)
        names = [p.name for p in pfolder(sb, s4).glob("ticket-*")] \
            if pfolder(sb, s4).is_dir() else []
        check("E-7: a block writes ticket-<64 hex fingerprint> in the Session folder",
              len(names) == 1 and re.fullmatch(r"ticket-[0-9a-f]{64}", names[0]) is not None, "tickets: %s" % names)


# --------------------------------------------------------------------------------------------------------------
# T-*: the Transcript turn state opens and closes the gate (the tracker, marker and reset hook are retired)
# --------------------------------------------------------------------------------------------------------------
def append_lines(path: Path, *lines: str) -> None:
    """Append ``lines`` to a transcript: a session's transcript only grows."""
    with open(path, "ab") as fh:
        fh.write(("\n".join(lines) + "\n").encode("utf-8"))


def run_marker(w: World) -> None:
    with af.Sandbox("cgt-") as sb:
        H = af.t_human
        cases = [
            ("codegraph_explore", "mcp__codegraph__codegraph_explore"),
            ("codegraph_search", "mcp__codegraph__codegraph_search"),
            ("an unknown future tool name (codegraph_zz_future_tool)", "mcp__codegraph__codegraph_zz_future_tool"),
        ]
        for number, (label, tool) in enumerate(cases):
            project = project_of(sb, "trk-%d" % number)  # a fresh project per case: no leaked legacy sentinel
            session = sid()
            transcript = fresh_transcript(sb, [H(1)])
            before = cut(w, sb, project, None, session, path=transcript)
            check(f"T-1 control [{label}]: blocked before the CodeGraph call", blocked(before), describe(before))
            append_lines(transcript, af.t_mcp_use(tool), af.t_tool_result())
            after = cut(w, sb, project, None, session, path=transcript)
            # The blocked call above issued a retry ticket for this exact Read, so the retry escape would also let it through:
            # only the ABSENCE of an `allowed (` line proves that the transcript did it.
            check(f"T-1 [{label}]: after the tool use the same Read is allowed by the TRANSCRIPT (no `allowed (` line: not the "
                  "retry escape)", silent_allow(after), describe(after))
            folder = pfolder(sb, session)
            check(f"T-1 [{label}]: and no turn.json, no mcp-seen and no legacy sentinel is written (the tracker is retired)",
                  not (folder / "turn.json").exists() and not (folder / "mcp-seen").exists()
                  and not (project / ".claude" / ".codegraph-used-this-turn").exists(), sorted(p.name for p in folder.iterdir()))
            fresh = cut(w, sb, project, [H(1)])
            check(f"T-1 [{label}]: and a FRESH session with its own closed transcript is still BLOCKED [control]", blocked(fresh),
                  describe(fresh))

        project = project_of(sb, "trk-other")
        # a tool that is not a CodeGraph tool opens nothing
        for tool in ("Bash", "mcp__other__codegraph_search"):
            line = af.t_assistant({"type": "tool_use", "id": "t", "name": tool, "input": {"command": "ls"}})
            proc = cut(w, sb, project, [H(1), line])
            check(f"T-2: {tool} does not open the gate", blocked(proc), describe(proc))

        # the gate follows the transcript across a directory change (cd / EnterWorktree)
        session = sid()
        here, there = project / "src", project / "elsewhere" / "deeper"
        transcript = fresh_transcript(sb, [H(1), af.t_mcp_use("mcp__codegraph__codegraph_explore")])
        run_hook(w.guard, sb, project, "Read", read_cs(project), session, cwd=here, transcript=transcript)
        moved = run_hook(w.guard, sb, project, "Read", read_cs(project), session, cwd=there, transcript=transcript)
        check("T-3: the same session's transcript opens the gate for a call made with another cwd", allowed(moved), describe(moved))
        other = run_hook(w.guard, sb, project, "Read", read_cs(project), sid(), cwd=there)
        check("T-3: another session with its own closed transcript is BLOCKED [control]", blocked(other), describe(other))

        # a new human prompt closes the gate again (no hook deletes anything)
        session = sid()
        transcript = fresh_transcript(sb, [H(1), af.t_mcp_use(), af.t_tool_result()])
        opened = cut(w, sb, project, None, session, path=transcript)
        append_lines(transcript, H(2))
        closed = cut(w, sb, project, None, session, path=transcript)
        check("T-4: open, then a new human prompt: the guard blocks the same Read again",
              silent_allow(opened) and blocked(closed), describe(opened) + " / " + describe(closed))

        # the legacy sentinel no longer opens the gate (it is not even cleaned up any more)
        legacy = project / ".claude" / ".codegraph-used-this-turn"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text("legacy\n", encoding="utf-8")
        proc = cut(w, sb, project, [H(1)])
        check("T-5: a legacy <cwd>/.claude/.codegraph-used-this-turn does NOT open the gate: BLOCKED", blocked(proc), describe(proc))
        legacy.unlink()

        # a subagent's own call is allowed at step 3 (its transcript is another file and is never read)
        sub = cut(w, sb, project, [H(1)], extra={"agent_id": "a1", "agent_type": "general-purpose"})
        check("T-6: a subagent's own Read is allowed at step 3 (fail-open:subagent), not by the parent's transcript",
              allowed(sub, "fail-open:subagent"), describe(sub))
        # T-7: where it matters: the main session dispatched the subagent (C-7), so its own next Read is allowed
        before = cut(w, sb, project, [H(1)])
        check("T-7 control: the main session's Read is blocked before any dispatch", blocked(before), describe(before))
        parent = cut(w, sb, project, [H(1), af.t_agent_use(), af.t_tool_result()])
        check("T-7: an Agent dispatch in the current turn opens the gate for the main session: allowed, no `allowed (` line",
              silent_allow(parent), describe(parent))

        # the hook files never use is_junction / isjunction (Python 3.12+ only)
        for hook in (w.reset, w.tracker, w.guard):
            text = hook.read_text(encoding="utf-8")
            check(f"I-5 [control]: {hook.name} does not use is_junction / isjunction",
                  "is_junction" not in text and "isjunction" not in text)


# --------------------------------------------------------------------------------------------------------------
# O-*: index ownership over git layouts, in three helper modes
# --------------------------------------------------------------------------------------------------------------
def ownership_fixtures(sb: af.Sandbox) -> list[dict]:
    """Each fixture: name, project (CLAUDE_PROJECT_DIR), cwd, and the reason expected from the guard per helper mode
    (None = the gate stays). ``installer`` is the class the installer's index note must report."""
    out: list[dict] = []
    for layout in ("inside", "outside"):
        for form in ("absolute", "relative"):
            for variant in ("main-index-only", "own-index", "own-index-server-in-main-only"):
                tag = "wt-%s-%s-%s" % (layout, form, variant)
                info = af.make_linked_worktree(sb.root / tag, layout=layout, gitdir_form=form)
                wt, main = info["worktree"], info["main"]
                (wt / "src" / "deep").mkdir(parents=True, exist_ok=True)
                af.plant_index(main)
                af.plant_server(main)
                if variant != "main-index-only":
                    af.plant_index(wt)
                if variant != "own-index-server-in-main-only":
                    af.plant_server(wt)
                other_tree = variant == "main-index-only"
                out.append({
                    "name": "%s layout, %s gitdir, %s" % (layout, form, variant), "project": wt, "cwd": wt / "src" / "deep",
                    "root": wt, "bound": "fail-open:index-other-tree" if other_tree else None, "fallback": None,
                    "stale": None, "installer": "index-other-tree" if other_tree else "index-present",
                    "installer_ok": variant != "own-index-server-in-main-only"})
    return out


def run_ownership(w: World) -> None:
    with af.Sandbox("cgo-") as sb:
        if not clean_above("O-*", sb.root):
            return
        for fx in ownership_fixtures(sb):
            for mode, hook in w.modes.items():
                proc = run_hook(hook, sb, fx["project"], "Read", read_cs(fx["root"]), sid(), cwd=fx["cwd"])
                want = fx[mode]
                label = f"O-1 [{mode} helper] {fx['name']}"
                if want is None:
                    check(f"{label}: the gate stays (BLOCKED)", blocked(proc), describe(proc))
                else:
                    check(f"{label}: allowed, reason {want}", allowed(proc, want), describe(proc))
        # an undecidable tree, a non-git folder and a main checkout WITHOUT any index never fire index-other-tree
        for mode, hook in w.modes.items():
            project = project_of(sb, "O-undec-" + mode, git="undecidable", index=False)
            proc = run_hook(hook, sb, project, "Read", read_cs(project), sid())
            check(f"O-2 [{mode} helper]: an undecidable tree with no index fails open as no-index (never index-other-tree)",
                  allowed(proc, "fail-open:no-index"), describe(proc))
            project = project_of(sb, "O-nongit-" + mode, git="none", index=True)
            proc = run_hook(hook, sb, project, "Read", read_cs(project), sid())
            check(f"O-3 [{mode} helper]: a non-git project WITH an index and a server keeps the gate [control]",
                  blocked(proc), describe(proc))


def run_server_only_under_main(w: World) -> None:
    """A worktree session whose server sits ONLY under the main checkout's path stays gated, in both layouts, with
    the helper bound and under Guard fallback mode (the worktree owns an index, so rule (2) cannot fire)."""
    with af.Sandbox("cgm-") as sb:
        for layout in ("inside", "outside"):
            info = af.make_linked_worktree(sb.root / layout, layout=layout, gitdir_form="absolute")
            wt, main = info["worktree"], info["main"]
            (wt / "src").mkdir(parents=True, exist_ok=True)
            af.plant_index(main)
            af.plant_index(wt)
            af.plant_server(main)
            for mode, hook in w.modes.items():
                proc = run_hook(hook, sb, wt, "Read", read_cs(wt), sid())
                check(f"O-4 [{mode} helper, {layout} layout]: server only under the main checkout's path: the gate stays",
                      blocked(proc), describe(proc))


# --------------------------------------------------------------------------------------------------------------
# P-*: parity with the installer
# --------------------------------------------------------------------------------------------------------------
def load_installer():
    # the scripts folder stays on sys.path: the installer imports its sibling helpers lazily
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import auto_improve_finish_install as fi  # noqa: WPS433
    return fi


def run_parity_server(w: World) -> None:
    try:
        fi = load_installer()
        state = getattr(fi, "_mcp_server_state")
    except Exception as exc:  # noqa: BLE001
        check("P-1: the installer's _mcp_server_state can be loaded for the parity rows", False, repr(exc))
        return
    with af.Sandbox("cgp-") as sb:
        def scenario(name, build):
            project = project_of(sb, "p1-" + re.sub(r"\W+", "-", name), server=False)
            build(project)
            with mock.patch.dict(os.environ, {"HOME": str(sb.home), "USERPROFILE": str(sb.home)}):
                ok = bool(state("codegraph", project, sb.home)["ok"])
            proc = run_hook(w.guard, sb, project, "Read", read_cs(project), sid())
            guard_says_ok = blocked(proc)  # a configured, enabled server keeps the gate shut
            check(f"P-1 server rule parity: {name} (installer says ok={ok}, guard keeps the gate={guard_says_ok})",
                  guard_says_ok == ok and (ok or allowed(proc)), describe(proc))

        server = {"command": "codegraph", "args": ["serve"]}
        scenario("project .mcp.json with a command", lambda p: af.plant_server(p))
        scenario("no entry anywhere", lambda p: None)
        scenario("an entry with no command and no url",
                 lambda p: (p / ".mcp.json").write_text(json.dumps({"mcpServers": {"codegraph": {}}}), encoding="utf-8"))
        scenario("listed in the project's settings.json disabledMcpjsonServers", lambda p: af.plant_server(p, disabled=True))

        def local_disabled(p):
            af.plant_server(p)
            (p / ".claude").mkdir(exist_ok=True)
            (p / ".claude" / "settings.local.json").write_text(json.dumps({"disabledMcpjsonServers": ["codegraph"]}),
                                                                 encoding="utf-8")
        scenario("listed in settings.local.json disabledMcpjsonServers", local_disabled)

        def user_disabled(p):
            af.plant_server(p)
            (sb.home / "settings.json").write_text(json.dumps({"disabledMcpjsonServers": ["codegraph"]}), encoding="utf-8")
        scenario("listed in the user's settings.json disabledMcpjsonServers", user_disabled)
        if (sb.home / "settings.json").exists():
            (sb.home / "settings.json").unlink()

        def user_server(p):
            (sb.home / ".claude.json").write_text(json.dumps({"mcpServers": {"codegraph": server}}), encoding="utf-8")
        scenario("defined in the user's .claude.json", user_server)

        def user_project_entry(p):
            (sb.home / ".claude.json").write_text(json.dumps({"projects": {str(p): {"mcpServers": {"codegraph": server}}}}),
                                                  encoding="utf-8")
        scenario("defined in .claude.json under THIS project's path", user_project_entry)

        def other_project_entry(p):
            (sb.home / ".claude.json").write_text(json.dumps({"projects": {str(p.parent / "other"): {
                "mcpServers": {"codegraph": server}}}}), encoding="utf-8")
        scenario("defined in .claude.json under ANOTHER project's path", other_project_entry)
        if (sb.home / ".claude.json").exists():
            (sb.home / ".claude.json").unlink()


def classify_note(notes: list[str]) -> str:
    text = "\n".join(str(n) for n in notes).lower()
    if "belongs to the main checkout" in text:
        return "index-other-tree"
    if "no index" in text:
        return "no-index"
    return "index-present"


def run_parity_ownership(w: World) -> None:
    try:
        fi = load_installer()
    except Exception as exc:  # noqa: BLE001
        check("P-2: the installer can be loaded for the parity rows", False, repr(exc))
        return
    with af.Sandbox("cgq-") as sb:
        if not clean_above("P-2", sb.root):
            return
        fixtures = [fx for fx in ownership_fixtures(sb) if fx["installer_ok"]]
        for tag, git, index in (("nongit-idx", "none", True), ("nongit-noidx", "none", False),
                                ("undec-noidx", "undecidable", False), ("main-idx", "main", True),
                                ("main-noidx", "main", False)):
            project = project_of(sb, "p2-" + tag, git=git, index=index)
            fixtures.append({"name": tag, "project": project, "cwd": project, "root": project,
                             "bound": None if index else "fail-open:no-index",
                             "installer": "index-present" if index else "no-index"})
        decoy = project_of(sb, "p2-decoy", git="none", index=False)
        af.plant_decoy(decoy)
        fixtures.append({"name": "decoy .codegraph without codegraph.db", "project": decoy, "cwd": decoy, "root": decoy,
                         "bound": "fail-open:no-index", "installer": "no-index", "decoy": True})
        for fx in fixtures:
            with mock.patch.dict(os.environ, {"HOME": str(sb.home), "USERPROFILE": str(sb.home)}):
                plan = fi.plan_addon(fx["project"], ADD_ON, claude_home=sb.home, plugin_root=af.plugin_root())
            notes = plan.get("notes", []) if isinstance(plan, dict) else []
            installer_says = classify_note(notes)
            proc = run_hook(w.guard, sb, fx["project"], "Read", read_cs(fx["root"]), sid(), cwd=fx["cwd"])
            guard_says = ("index-present" if blocked(proc) else
                          "index-other-tree" if "index-other-tree" in proc.stderr else
                          "no-index" if "no-index" in proc.stderr else "other: " + proc.stderr[:120])
            check(f"P-2 ownership parity: {fx['name']} -> expected {fx['installer']}; guard says {guard_says}, installer note says {installer_says}",
                  isinstance(plan, dict) and plan.get("status") == "plan" and guard_says == installer_says == fx["installer"],
                  "plan=%r notes=%r guard=%s" % ({k: plan.get(k) for k in ("status", "code", "message")}
                                                  if isinstance(plan, dict) else plan, notes, describe(proc)))
            if fx.get("decoy"):
                check("P-2: the installer names a .codegraph without codegraph.db as 'not an index'",
                      "not an index" in "\n".join(str(n) for n in notes).lower(), repr(notes))


# --------------------------------------------------------------------------------------------------------------
# U-*: worktree_own_root unit rows (loaded straight from the shared helper source)
# --------------------------------------------------------------------------------------------------------------
FAKE_HOST = "fake-host-259.invalid"
OTHER_HOST = "other-host-259.invalid"
NEITHER_MARKER = "a gitdir holding neither /.git/worktrees/ nor /.git/modules/"
HOSTILE_GITDIRS = [
    ("a UNC gitdir written with forward slashes", "gitdir: //%s/share/.git/worktrees/wt\n" % FAKE_HOST),
    ("a UNC gitdir written with backslashes", "gitdir: \\\\%s\\share\\.git\\worktrees\\wt\n" % FAKE_HOST),
    ("a device-path gitdir (\\\\?\\UNC\\host\\share)",
     "gitdir: \\\\?\\UNC\\%s\\share\\.git\\worktrees\\wt\n" % FAKE_HOST),
    ("a device-path gitdir (\\\\?\\C:\\...)", "gitdir: \\\\?\\C:\\fake259\\.git\\worktrees\\wt\n"),
    ("a device-path gitdir (\\\\.\\host)", "gitdir: \\\\.\\%s\\.git\\worktrees\\wt\n" % FAKE_HOST),
    (NEITHER_MARKER, "gitdir: ../elsewhere-259\n"),
    ("a first line over 4096 bytes whose /.git/worktrees/ marker lies beyond the 4096-byte cap",
     "gitdir: " + "a" * 5000 + "/.git/worktrees/wt\n"),
]


@contextmanager
def watch_fake_host(touched: list):
    """Every file-system probe of a path under the fake host is RECORDED and answered without touching the network
    (False, an OSError, or the path itself for realpath); every other path goes to the real function."""
    import builtins
    from contextlib import ExitStack

    def aimed(arg) -> bool:
        try:
            text = os.fspath(arg)
        except TypeError:
            return False
        text = text.decode("utf-8", "replace") if isinstance(text, bytes) else text
        return FAKE_HOST in text.lower() or OTHER_HOST in text.lower()

    def wrap(owner, name, fallback):
        real = getattr(owner, name)

        def inner(path, *args, **kwargs):
            if aimed(path):
                touched.append("%s(%s)" % (name, os.fspath(path)))
                if fallback is OSError:
                    raise OSError("the test refuses to touch %s" % FAKE_HOST)
                return path if fallback == "path" else fallback
            return real(path, *args, **kwargs)
        return mock.patch.object(owner, name, inner)

    with ExitStack() as stack:
        for owner, name, fallback in ((os.path, "isdir", False), (os.path, "isfile", False), (os.path, "exists", False),
                                      (os.path, "islink", False), (os.path, "realpath", "path"), (os, "stat", OSError),
                                      (os, "lstat", OSError), (os, "listdir", OSError), (builtins, "open", OSError)):
            stack.enter_context(wrap(owner, name, fallback))
        yield


def hostile_gitdir_fixtures(base: Path) -> list:
    """[(description, folder F holding the .git file, a path below F)] -- one .git FILE per hostile gitdir line."""
    out = []
    (Path(base) / "elsewhere-259").mkdir(parents=True, exist_ok=True)
    for number, (desc, line) in enumerate(HOSTILE_GITDIRS):
        folder = Path(base) / ("hostile-%d" % number)
        deep = folder / "src" / "deep"
        deep.mkdir(parents=True, exist_ok=True)
        (folder / ".git").write_text(line, encoding="utf-8")
        out.append((desc, folder, deep))
    return out


def run_hostile_own_root(label: str, fn, base: Path) -> None:
    """Security W3: a gitdir that is a UNC or device path, holds neither /.git/worktrees/ nor /.git/modules/, or sits
    beyond a 4096-byte first line is UNDECIDABLE: (F, None). No path under the fake host is ever probed."""
    for desc, folder, deep in hostile_gitdir_fixtures(base):
        touched: list = []
        try:
            with watch_fake_host(touched):
                got = fn(str(deep))
        except Exception as exc:  # noqa: BLE001
            check(f"U-H [{label}]: {desc} -> (F, None)", False, "raised %r" % (exc,))
            continue
        shape = ((af.canon(got[0]), af.canon(got[1]) if got[1] is not None else None)
                 if isinstance(got, (tuple, list)) and len(got) == 2 else got)
        check(f"U-H [{label}]: {desc} -> (F, None), an undecidable tree", shape == (af.canon(folder), None),
              "got %r, expected (%s, None)" % (got, folder))
        check(f"U-H [{label}]: {desc} -> no path under the fake host is probed", not touched, "probed: %s" % touched)
    # positive control: a submodule gitdir (/.git/modules/) is a decidable pointer
    folder = Path(base) / "modules-control"
    deep = folder / "src" / "deep"
    deep.mkdir(parents=True, exist_ok=True)
    (folder / ".git").write_text("gitdir: ../.git/modules/sub259\n", encoding="utf-8")
    expected = os.path.normpath(os.path.join(str(folder), "../.git/modules/sub259"))
    try:
        got = fn(str(deep))
        ok = (isinstance(got, (tuple, list)) and len(got) == 2 and af.canon(got[0]) == af.canon(folder)
              and got[1] is not None and af.canon(got[1]) == af.canon(expected))
    except Exception as exc:  # noqa: BLE001
        got, ok = "raised %r" % (exc,), False
    check(f"U-H [{label}] control: a gitdir under /.git/modules/ is returned as the pointer", ok,
          "got %r, expected (%s, %s)" % (got, folder, expected))


def run_hostile_git_file_kind(pp, base: Path) -> None:
    """The same refusal in the helper's _git_file_kind: undecidable, never a probe of the fake host; a real linked
    worktree is still a linked-worktree [control]."""
    kind = getattr(pp, "_git_file_kind", None)
    if kind is None:
        check("U-H: _project_paths._git_file_kind exists", False, "not defined")
        return
    for desc, folder, _deep in hostile_gitdir_fixtures(base):
        touched: list = []
        try:
            with watch_fake_host(touched):
                got = kind(str(folder / ".git"), str(folder))
        except Exception as exc:  # noqa: BLE001
            check(f"U-H [_git_file_kind]: {desc} -> ('undecidable', None)", False, "raised %r" % (exc,))
            continue
        if desc == NEITHER_MARKER:
            # Review round 2 (code reviewer B1): the /.git/worktrees|modules/ marker rule belongs to worktree_own_root and
            # its inline copies ONLY. For the shared classification a gitdir folder with no commondir is a main checkout,
            # exactly as in HEAD (a --separate-git-dir checkout).
            check(f"U-H [_git_file_kind]: {desc} -> keeps HEAD's classification ('main-checkout', the folder)",
                  got[0] == "main-checkout" and af.canon(got[1]) == af.canon(folder), "got %r" % (got,))
        else:
            check(f"U-H [_git_file_kind]: {desc} -> ('undecidable', None)", tuple(got) == ("undecidable", None),
                  "got %r" % (got,))
        check(f"U-H [_git_file_kind]: {desc} -> no path under the fake host is probed", not touched,
              "probed: %s" % touched)
    info = af.make_linked_worktree(Path(base) / "kind-control", layout="inside", gitdir_form="absolute")
    got = kind(str(info["worktree"] / ".git"), str(info["worktree"]))
    check("U-H [_git_file_kind] control: a real linked worktree is still a linked-worktree",
          got[0] == "linked-worktree" and af.canon(got[1]) == af.canon(info["main"]), "got %r" % (got,))


def run_own_root_units(w: World) -> None:
    pp = load_module(af.HOOKS_DIR / "_project_paths.py", "project_paths_under_test")
    guard_mod = load_module(w.guard, "codegraph_first_guard_units")
    try:
        bridge = load_module(SCRIPTS_DIR / "_claude_paths.py", "claude_paths_under_test")
        bridge_fn = getattr(bridge, "_inline_worktree_own_root", None)
    except Exception as exc:  # noqa: BLE001
        check("U: the scripts bridge _claude_paths loads", False, repr(exc))
        bridge_fn = None
    copies = [("helper", getattr(pp, "worktree_own_root", None)),
              ("guard inline copy", getattr(guard_mod, "_inline_own_root", None)),
              ("bridge inline copy", bridge_fn)]
    with af.Sandbox("cgu-") as sb:
        base = sb.root / "u"
        for label, fn in copies:
            for name, ok, detail in af.own_root_cases(fn, base):
                check("U [%s]: %s" % (label, name), ok, detail)
        check("U: worktree_own_root is exported for the bridge (listed in _project_paths.__all__ when it has one)",
              not hasattr(pp, "__all__") or "worktree_own_root" in pp.__all__,
              "__all__ does not list worktree_own_root")
        # the three copies of the walk answer the same on the same inputs (the fixtures own_root_cases just built)
        probes = [base / rel for rel in ("main-checkout/src/deeper", "main-checkout/src/not/yet/File.cs", "nogit/deep",
                                         "unreadable/deep", "nogitdirline/deep")]
        probes += sorted(base.glob("lw-*/**/src/sub"))
        for probe in probes:
            answers = {}
            for label, fn in copies:
                try:
                    got = fn(str(probe)) if fn is not None else ("missing", None)
                    answers[label] = (af.canon(got[0]), af.canon(got[1]) if got[1] is not None else None)
                except Exception as exc:  # noqa: BLE001
                    answers[label] = "raised %r" % (exc,)
            check("U parity: the helper, the guard's inline copy and the bridge's inline copy agree on %s" %
                  probe.relative_to(base).as_posix(), len({repr(v) for v in answers.values()}) == 1, repr(answers))
        # Security W3 (hostile gitdir lines): the helper, both inline copies and _git_file_kind
        for label, fn in copies:
            if fn is None:
                check(f"U-H [{label}]: the function exists", False, "not defined")
                continue
            run_hostile_own_root(label, fn, sb.root / ("h-" + label.replace(" ", "-")))
        run_hostile_git_file_kind(pp, sb.root / "h-kind")


# --------------------------------------------------------------------------------------------------------------
# V-*: review round 2 -- the shared classification keeps HEAD's answers (B1), the commondir hop (P2-W1), the 4096-byte
# first line (P2-N2). Fixtures are built by hand: no git, no network (every probe of a fake host is answered by watcher).
# --------------------------------------------------------------------------------------------------------------
def make_bare_worktree(base: Path) -> dict:
    """A worktree of a BARE repository, built by hand: <base>/repo.git/worktrees/wt/commondir = ../.. and
    <base>/wt/.git = 'gitdir: <base>/repo.git/worktrees/wt' (no /.git/ segment anywhere in the gitdir)."""
    base = Path(base)
    admin = base / "repo.git" / "worktrees" / "wt"
    admin.mkdir(parents=True, exist_ok=True)
    (admin / "commondir").write_text("../..\n", encoding="utf-8")
    (base / "repo.git" / "HEAD").write_text("ref: refs/heads/master\n", encoding="utf-8")
    worktree = base / "wt"
    (worktree / "src").mkdir(parents=True, exist_ok=True)
    (worktree / ".git").write_text("gitdir: %s\n" % admin.as_posix(), encoding="utf-8")
    return {"base": base, "bare": base / "repo.git", "admin": admin, "worktree": worktree, "deep": worktree / "src"}


def make_separate_git_dir_checkout(base: Path) -> dict:
    """A --separate-git-dir checkout built by hand: <base>/sep/.git = 'gitdir: <base>/sepgit' (no commondir there)."""
    base = Path(base)
    gitdir = base / "sepgit"
    gitdir.mkdir(parents=True, exist_ok=True)
    (gitdir / "HEAD").write_text("ref: refs/heads/master\n", encoding="utf-8")
    checkout = base / "sep"
    (checkout / "src").mkdir(parents=True, exist_ok=True)
    (checkout / ".git").write_text("gitdir: %s\n" % gitdir.as_posix(), encoding="utf-8")
    return {"checkout": checkout, "gitdir": gitdir, "deep": checkout / "src"}


def run_regression_kinds(pp, copies, base: Path) -> None:
    """Code reviewer B1: tree_kind / main_checkout_root / _git_file_kind keep HEAD's classification for the two layouts
    whose gitdir has no /.git/ segment. The marker rule stays in worktree_own_root and its inline copies [controls]."""
    bare = make_bare_worktree(base / "bare-1")
    want_main = af.canon(bare["base"])
    got = pp._git_file_kind(str(bare["worktree"] / ".git"), str(bare["worktree"]))
    check("V-B1 [_git_file_kind]: a worktree of a BARE repository reads linked-worktree, main = the bare folder's parent",
          got[0] == "linked-worktree" and af.canon(got[1]) == want_main, "got %r, expected linked-worktree / %s" % (got, bare["base"]))
    check("V-B1 [tree_kind]: a worktree of a BARE repository is a linked-worktree",
          pp.tree_kind(str(bare["deep"])) == "linked-worktree", "got %r" % (pp.tree_kind(str(bare["deep"])),))
    check("V-B1 [main_checkout_root]: and its main checkout root is the bare folder's parent",
          af.canon(pp.main_checkout_root(str(bare["deep"]))) == want_main,
          "got %r, expected %s" % (pp.main_checkout_root(str(bare["deep"])), bare["base"]))

    sep = make_separate_git_dir_checkout(base / "sep-1")
    got = pp._git_file_kind(str(sep["checkout"] / ".git"), str(sep["checkout"]))
    check("V-B1 [_git_file_kind]: a --separate-git-dir checkout reads main-checkout",
          got[0] == "main-checkout" and af.canon(got[1]) == af.canon(sep["checkout"]), "got %r" % (got,))
    check("V-B1 [tree_kind]: a --separate-git-dir checkout is a main-checkout",
          pp.tree_kind(str(sep["deep"])) == "main-checkout", "got %r" % (pp.tree_kind(str(sep["deep"])),))
    check("V-B1 [main_checkout_root]: and its main checkout root is the checkout itself",
          af.canon(pp.main_checkout_root(str(sep["deep"]))) == af.canon(sep["checkout"]),
          "got %r" % (pp.main_checkout_root(str(sep["deep"])),))

    for label, fn in copies:
        if fn is None:
            continue
        for what, layout in (("a bare-repository worktree", bare), ("a --separate-git-dir checkout", sep)):
            folder = layout.get("worktree") or layout["checkout"]
            try:
                got = fn(str(layout["deep"]))
                shaped = (af.canon(got[0]), got[1])
            except Exception as exc:  # noqa: BLE001
                got, shaped = "raised %r" % (exc,), None
            check(f"V-B1 control [worktree_own_root: {label}]: {what} stays (own folder, None) (the marker rule lives here)",
                  shaped == (af.canon(folder), None), "got %r" % (got,))


def run_commondir_hop(pp, base: Path) -> None:
    """Security P2-W1: the commondir inside a LOCAL gitdir may not send the helper to another host."""
    commondirs = [("//%s/share/.git" % FAKE_HOST, "forward-slash UNC"), ]
    if os.name == "nt":
        commondirs += [("\\\\%s\\share\\.git" % FAKE_HOST, "backslash UNC"),
                       ("\\\\?\\UNC\\%s\\share" % FAKE_HOST, "device-path UNC"),
                       ("\\\\.\\%s" % FAKE_HOST, "device-path host")]

    def fixture(name: str, text: bytes) -> tuple:
        folder = base / name
        deep = folder / "src" / "deep"
        deep.mkdir(parents=True, exist_ok=True)
        admin = folder / "evil" / ".git" / "worktrees" / "x"
        admin.mkdir(parents=True, exist_ok=True)
        (folder / ".git").write_text("gitdir: evil/.git/worktrees/x\n", encoding="utf-8")
        (admin / "commondir").write_bytes(text)
        return folder, deep, admin

    for number, (text, label) in enumerate(commondirs):
        folder, deep, _admin = fixture("cd-%d" % number, text.encode("utf-8") + b"\n")
        touched: list = []
        try:
            with watch_fake_host(touched):
                got = pp._git_file_kind(str(folder / ".git"), str(folder))
                kind = pp.tree_kind(str(deep))
                main = pp.main_checkout_root(str(deep))
        except Exception as exc:  # noqa: BLE001
            check(f"V-W1 [{label}]: a commondir naming another host is undecidable", False, "raised %r" % (exc,))
            continue
        check(f"V-W1 [{label}]: _git_file_kind -> ('undecidable', None)", tuple(got) == ("undecidable", None), "got %r" % (got,))
        check(f"V-W1 [{label}]: tree_kind -> undecidable", kind == "undecidable", "got %r" % (kind,))
        check(f"V-W1 [{label}]: main_checkout_root -> None", main is None, "got %r" % (main,))
        check(f"V-W1 [{label}]: no stat/open/realpath/isdir under the fake host is ever made", not touched,
              "probed: %s" % touched)

    # controls: a plain local commondir is still a linked worktree; an over-long one is refused
    folder, deep, admin = fixture("cd-ok", b"../..\n")
    got = pp._git_file_kind(str(folder / ".git"), str(folder))
    check("V-W1 control: a local commondir (../..) is still a linked-worktree, main = the folder holding .git",
          got[0] == "linked-worktree" and af.canon(got[1]) == af.canon(folder / "evil"), "got %r" % (got,))
    folder, deep, admin = fixture("cd-long", b"../.." + b" " * 5000 + b"\n")
    got = pp._git_file_kind(str(folder / ".git"), str(folder))
    check("V-W1: a commondir over 4096 bytes is refused (undecidable), not read whole",
          tuple(got) == ("undecidable", None), "got %r" % (got,))

    # same-host rule: a UNC target naming the SAME host as the tree's own UNC path is allowed (the helper looks at it)
    folder, _deep, admin = fixture("cd-same", ("//%s/share/.git" % FAKE_HOST).encode("utf-8") + b"\n")
    own = "//%s/share/repo" % FAKE_HOST
    # (an ABSOLUTE local gitdir: a relative one would resolve against the UNC folder and be remote itself)
    local_file = folder / "absolute.gitfile"
    local_file.write_text("gitdir: %s\n" % admin.as_posix(), encoding="utf-8")
    touched = []
    with watch_fake_host(touched):
        pp._git_file_kind(str(local_file), own)
    check("V-W1 control: a commondir on the SAME host as the tree's own UNC path is not refused (it is looked at)",
          bool(touched), "no probe of the same-host target was made: the target was refused")
    folder, _deep, admin = fixture("cd-other", ("//%s/share/.git" % FAKE_HOST).encode("utf-8") + b"\n")
    local_file = folder / "absolute.gitfile"
    local_file.write_text("gitdir: %s\n" % admin.as_posix(), encoding="utf-8")
    touched = []
    with watch_fake_host(touched):
        got = pp._git_file_kind(str(local_file), "//%s/share/repo" % OTHER_HOST)
    check("V-W1: a commondir on ANOTHER host than the tree's own UNC path is refused with no probe",
          tuple(got) == ("undecidable", None) and not touched, "got %r, probed: %s" % (got, touched))
    # the first hop honours the same-host rule too (Addendum 2, item 7: at EVERY hop)
    gitfile = base / "same-host.gitfile"
    gitfile.write_text("gitdir: //%s/share/repo/.git/worktrees/x\n" % FAKE_HOST, encoding="utf-8")
    touched = []
    with watch_fake_host(touched):
        pp._git_file_kind(str(gitfile), "//%s/share/repo" % FAKE_HOST)
    check("V-W1: a gitdir on the SAME host as the tree's own UNC path is looked at, not refused (every hop)",
          bool(touched), "no probe of the same-host gitdir was made: it was refused")


def run_commondir_callers(w: World, pp, base: Path) -> None:
    """P2-W1, caller side: the guard's _main_candidate / index_verdict and the installer's _codegraph_index_notes must not
    probe another host even when the helper (an OLDER release) hands them one."""
    import types

    def hostile_tree(name: str, index_in_parent: bool) -> tuple:
        top = base / name
        folder = top / "tree"
        deep = folder / "src" / "deep"
        deep.mkdir(parents=True, exist_ok=True)
        admin = folder / "evil" / ".git" / "worktrees" / "x"
        admin.mkdir(parents=True, exist_ok=True)
        (folder / ".git").write_text("gitdir: evil/.git/worktrees/x\n", encoding="utf-8")
        (admin / "commondir").write_text("//%s/share/.git\n" % FAKE_HOST, encoding="utf-8")
        if index_in_parent:
            af.plant_index(top)
        return folder, deep

    remote = "//%s/share" % FAKE_HOST
    old_tree_kind = lambda path: "linked-worktree"  # noqa: E731 - what a release without the refusal answers
    old_main_root = lambda path: remote  # noqa: E731

    def is_remote(value) -> bool:
        return isinstance(value, str) and (value.replace("\\", "/").startswith("//") or FAKE_HOST in value.lower())

    for with_index in (False, True):
        tag = "with an index above the tree" if with_index else "no index"
        folder, deep = hostile_tree("cg-idx" if with_index else "cg-noidx", with_index)
        for helper in ("current helper", "older helper"):
            guard_mod = load_module(w.guard, "cg_hops_%s_%s" % (with_index, helper.split()[0]))
            if helper == "older helper":
                guard_mod._pp_tree_kind = old_tree_kind
                guard_mod._pp_main_checkout_root = old_main_root
            touched: list = []
            try:
                with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": ""}), watch_fake_host(touched):
                    candidate = guard_mod._main_candidate(str(deep))
                    verdict = guard_mod.index_verdict(str(deep))
            except Exception as exc:  # noqa: BLE001
                check(f"V-W1 guard [{helper}, {tag}]: runs", False, "raised %r" % (exc,))
                continue
            check(f"V-W1 guard [{helper}, {tag}]: _main_candidate never returns a remote path",
                  not is_remote(candidate), "returned %r" % (candidate,))
            check(f"V-W1 guard [{helper}, {tag}]: index_verdict probes nothing under the fake host", not touched,
                  "probed: %s (verdict %s)" % (touched, verdict))

    try:
        fi = load_installer()
    except Exception as exc:  # noqa: BLE001
        check("V-W1 installer: the installer can be loaded", False, repr(exc))
        return
    for with_index in (False, True):
        tag = "with an index above the tree" if with_index else "no index"
        folder, deep = hostile_tree("fi-idx" if with_index else "fi-noidx", with_index)
        older = types.SimpleNamespace(TREE_HOP_REFUSAL=True, worktree_own_root=pp.worktree_own_root,
                                      tree_kind=old_tree_kind, main_checkout_root=old_main_root)
        for helper, patch in (("current helper", None), ("older helper", lambda: older)):
            touched = []
            try:
                with watch_fake_host(touched):
                    if patch is None:
                        notes = fi._codegraph_index_notes(folder)
                    else:
                        with mock.patch.object(fi, "_launcher_api", patch):
                            notes = fi._codegraph_index_notes(folder)
            except Exception as exc:  # noqa: BLE001
                check(f"V-W1 installer [{helper}, {tag}]: runs", False, "raised %r" % (exc,))
                continue
            check(f"V-W1 installer [{helper}, {tag}]: _codegraph_index_notes probes nothing under the fake host",
                  not touched, "probed: %s (notes %r)" % (touched, notes))


def run_first_line_cap(pp, copies, base: Path) -> None:
    """Security P2-N2: a .git first line of exactly 4096 bytes with no newline was cut off by the read cap: undecidable."""

    def fixture(name: str, tail: bytes) -> tuple:
        folder = base / name
        deep = folder / "src"
        deep.mkdir(parents=True, exist_ok=True)
        prefix = ("gitdir: %s/" % (folder / "evil" / ".git" / "worktrees").as_posix()).encode("utf-8")
        return folder, deep, prefix

    folder, deep, prefix = fixture("cap-exact", b"")
    pad = 4096 - len(prefix)
    (folder / ".git").write_bytes(prefix + b"w" * pad)
    check("V-N2 fixture: the first line is exactly 4096 bytes with no newline", (folder / ".git").stat().st_size == 4096,
          "size %s" % (folder / ".git").stat().st_size)
    for label, fn in copies:
        if fn is None:
            continue
        try:
            got = fn(str(deep))
            shaped = (af.canon(got[0]), got[1])
        except Exception as exc:  # noqa: BLE001
            got, shaped = "raised %r" % (exc,), None
        check(f"V-N2 [{label}]: a first line of exactly 4096 bytes with no newline is undecidable (F, None)",
              shaped == (af.canon(folder), None), "got %r" % (got,))
    got = pp._git_file_kind(str(folder / ".git"), str(folder))
    check("V-N2 [_git_file_kind]: the same file is ('undecidable', None)", tuple(got) == ("undecidable", None), "got %r" % (got,))

    folder, deep, prefix = fixture("cap-fits", b"")
    (folder / ".git").write_bytes(prefix + b"w" * (4096 - len(prefix) - 1) + b"\n")
    pointer = os.path.normpath(prefix.decode("utf-8")[len("gitdir: "):] + "w" * (4096 - len(prefix) - 1))
    expected = (af.canon(folder), pointer.replace("\\", "/").lower())
    for label, fn in copies:
        if fn is None:
            continue
        try:
            got = fn(str(deep))
            shaped = (af.canon(got[0]), got[1].replace("\\", "/").lower() if got[1] is not None else None)
        except Exception as exc:  # noqa: BLE001
            got, shaped = "raised %r" % (exc,), None
        check(f"V-N2 control [{label}]: 4095 bytes plus a newline (inside the cap) is still a decidable pointer",
              shaped == expected, "got %r, expected %r" % (got, expected))


def run_review_round_two(w: World) -> None:
    pp = load_module(af.HOOKS_DIR / "_project_paths.py", "project_paths_round_two")
    guard_mod = load_module(w.guard, "codegraph_first_guard_round_two")
    try:
        bridge = load_module(SCRIPTS_DIR / "_claude_paths.py", "claude_paths_round_two")
        bridge_fn = getattr(bridge, "_inline_worktree_own_root", None)
    except Exception as exc:  # noqa: BLE001
        check("V: the scripts bridge _claude_paths loads", False, repr(exc))
        bridge_fn = None
    copies = [("helper", getattr(pp, "worktree_own_root", None)),
              ("guard inline copy", getattr(guard_mod, "_inline_own_root", None)),
              ("bridge inline copy", bridge_fn)]
    with af.Sandbox("cgv-") as sb:
        base = sb.root / "v"
        base.mkdir()
        run_regression_kinds(pp, copies, base / "b1")
        run_commondir_hop(pp, base / "w1")
        run_commondir_callers(w, pp, base / "w1c")
        run_first_line_cap(pp, copies, base / "n2")


# --------------------------------------------------------------------------------------------------------------
# X-*: the temp folder pruner, through the before_remove seam
# --------------------------------------------------------------------------------------------------------------
def load_reset_module(sb: af.Sandbox, w: World):
    """The guard, loaded in-process: since the cut-over (issue #262, C-5) the pruner, the Connection probe and the notice live in
    the guard's own file. The function keeps its old name so the rows that exercise them read as before."""
    spec = importlib.util.spec_from_file_location("codegraph_guard_pruner_under_test", w.guard)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


KNOWN = ("turn.json", "availability.json", "pruned", "logged-no-index", "ticket-" + "a" * 64)


def old_session(tmp: Path, name: str, files=KNOWN, age_days: float = 10) -> Path:
    folder = tmp / (af.CODEGRAPH_SESSION_PREFIX + name)
    folder.mkdir()
    stamp = time.time() - age_days * 86400
    for f in files:
        (folder / f).write_text("{}\n", encoding="utf-8")
        os.utime(str(folder / f), (stamp, stamp))
    os.utime(str(folder), (stamp, stamp))
    return folder


def run_pruner(w: World) -> None:
    with af.Sandbox("cgx-") as sb:
        with mock.patch.dict(os.environ, af.isolated_env(sb.home, sb.tmp), clear=True):
            saved = tempfile.tempdir
            tempfile.tempdir = str(sb.tmp)
            try:
                mod = load_reset_module(sb, w)
                prune = getattr(mod, "prune_session_folders", None)  # the contract's named seam: no reflection
                if prune is None:
                    check("X-0: the guard defines prune_session_folders(root, before_remove=...)", False,
                          "codegraph-first-guard.py has no prune_session_folders")
                    return
                run_pruner_cases(sb, prune)
            finally:
                tempfile.tempdir = saved


def run_pruner_cases(sb: af.Sandbox, prune) -> None:
    tmp = sb.tmp

    def attempt(label: str, fn_cb, setup) -> object:
        """Run the pruner once; a call that cannot be made is a diagnostic FAIL, never a crash."""
        try:
            prune(str(tmp), before_remove=fn_cb)
            return True
        except Exception as exc:  # noqa: BLE001
            check(label, False, "calling the prune function raised %r" % (exc,))
            return None

    # X-1 an old folder of known plain files is deleted, file by file, through the seam
    folder = old_session(tmp, "old")
    seen: list[str] = []
    if attempt("X-1", lambda p: seen.append(str(p)), None):
        check("X-1: an old folder holding only known plain files is deleted", not folder.exists(), "folder still exists")
        check("X-1: the seam saw each file before its removal", len(seen) >= len(KNOWN), "seen: %s" % seen)

    # X-2 a known file replaced by a FOLDER of the same name: kept. DEFENCE IN DEPTH ONLY: the OS refuses os.remove of a
    # folder, so this row stays green even without the pruner's per-file re-check; X-2b and X-4 are the rows that bite.
    folder = old_session(tmp, "swap-folder")
    done: list[int] = []

    def swap_with_folder(p):
        if not done:
            done.append(1)
            os.remove(str(p))
            os.mkdir(str(p))
    if attempt("X-2", swap_with_folder, None):
        check("X-2 (defence in depth: the OS refuses the remove too): a known file swapped for a same-named FOLDER keeps "
              "the session folder", folder.is_dir(), "session folder was removed")
        check("X-2 (defence in depth): and the planted folder is untouched", any(c.is_dir() for c in folder.iterdir()),
              "no folder inside")
    for child in list(folder.iterdir()) if folder.exists() else []:
        if child.is_dir():
            child.rmdir()
    shutil.rmtree(folder, ignore_errors=True)

    # X-3 a known file renamed to an unknown name: kept (defence in depth too: os.remove of the vanished name raises)
    folder = old_session(tmp, "rename")
    done = []

    def rename_it(p):
        if not done:
            done.append(1)
            os.rename(str(p), str(p) + ".foreign")
    if attempt("X-3", rename_it, None):
        check("X-3 (defence in depth): a known file renamed to an UNKNOWN name keeps the session folder", folder.is_dir()
              and any(c.name.endswith(".foreign") for c in folder.iterdir()), "folder gone or renamed file gone")
    shutil.rmtree(folder, ignore_errors=True)

    # X-2b a known file swapped for a FOLDER LINK (a junction on Windows: no privilege needed; a symlink on POSIX): the
    # per-file re-check must keep the session folder. os.remove DOES remove a folder link, so without the re-check the
    # link would go, the rest of the files would follow and the session folder would be deleted: this row bites on a
    # machine that cannot create file symlinks (X-6 skips there).
    folder = old_session(tmp, "swap-junction-file")
    link_target = sb.root / "x2b-target"
    link_target.mkdir()
    (link_target / "keep.txt").write_text("keep me\n", encoding="utf-8")
    done = []

    def swap_with_folder_link(p):
        if not done:
            done.append(1)
            os.remove(str(p))
            if not af.make_dir_link(Path(p), link_target):
                done.append("link refused")
    if attempt("X-2b", swap_with_folder_link, None):
        if "link refused" in done:
            skip("X-2b: a known file swapped for a folder link", "the OS refused to create a folder link")
        else:
            planted = [c for c in folder.iterdir() if af.is_link(c)] if folder.is_dir() else []
            check("X-2b: a known file swapped for a FOLDER LINK keeps the session folder (the per-file re-check)",
                  folder.is_dir() and len(planted) == 1, "session folder exists=%s, links inside=%s"
                  % (folder.is_dir(), [c.name for c in planted]))
            check("X-2b: and the link's target is untouched", (link_target / "keep.txt").read_text(encoding="utf-8")
                  == "keep me\n", "target changed")
    for child in list(folder.iterdir()) if folder.exists() else []:
        if af.is_link(child):
            try:
                os.rmdir(str(child))
            except OSError:
                try:
                    os.remove(str(child))
                except OSError:
                    pass
    shutil.rmtree(folder, ignore_errors=True)

    # X-4 the session folder swapped for a folder link after the folder test: kept, and EVERY known name in the link's
    # target survives (the target holds all of KNOWN, so a pruner without the per-file re-check would delete them)
    folder = old_session(tmp, "swap-link")
    target = sb.root / "x4-target"
    target.mkdir()
    for f in KNOWN + ("precious.txt",):
        (target / f).write_text("keep me\n", encoding="utf-8")
    swapped: list[str] = []

    def swap_with_link(p):
        if swapped:
            return
        parent = Path(p).parent
        moved = parent.with_name(parent.name + "-moved")
        try:
            os.rename(str(parent), str(moved))
        except OSError as exc:
            swapped.append("rename failed: %s" % exc)
            return
        if not af.make_dir_link(parent, target):
            os.rename(str(moved), str(parent))
            swapped.append("link failed")
            return
        swapped.append("ok")
    if attempt("X-4", swap_with_link, None):
        if swapped and swapped[0] == "ok":
            check("X-4: a session folder swapped for a folder link after the folder test: every known name in the link's "
                  "target survives, untouched",
                  all((target / f).is_file() and (target / f).read_text(encoding="utf-8") == "keep me\n"
                      for f in KNOWN + ("precious.txt",)),
                  "target holds: %s" % sorted(c.name for c in target.iterdir()))
            check("X-4: and the link itself is kept (never removed as if it were the session folder)",
                  af.is_link(folder) or folder.exists(), "link removed")
        else:
            skip("X-4: the session folder swapped for a folder link", "could not perform the swap: %r" % (swapped,))
    for stray in (folder, folder.with_name(folder.name + "-moved")):
        if af.is_link(stray):
            try:
                os.rmdir(str(stray))
            except OSError:
                pass
        else:
            shutil.rmtree(stray, ignore_errors=True)

    # X-5 a folder link at the folder-test stage: kept, the target untouched
    target = sb.root / "x5-target"
    target.mkdir()
    stamp = time.time() - 10 * 86400
    for f in KNOWN:
        (target / f).write_text("keep me\n", encoding="utf-8")
        os.utime(str(target / f), (stamp, stamp))
    link = tmp / (af.CODEGRAPH_SESSION_PREFIX + "linked")
    if af.make_dir_link(link, target):
        if attempt("X-5", lambda p: None, None):
            check("X-5: an auto-improve-codegraph-* entry that is a folder link is skipped: its target is untouched",
                  all((target / f).exists() for f in KNOWN), "target holds: %s" % sorted(c.name for c in target.iterdir()))
            check("X-5: and the link is kept", af.is_link(link), "link was removed")
        try:
            os.rmdir(str(link))
        except OSError:
            pass
    else:
        skip("X-5: a folder link in the temp folder", "the OS refused to create a folder link")

    # X-6 a file symlink in place of a known file (only when the OS lets us create one)
    probe_target = sb.root / "x6-probe-target"
    probe_target.write_text("x\n", encoding="utf-8")
    probe_link = sb.root / "x6-probe-link"
    try:
        os.symlink(str(probe_target), str(probe_link))
        can_symlink = True
        os.remove(str(probe_link))
    except (OSError, NotImplementedError):
        can_symlink = False
    if can_symlink:
        folder = old_session(tmp, "file-symlink")
        outside = sb.root / "x6-outside.txt"
        outside.write_text("keep me\n", encoding="utf-8")
        done = []

        def swap_with_symlink(p):
            if not done:
                done.append(1)
                os.remove(str(p))
                os.symlink(str(outside), str(p))
        if attempt("X-6", swap_with_symlink, None):
            check("X-6: a known file swapped for a FILE SYMLINK keeps the session folder and the symlink's target",
                  folder.is_dir() and outside.exists() and outside.read_text(encoding="utf-8") == "keep me\n",
                  "folder exists=%s target exists=%s" % (folder.is_dir(), outside.exists()))
        shutil.rmtree(folder, ignore_errors=True)
    else:
        skip("X-6: a file symlink swapped in", FILE_SYMLINK_REFUSED)
        print("        " + FILE_SYMLINK_REFUSED)

    # X-7 a foreign file, a young folder, an unrelated folder: kept
    foreign = old_session(tmp, "foreign", files=KNOWN + ("notes.txt",))
    young = old_session(tmp, "young", age_days=1)
    unrelated = tmp / "some-other-tool-folder"
    unrelated.mkdir()
    (unrelated / "turn.json").write_text("{}\n", encoding="utf-8")
    old = time.time() - 30 * 86400
    os.utime(str(unrelated / "turn.json"), (old, old))
    os.utime(str(unrelated), (old, old))
    if attempt("X-7", lambda p: None, None):
        check("X-7: an old folder holding a FOREIGN file is kept whole", foreign.is_dir()
              and (foreign / "notes.txt").exists(), "foreign folder gone")
        check("X-7: a folder younger than 7 days is kept", young.is_dir() and (young / "turn.json").exists(),
              "young folder gone")
        check("X-7: a folder that does not start with auto-improve-codegraph- is never touched (no removal by pattern)",
              (unrelated / "turn.json").exists(), "unrelated folder was touched")
    shutil.rmtree(foreign, ignore_errors=True)
    shutil.rmtree(young, ignore_errors=True)

    # X-9 (review round 2, P2-N3 / N1): the guard and the tracker create `.tmp-<16 hex>` siblings before os.replace; one left
    # behind by a killed hook is a KNOWN name, so it does not keep an old session folder alive forever.
    leftover = old_session(tmp, "tmp-leftover", files=KNOWN + (".tmp-0123456789abcdef",))
    unknown_tmp = old_session(tmp, "tmp-lookalike", files=KNOWN + (".tmp-0123456789abcdeg",))
    short_tmp = old_session(tmp, "tmp-short", files=KNOWN + (".tmp-0123456789abcde",))
    foreign_again = old_session(tmp, "tmp-and-foreign", files=KNOWN + (".tmp-0123456789abcdef", "notes.txt"))
    if attempt("X-9", lambda p: None, None):
        check("X-9: an old folder holding only known files plus a `.tmp-<16 hex>` sibling is deleted",
              not leftover.exists(), "session folder still exists: %s" % sorted(c.name for c in leftover.iterdir())
              if leftover.exists() else "")
        check("X-9 control: a `.tmp-` name whose suffix is not 16 hex digits is UNKNOWN and keeps the folder",
              unknown_tmp.is_dir(), "folder was removed")
        check("X-9 control: a `.tmp-` name with only 15 hex digits is UNKNOWN and keeps the folder",
              short_tmp.is_dir(), "folder was removed")
        check("X-9 control: a `.tmp-<16 hex>` sibling does not excuse an unknown file: the folder is kept",
              foreign_again.is_dir() and (foreign_again / "notes.txt").exists(), "folder was removed")
    for stray in (leftover, unknown_tmp, short_tmp, foreign_again):
        shutil.rmtree(stray, ignore_errors=True)


def run_prune_once(w: World) -> None:
    """The guard's prompt row prunes the Per-user session parent (never the temp folder) once per session (Prune flag), as a hook
    process, on the first prompt only."""
    with af.Sandbox("cgy-") as sb:
        project = project_of(sb, "prune")
        session = sid()
        first_old = old_session(af.session_parent(sb.home), "first-old")
        done = run_hook(w.guard, sb, project, "", {}, session, event="UserPromptSubmit", payload_extra={"prompt": "one"}, argv=["notice"])
        check("X-8: the first prompt of a session exits 0", done.returncode == 0, describe(done))
        check("X-8: the first prompt prunes an old, known-file session folder of another session",
              not first_old.exists(), "old folder still exists")
        check("X-8: and leaves a `pruned` flag in this session's folder",
              (pfolder(sb, session) / "pruned").exists(), "no pruned flag")
        second_old = old_session(af.session_parent(sb.home), "second-old")
        run_hook(w.guard, sb, project, "", {}, session, event="UserPromptSubmit", payload_extra={"prompt": "two"}, argv=["notice"])
        check("X-8: the second prompt of the SAME session does not prune again", second_old.is_dir(),
              "pruned a second time")
        third = sid()
        run_hook(w.guard, sb, project, "", {}, third, event="UserPromptSubmit", payload_extra={"prompt": "three"}, argv=["notice"])
        check("X-8: another session prunes on its own first prompt", not second_old.exists(),
              "second old folder still exists")


# --------------------------------------------------------------------------------------------------------------
# S-*: state hygiene (review round: cache per cwd, once-per-session flag order, session key collisions)
# --------------------------------------------------------------------------------------------------------------
def run_state(w: World) -> None:
    with af.Sandbox("cgs-") as sb:
        # S-1 the index verdict is cached per DISTINCT cwd, not once per session: the same session moving from a tree
        # with no index into a tree with one is gated again
        noidx = project_of(sb, "s1-noidx", index=False)
        withidx = project_of(sb, "s1-idx")
        if clean_above("S-1", noidx):
            session = sid()
            first = run_hook(w.guard, sb, noidx, "Read", read_cs(noidx), session)
            check("S-1: a session in a tree with no index is let through (fail-open:no-index)",
                  allowed(first, "fail-open:no-index"), describe(first))
            second = run_hook(w.guard, sb, withidx, "Read", read_cs(withidx), session)
            check("S-1: the SAME session, now with cwd in a tree that has an index, is BLOCKED (the verdict is cached "
                  "per cwd, not per session)", blocked(second), describe(second))

        # S-2 the once-per-session `logged-<reason>` flag is created AFTER the record is written: a call whose log
        # write could not happen must not suppress the record of the next call
        project = project_of(sb, "s2", index=False)
        session = sid()
        run_hook(w.guard, sb, project, "Read", read_cs(project), session)  # no .claude/logs folder: nothing can be logged
        make_logs(project)
        run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        got = events(project, "fail-open")
        check("S-2: a fail-open whose record could not be written does not use up the session's one record for that "
              "reason: the next call logs it", len(got) == 1, "records: %r" % got)

        # S-3 a session id ending in '.' (Windows strips the dot) never shares a folder with the id without it
        base_id = sid()
        project = project_of(sb, "s3")
        opened = fresh_transcript(sb, [af.t_human(1), af.t_mcp_use()])
        run_hook(w.guard, sb, project, "Read", read_cs(project), base_id + ".", transcript=opened)
        other = run_hook(w.guard, sb, project, "Read", read_cs(project), base_id)
        check("S-3: the state of session 'X.' (its cursor included) does not reach the gate of session 'X' (no folder shared once "
              "Windows strips the dot)", blocked(other), describe(other))
        own = run_hook(w.guard, sb, project, "Read", read_cs(project), base_id + "k", transcript=opened)
        check("S-3 [control]: a plain session id keeps working: its own open transcript opens its own gate", silent_allow(own),
              describe(own))


# --------------------------------------------------------------------------------------------------------------
# L-*: no state write goes THROUGH a link at the file name (security W1)
# --------------------------------------------------------------------------------------------------------------
def run_link_writes(w: World) -> None:
    with af.Sandbox("cgl-") as sb:
        guard_mod = load_module(w.guard, "codegraph_first_guard_links")
        project = project_of(sb, "lnk")
        decoy_text = "DECOY: a file the hooks must never rewrite\n"
        kinds = [("hard link", "hard")]
        if af.can_make_file_symlink(sb.root):
            kinds.append(("symlink", "symlink"))
        else:
            skip("L-*: state files that are symlinks", FILE_SYMLINK_REFUSED)
            print("        " + FILE_SYMLINK_REFUSED)
        # controls: without a link the hooks write their files (so the rows below can only fail for the link)
        session = sid()
        done = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        folder = pfolder(sb, session)
        check("L control: the guard writes availability.json and a ticket-<64 hex> into the Session folder",
              blocked(done) and (folder / "availability.json").is_file() and len(list(folder.glob("ticket-*"))) == 1,
              describe(done) + " / " + str(sorted(p.name for p in folder.glob("*"))))
        check("L control: the guard writes the Transcript cursor", (folder / "transcript-cursor.json").is_file(),
              str(sorted(p.name for p in folder.glob("*"))))
        for kind_label, kind in kinds:
            for state_name in ("availability.json", "ticket", "transcript-cursor.json"):
                session = sid()
                folder = pfolder(sb, session, True)
                folder.mkdir()
                decoy = sb.root / ("decoy-%s-%s.txt" % (kind, state_name))
                decoy.write_text(decoy_text, encoding="utf-8")
                name = ("ticket-" + guard_mod.call_fingerprint("Read", read_cs(project))
                        if state_name == "ticket" else state_name)
                label = "L [%s at %s]" % (kind_label, state_name)
                if not af.make_file_link(folder / name, decoy, kind):
                    skip(label, "the OS refused to create the %s" % kind_label)
                    continue
                proc = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
                after = decoy.read_text(encoding="utf-8", errors="replace")
                check(f"{label}: the hook does not write through the link: the decoy file is unchanged",
                      after == decoy_text, "decoy now holds %r; %s" % (after[:120], describe(proc)))
                try:
                    os.remove(str(folder / name))
                except OSError:
                    pass


# --------------------------------------------------------------------------------------------------------------
#
# W-*: review round 3 (Addendum 3, items 11-14). Every host here is a fake name under .invalid, answered by
# watch_fake_host / af.unc_share: no row touches a network.
# --------------------------------------------------------------------------------------------------------------
OWN_HOST = "own-259.invalid"
MAP_HOST = "mapped-259.invalid"
UNC_OWN = "\\\\%s\\team\\repo" % OWN_HOST
FOREIGN = (FAKE_HOST, OTHER_HOST)


def plain(value) -> str | None:
    """A comparable spelling of a path: backslashes, lower case, no device prefix, no trailing separator."""
    if value is None:
        return None
    text = str(value).replace("/", "\\")
    if text.lower().startswith("\\\\?\\unc\\"):
        text = "\\\\" + text[8:]
    elif text.startswith("\\\\?\\") or text.startswith("\\\\.\\"):
        text = text[4:]
    return text.lower().rstrip("\\")


# (target, own, allowed?, why). Rows whose answer depends on a decision the contract leaves open are not listed here;
# the parity table below pins them across the four copies instead.
HOP_TABLE = [
    ("C:\\x\\y", UNC_OWN, True, "a local path is never a remote hop"),
    ("/home/u/x", "C:\\repo", True, "a posix-style local path"),
    ("//%s/team/x" % OWN_HOST, UNC_OWN, True, "a same-host UNC path without '..' stays allowed"),
    ("\\\\%s\\team\\x" % OWN_HOST.upper(), UNC_OWN, True, "the host compares without case"),
    ("\\\\?\\UNC\\%s\\team\\x" % OWN_HOST, UNC_OWN, True, "a same-host \\\\?\\UNC\\ path without '..' stays allowed"),
    ("//%s/s/x" % OTHER_HOST, UNC_OWN, False, "another host is refused"),
    ("\\\\?\\UNC\\%s\\s\\x" % OTHER_HOST, UNC_OWN, False, "another host in the \\\\?\\UNC\\ form is refused"),
    ("//%s/team/x" % OWN_HOST, "C:\\repo", False, "a UNC hop from a local tree is refused"),
    ("//%s/team/../x" % OWN_HOST, UNC_OWN, False, "a '..' inside a same-host UNC path is refused"),
    ("\\\\%s\\team\\a\\..\\b" % OWN_HOST, UNC_OWN, False, "a '..' inside a backslash UNC path is refused"),
    ("//?/UNC/%s/../%s/s/.git" % (OWN_HOST, FAKE_HOST), UNC_OWN, False, "the host switch by '..' (forward slashes)"),
    ("\\\\?\\UNC\\%s\\share\\..\\..\\%s" % (OWN_HOST, FAKE_HOST), UNC_OWN, False, "the share climb by '..'"),
    ("\\\\?\\UNC\\%s\\..\\%s\\s" % (OWN_HOST, FAKE_HOST), UNC_OWN, False, "the host climb by '..'"),
]

PARITY_TARGETS = [
    "C:\\x\\y", "C:/x/../y", "/home/u/x", "relative/dir", "../up", "",
    "//own-259.invalid/team/x", "\\\\own-259.invalid\\team\\x", "\\\\OWN-259.INVALID\\team\\x", "//other-host-259.invalid/s/x",
    "\\\\?\\UNC\\own-259.invalid\\team\\x", "\\\\?\\unc\\own-259.invalid\\team\\x", "//?/UNC/other-host-259.invalid/s",
    "\\\\.\\own-259.invalid", "\\\\.\\UNC\\own-259.invalid\\team\\x", "\\\\?\\C:\\x", "\\\\.\\C:\\x", "///own-259.invalid/team",
    "//own-259.invalid/team/../x", "//own-259.invalid/../other-host-259.invalid/s", "//?/UNC/own-259.invalid/../fake-host-259.invalid/s",
    "\\\\?\\UNC\\own-259.invalid\\team\\..\\..\\fake-host-259.invalid\\s", "\\\\?\\C:\\a\\..\\b", "C:\\a\\..\\b",
    "//", "\\\\", "//?", "//?/UNC",
]
PARITY_OWNS = [UNC_OWN, "//OWN-259.invalid/team/repo", "\\\\other-host-259.invalid\\s", "C:\\repo", "\\\\?\\C:\\repo",
               "\\\\?\\UNC\\own-259.invalid\\team\\repo", "\\\\.\\own-259.invalid", "/home/u/repo", ""]


def run_hop_rows(mods, six=None) -> None:
    """Item 11 (normalise, then check) and item 14 (the four copies of _hop_allowed agree; since issue #271 the copies of
    _remote_host and of _own_spellings agree: ``six`` = the four plus the codegraph tracker and reset hook. Since issue #262 the
    two disabled hooks are no longer active copies, so the caller passes the four only)."""
    six = six or mods
    for label, mod in mods:
        fn = getattr(mod, "_hop_allowed", None)
        if fn is None:
            check(f"W-11 [{label}]: _hop_allowed exists", False, "not defined")
            continue
        for target, own, want, why in HOP_TABLE:
            try:
                got = fn(target, own)
            except Exception as exc:  # noqa: BLE001
                got = "raised %r" % (exc,)
            check(f"W-11 [{label}] _hop_allowed({target!r}, own {own!r}) is {want}: {why}", got is want, "got %r" % (got,))

    # item 14: one list of inputs through the copies (_remote_host: six since issue #271, four since the cut-over of issue #262)
    for target in PARITY_TARGETS:
        answers = {}
        for label, mod in six:
            try:
                answers[label] = mod._remote_host(target)
            except Exception as exc:  # noqa: BLE001
                answers[label] = "raised %r" % (exc,)
        check(f"W-14 parity: the four copies of _remote_host (helper, guard, bridge, installer) agree on {target!r}",
              len(answers) == 4 and len({repr(v) for v in answers.values()}) == 1, repr(answers))
    for own in PARITY_OWNS:
        differing = []
        for target in PARITY_TARGETS:
            answers = {}
            for label, mod in mods:
                try:
                    answers[label] = mod._hop_allowed(target, own)
                except Exception as exc:  # noqa: BLE001
                    answers[label] = "raised %r" % (exc,)
            if len({repr(v) for v in answers.values()}) != 1:
                differing.append((target, answers))
        check(f"W-14 parity: the four copies of _hop_allowed agree for the own path {own!r} on {len(PARITY_TARGETS)} targets",
              not differing, "differ on: %r" % (differing[:3],))

    # N1: the `*also` (realpath) argument of _hop_allowed, and _own_spellings, through the four copies
    also_cases = [
        ("C:\\mapped\\repo", "\\\\own-259.invalid\\team\\repo"),
        ("C:\\mapped\\repo", "\\\\other-host-259.invalid\\s\\repo"),
        ("C:\\repo", "C:\\repo"),
        ("\\\\?\\C:\\repo", "//OWN-259.invalid/team/repo"),
        ("/home/u/repo", "\\\\?\\UNC\\own-259.invalid\\team\\repo"),
    ]
    for own, also in also_cases:
        differing = []
        for target in PARITY_TARGETS:
            answers = {}
            for label, mod in mods:
                try:
                    answers[label] = mod._hop_allowed(target, own, also)
                except Exception as exc:  # noqa: BLE001
                    answers[label] = "raised %r" % (exc,)
            if len({repr(v) for v in answers.values()}) != 1:
                differing.append((target, answers))
        check(f"W-14 parity: the four copies of _hop_allowed agree for own {own!r} with also {also!r} on {len(PARITY_TARGETS)} targets",
              not differing, "differ on: %r" % (differing[:3],))
    mapped_ok = all(mod._hop_allowed("//own-259.invalid/team/x", "C:\\mapped\\repo", "\\\\own-259.invalid\\team\\repo") is True
                    for _, mod in mods)
    check("W-14 parity: a `also` spelling on the target's host allows a same-host hop from a local own path (all four copies)",
          mapped_ok, "a copy refused it")
    spelling_inputs = PARITY_OWNS + ["C:\\mapped\\repo", "\\\\.\\C:\\repo", "relative\\dir", "//", "\\\\?\\UNC"]
    differing = []
    for path in spelling_inputs:
        answers = {}
        for label, mod in six:
            try:
                answers[label] = repr(tuple(mod._own_spellings(path)))
            except Exception as exc:  # noqa: BLE001
                answers[label] = "raised %r" % (exc,)
        if len(set(answers.values())) != 1 or len(answers) != 4:
            differing.append((path, answers))
    check(f"W-14 parity: the four copies of _own_spellings (helper, guard, bridge, installer) agree on "
          f"{len(spelling_inputs)} inputs", not differing, "differ on: %r" % (differing[:3],))


def unc_tree(share_root: Path, name: str, gitfile_text: str, commondir: str | None,
             admin_rel: str = "evil/.git/worktrees/x") -> Path:
    """A tree on the simulated share: <share_root>/<name>/.git (a FILE) and, when given, the admin folder with its
    commondir. ``\\\\own-259.invalid\\team\\<name>`` is its UNC spelling."""
    folder = Path(share_root) / name
    (folder / "src").mkdir(parents=True, exist_ok=True)
    (folder / ".git").write_text(gitfile_text, encoding="utf-8")
    if commondir is not None:
        admin = folder / Path(admin_rel)
        admin.mkdir(parents=True, exist_ok=True)
        (admin / "commondir").write_text(commondir + "\n", encoding="utf-8")
    return folder


def unc_of(name: str) -> str:
    return "\\\\%s\\team\\%s" % (OWN_HOST, name)


def run_unc_tree_rows(pp, copies, base: Path) -> None:
    """Item 11 on a tree that lives on a literal UNC path: the commondir and gitdir values are judged after
    normalisation, and nothing under the other host is ever probed."""
    share = base / "share"
    share.mkdir(parents=True)
    climb = "../" * 7 + "%s/s/.git" % FAKE_HOST
    commondirs = [
        ("host switch by '..' (forward slashes)", "gitdir: evil/.git/worktrees/x", "//?/UNC/%s/../%s/s/.git" % (OWN_HOST, FAKE_HOST)),
        ("share climb by '..'", "gitdir: evil/.git/worktrees/x", "\\\\?\\UNC\\%s\\share\\..\\..\\%s" % (OWN_HOST, FAKE_HOST)),
        ("host climb by '..'", "gitdir: evil/.git/worktrees/x", "\\\\?\\UNC\\%s\\..\\%s\\s" % (OWN_HOST, FAKE_HOST)),
        ("a relative climb behind a same-host device-form gitdir", None, climb),
    ]
    with af.unc_share(share, OWN_HOST, others=FOREIGN):
        for number, (label, gitline, value) in enumerate(commondirs):
            name = "cd%d" % number
            gitline = gitline or "gitdir: //?/UNC/%s/team/%s/evil/.git/worktrees/x" % (OWN_HOST, name)
            unc_tree(share, name, gitline + "\n", value)
            touched: list = []
            try:
                with watch_fake_host(touched):
                    got = pp._git_file_kind(unc_of(name) + "\\.git", unc_of(name))
            except Exception as exc:  # noqa: BLE001
                check(f"W-11 [_git_file_kind, UNC tree]: {label} -> undecidable", False, "raised %r" % (exc,))
                continue
            check(f"W-11 [_git_file_kind, UNC tree]: a commondir with a {label} is ('undecidable', None)",
                  tuple(got) == ("undecidable", None), "got %r" % (got,))
            check(f"W-11 [_git_file_kind, UNC tree]: a commondir with a {label}: nothing under the other host is probed",
                  not touched, "probed: %s" % touched)

        # controls: the ordinary relative commondir and a same-host absolute one (no '..') stay a linked worktree
        unc_tree(share, "ok-rel", "gitdir: evil/.git/worktrees/x\n", "../..")
        got = pp._git_file_kind(unc_of("ok-rel") + "\\.git", unc_of("ok-rel"))
        check("W-11 control [_git_file_kind, UNC tree]: the ordinary commondir '../..' is still a linked-worktree",
              got[0] == "linked-worktree" and plain(got[1]) == plain(unc_of("ok-rel") + "\\evil"), "got %r" % (got,))
        unc_tree(share, "ok-abs", "gitdir: evil/.git/worktrees/x\n", "//%s/team/ok-abs/evil/.git" % OWN_HOST)
        got = pp._git_file_kind(unc_of("ok-abs") + "\\.git", unc_of("ok-abs"))
        check("W-11 control [_git_file_kind, UNC tree]: a same-host absolute commondir without '..' is still a "
              "linked-worktree", got[0] == "linked-worktree" and plain(got[1]) == plain(unc_of("ok-abs") + "\\evil"),
              "got %r" % (got,))

        # the gitdir hop, in the helper's _git_file_kind and in the three walks
        gitdirs = [
            ("host switch by '..'", "gitdir: //?/UNC/%s/../%s/s/.git/worktrees/x" % (OWN_HOST, FAKE_HOST)),
            ("share climb by '..'",
             "gitdir: \\\\?\\UNC\\%s\\share\\..\\..\\%s\\s\\.git\\worktrees\\x" % (OWN_HOST, FAKE_HOST)),
            ("'..' inside a same-host UNC path", "gitdir: //%s/team/gd2/sub/../admin/.git/worktrees/x" % OWN_HOST),
        ]
        for number, (label, line) in enumerate(gitdirs):
            name = "gd%d" % number
            unc_tree(share, name, line + "\n", None)
            (share / name / "admin" / ".git" / "worktrees" / "x").mkdir(parents=True, exist_ok=True)
            touched = []
            try:
                with watch_fake_host(touched):
                    got = pp._git_file_kind(unc_of(name) + "\\.git", unc_of(name))
            except Exception as exc:  # noqa: BLE001
                check(f"W-11 [_git_file_kind, UNC tree]: gitdir with {label}", False, "raised %r" % (exc,))
                continue
            check(f"W-11 [_git_file_kind, UNC tree]: a gitdir with a {label} is ('undecidable', None)",
                  tuple(got) == ("undecidable", None), "got %r" % (got,))
            check(f"W-11 [_git_file_kind, UNC tree]: a gitdir with a {label}: nothing under the other host is probed",
                  not touched, "probed: %s" % touched)
            for copy_label, fn in copies:
                if fn is None:
                    continue
                touched = []
                try:
                    with watch_fake_host(touched):
                        own = fn(unc_of(name) + "\\src")
                except Exception as exc:  # noqa: BLE001
                    check(f"W-11 [{copy_label}, UNC tree]: gitdir with {label}", False, "raised %r" % (exc,))
                    continue
                shaped = (plain(own[0]), own[1]) if isinstance(own, (tuple, list)) and len(own) == 2 else own
                check(f"W-11 [{copy_label}, UNC tree]: a gitdir with a {label} is undecidable: (the tree, None)",
                      shaped == (plain(unc_of(name)), None), "got %r" % (own,))
                check(f"W-11 [{copy_label}, UNC tree]: a gitdir with a {label}: nothing under the other host is probed",
                      not touched, "probed: %s" % touched)

        # control: a same-host gitdir without '..' is a decidable pointer in all three walks
        unc_tree(share, "gd-ok", "gitdir: //%s/team/gd-ok/.git/worktrees/x\n" % OWN_HOST, None)
        for copy_label, fn in copies:
            if fn is None:
                continue
            try:
                own = fn(unc_of("gd-ok") + "\\src")
            except Exception as exc:  # noqa: BLE001
                own = "raised %r" % (exc,)
            ok = (isinstance(own, (tuple, list)) and len(own) == 2 and plain(own[0]) == plain(unc_of("gd-ok"))
                  and isinstance(own[1], str) and "/.git/worktrees/" in own[1].replace("\\", "/"))
            check(f"W-11 control [{copy_label}, UNC tree]: a same-host gitdir without '..' is still a decidable pointer",
                  ok, "got %r" % (own,))


def make_mapped_layout(base: Path) -> dict:
    """<base>/share/main is a main checkout (the 'mapped drive'); <base>/wt is a linked worktree of it on ANOTHER
    volume (not under the share); <base>/share/zwt is a linked worktree on the share itself."""
    share = base / "share"
    info = af.make_linked_worktree(base, name="wt1", layout="outside", main=share / "main")
    info["share"] = share
    (info["worktree"] / "src").mkdir(parents=True, exist_ok=True)
    return info


def run_mapped_drive_rows(pp, copies, base: Path) -> None:
    """Item 12: a mapped drive resolves to \\\\server\\share, and both spellings count as the tree's own host."""
    info = make_mapped_layout(base / "a")
    share, main, wt = info["share"], info["main"], info["worktree"]
    want_main = plain("\\\\%s\\team\\main" % MAP_HOST)
    touched: list = []
    with watch_fake_host(touched), af.unc_share(share, MAP_HOST, resolve_local=True, others=FOREIGN):
        kind = pp.tree_kind(str(wt / "src"))
        root = pp.main_checkout_root(str(wt / "src"))
        got = pp._git_file_kind(str(wt / ".git"), str(wt))
    check("W-12 [mapped drive]: a worktree on another volume of a mapped-drive repository reads linked-worktree (as HEAD reads it)",
          kind == "linked-worktree", "tree_kind -> %r" % (kind,))
    check("W-12 [mapped drive]: and its main checkout root is the share spelling (as HEAD returns it)",
          plain(root) == want_main, "main_checkout_root -> %r, expected %s" % (root, want_main))
    check("W-12 [mapped drive]: _git_file_kind says ('linked-worktree', the share spelling)",
          got[0] == "linked-worktree" and plain(got[1]) == want_main, "got %r" % (got,))
    check("W-12 [mapped drive]: nothing under another fake host is probed", not touched, "probed: %s" % touched)

    # the written form: the tree is opened through the 'drive' while its gitdir: is recorded in UNC form
    zwt = unc_tree(share, "zwt", "gitdir: //%s/team/main/.git/worktrees/wt1\n" % MAP_HOST, None)
    with af.unc_share(share, MAP_HOST, resolve_local=True, others=FOREIGN):
        kind = pp.tree_kind(str(zwt / "src"))
        root = pp.main_checkout_root(str(zwt / "src"))
        got = pp._git_file_kind(str(zwt / ".git"), str(zwt))
    check("W-12 [written form]: a tree opened through the drive whose gitdir: is recorded as a UNC path reads linked-worktree",
          kind == "linked-worktree", "tree_kind -> %r" % (kind,))
    check("W-12 [written form]: and its main checkout root is the share spelling",
          plain(root) == want_main, "main_checkout_root -> %r, expected %s" % (root, want_main))
    check("W-12 [written form]: _git_file_kind agrees", got[0] == "linked-worktree" and plain(got[1]) == want_main,
          "got %r" % (got,))
    for copy_label, fn in copies:
        if fn is None:
            continue
        try:
            with af.unc_share(share, MAP_HOST, resolve_local=True, others=FOREIGN):
                own = fn(str(zwt / "src"))
        except Exception as exc:  # noqa: BLE001
            own = "raised %r" % (exc,)
        ok = (isinstance(own, (tuple, list)) and len(own) == 2 and own[1] is not None
              and "/.git/worktrees/" in str(own[1]).replace("\\", "/"))
        check(f"W-12 [written form, {copy_label}]: the gitdir recorded in UNC form is a decidable pointer, not (F, None)",
              ok, "got %r" % (own,))

    # a gitdir naming a DIFFERENT host is still refused, mapped drive or not (control)
    other = unc_tree(share, "other-host", "gitdir: //%s/share/.git/worktrees/x\n" % FAKE_HOST, None)
    touched = []
    with watch_fake_host(touched), af.unc_share(share, MAP_HOST, resolve_local=True, others=FOREIGN):
        kind = pp.tree_kind(str(other / "src"))
        got = pp._git_file_kind(str(other / ".git"), str(other))
    check("W-12 control [mapped drive]: a gitdir naming a DIFFERENT host is still undecidable",
          kind == "undecidable" and tuple(got) == ("undecidable", None), "tree_kind %r, _git_file_kind %r" % (kind, got))
    check("W-12 control [mapped drive]: and nothing under that host is probed", not touched, "probed: %s" % touched)
    for copy_label, fn in copies:
        if fn is None:
            continue
        touched = []
        with watch_fake_host(touched), af.unc_share(share, MAP_HOST, resolve_local=True, others=FOREIGN):
            own = fn(str(other / "src"))
        check(f"W-12 control [mapped drive, {copy_label}]: a gitdir naming a DIFFERENT host is (the tree, None), no probe",
              isinstance(own, (tuple, list)) and own[1] is None and not touched, "got %r, probed %s" % (own, touched))


def run_device_form_rows(pp, copies, base: Path) -> None:
    """Item 12 / N1: the tree's own path in the \\\\?\\ device form names a LOCAL drive; that is not a remote host."""
    info = af.make_linked_worktree(base / "dev", layout="inside", gitdir_form="relative")
    worktree, main = info["worktree"], info["main"]
    dev = "\\\\?\\" + str(worktree)
    got = pp._git_file_kind(dev + "\\.git", dev)
    check("W-12 [device form]: _git_file_kind of a \\\\?\\<drive> tree with a local relative gitdir is a linked-worktree",
          got[0] == "linked-worktree" and plain(got[1]) == plain(main), "got %r" % (got,))
    kind = pp.tree_kind(dev)
    check("W-12 [device form]: tree_kind of the \\\\?\\<drive> path is linked-worktree", kind == "linked-worktree",
          "got %r" % (kind,))
    for copy_label, fn in copies:
        if fn is None:
            continue
        try:
            own = fn(dev)
        except Exception as exc:  # noqa: BLE001
            own = "raised %r" % (exc,)
        ok = (isinstance(own, (tuple, list)) and len(own) == 2 and plain(own[0]) == plain(worktree)
              and own[1] is not None and "/.git/worktrees/" in str(own[1]).replace("\\", "/"))
        check(f"W-12 [device form, {copy_label}]: a \\\\?\\<drive> own path with a local gitdir is not refused",
              ok, "got %r" % (own,))
    # control: the same tree through its ordinary spelling
    plain_got = pp._git_file_kind(str(worktree / ".git"), str(worktree))
    check("W-12 control [device form]: the ordinary spelling of the same tree is a linked-worktree",
          plain_got[0] == "linked-worktree", "got %r" % (plain_got,))
    # control: a device-form tree whose gitdir names ANOTHER host is still refused, with no probe
    hostile = Path(base) / "dev-hostile"
    (hostile / "src").mkdir(parents=True)
    (hostile / ".git").write_text("gitdir: //%s/share/.git/worktrees/x\n" % FAKE_HOST, encoding="utf-8")
    touched: list = []
    with watch_fake_host(touched):
        got = pp._git_file_kind("\\\\?\\" + str(hostile / ".git"), "\\\\?\\" + str(hostile))
    check("W-12 control [device form]: a gitdir naming a DIFFERENT host is still ('undecidable', None), no probe",
          tuple(got) == ("undecidable", None) and not touched, "got %r, probed %s" % (got, touched))


def run_review_round_three_hops(w: World) -> None:
    pp = load_module(af.HOOKS_DIR / "_project_paths.py", "project_paths_round_three")
    guard_mod = load_module(w.guard, "codegraph_first_guard_round_three")
    try:
        bridge = load_module(SCRIPTS_DIR / "_claude_paths.py", "claude_paths_round_three")
    except Exception as exc:  # noqa: BLE001
        check("W: the scripts bridge _claude_paths loads", False, repr(exc))
        return
    fi = load_installer()
    mods = [("helper", pp), ("guard", guard_mod), ("bridge", bridge), ("installer", fi)]
    run_hop_rows(mods)  # the four active copies (helper, guard, bridge, installer): the disabled tracker and reset copies left the set
    copies = [("helper", getattr(pp, "worktree_own_root", None)),
              ("guard inline copy", getattr(guard_mod, "_inline_own_root", None)),
              ("bridge inline copy", getattr(bridge, "_inline_worktree_own_root", None))]
    if os.name != "nt":
        skip("W-11/W-12 UNC, mapped-drive and device-form rows", "a Windows reading of paths (ntpath); this host is not Windows")
        return
    with af.Sandbox("cgw-") as sb:
        run_unc_tree_rows(pp, copies, sb.root / "unc")
        run_mapped_drive_rows(pp, copies, sb.root / "mapped")
        run_device_form_rows(pp, copies, sb.root / "devform")


# --------------------------------------------------------------------------------------------------------------
# W-13: an OLDER helper (the real _project_paths.py of pinned base commit 643b667), not a lambda stand-in
# --------------------------------------------------------------------------------------------------------------
# The "older" helper is read from a PINNED base commit (the last release before this change), never from HEAD:
# once this change is committed HEAD is the new helper and the fixture would be wrong.
BASE_COMMIT = "643b667"
BASE_HELPER_PATH = ".claude/hooks/_project_paths.py"


def head_helper_text() -> tuple:
    try:
        probe = subprocess.run(["git", "-C", str(af.PROJECT_ROOT), "cat-file", "-e", BASE_COMMIT + "^{commit}"],
                               capture_output=True, timeout=60)
        if probe.returncode != 0:
            return None, "commit %s is not available (shallow clone?): %s" % (
                BASE_COMMIT, probe.stderr.decode("utf-8", "replace").strip()[:200])
        proc = subprocess.run(["git", "-C", str(af.PROJECT_ROOT), "show", "%s:%s" % (BASE_COMMIT, BASE_HELPER_PATH)],
                              capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, repr(exc)
    if proc.returncode != 0:
        return None, proc.stderr.decode("utf-8", "replace").strip()[:200]
    return proc.stdout.decode("utf-8"), ""


@contextmanager
def helper_folder_first(folder: Path):
    """Import ``_project_paths`` / ``_claude_paths`` from ``folder`` for the span of the block; restore afterwards."""
    names = ("_project_paths", "_claude_paths", "_error_log")
    saved = {n: sys.modules.pop(n, None) for n in names}
    sys.path.insert(0, str(folder))
    try:
        yield
    finally:
        try:
            sys.path.remove(str(folder))
        except ValueError:
            pass
        for n in names:
            sys.modules.pop(n, None)
            if saved[n] is not None:
                sys.modules[n] = saved[n]


def run_older_helper_real(w: World) -> None:
    """Security P3-W2 / code reviewer W2: beside the REAL helper of the last release the guard must not call that
    helper's tree functions (they probe the host a hostile gitdir names) and must still decide."""
    text, why = head_helper_text()
    if text is None:
        skip("W-13: the guard beside the base commit's real _project_paths.py", "base commit helper is not available: %s" % why)
        print("        base commit helper is not available: " + why)
        return
    with af.Sandbox("cgo-") as sb:
        folder = sb.root / "older" / "hooks"
        folder.mkdir(parents=True)
        (folder / "_project_paths.py").write_text(text, encoding="utf-8")
        shutil.copyfile(af.HOOKS_DIR / "_error_log.py", folder / "_error_log.py")
        shutil.copyfile(w.guard, folder / HOOK_FILE)
        with helper_folder_first(folder):
            old_guard = load_module(folder / HOOK_FILE, "codegraph_guard_beside_head_helper")
        helper = old_guard._pp
        check("W-13 fixture: the helper the guard found is the base commit's (it has the tree functions and NO _hop_allowed)",
              helper is not None and callable(getattr(helper, "tree_kind", None))
              and not callable(getattr(helper, "_hop_allowed", None)),
              "helper %r" % (getattr(helper, "__file__", helper),))

        def hostile(name: str, index: bool, server: bool = True) -> Path:
            project = sb.root / name / "proj"
            (project / "src").mkdir(parents=True)
            (project / ".git").write_text("gitdir: //%s/share/.git/worktrees/x\n" % FAKE_HOST, encoding="utf-8")
            if index:
                af.plant_index(project)
            if server:
                af.plant_server(project)
            return project

        # the fixture is sensitive: calling that helper directly DOES probe the fake host
        project = hostile("ctl", True)
        touched: list = []
        with watch_fake_host(touched):
            helper.main_checkout_root(str(project / "src"))
        check("W-13 control: the base commit's own main_checkout_root probes the fake host (so a clean guard run means something)",
              bool(touched), "no probe recorded")

        for tag, index in (("with a Project index", True), ("without an index", False)):
            project = hostile("h-" + ("idx" if index else "noidx"), index)
            deep = project / "src"
            touched = []
            try:
                with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(project)}), watch_fake_host(touched):
                    candidate = old_guard._main_candidate(str(deep))
                    verdict = old_guard.index_verdict(str(deep))
            except Exception as exc:  # noqa: BLE001
                check(f"W-13 [{tag}]: the guard's _main_candidate and index_verdict run", False, "raised %r" % (exc,))
                continue
            check(f"W-13 [{tag}]: beside the base commit's helper the guard probes nothing under the fake host", not touched,
                  "probed: %s" % touched)
            check(f"W-13 [{tag}]: and never hands back a remote main checkout",
                  not (isinstance(candidate, str) and (candidate.replace("\\", "/").startswith("//") or FAKE_HOST in candidate.lower())),
                  "candidate %r" % (candidate,))
            check(f"W-13 [{tag}]: the verdict is still decided ({'index-present' if index else 'no-index'})",
                  verdict == ("index-present" if index else "no-index"), "verdict %r" % (verdict,))
        check("W-13: the guard does not bind the base commit's tree_kind (no refusal in that helper)",
              getattr(old_guard, "_pp_tree_kind", "missing") is None, "bound: %r" % (getattr(old_guard, "_pp_tree_kind", None),))
        check("W-13: the guard does not bind the base commit's main_checkout_root",
              getattr(old_guard, "_pp_main_checkout_root", "missing") is None,
              "bound: %r" % (getattr(old_guard, "_pp_main_checkout_root", None),))

        # the guard still decides, in-process, with a Session folder under the fixture temp folder
        for tag, index, want in (("block with a Project index and a configured server", True, "block"),
                                 ("allow when there is no index", False, "allow")):
            project = hostile("d-" + ("idx" if index else "noidx"), index)
            touched = []
            saved_temp, saved_cwd = tempfile.tempdir, os.getcwd()
            tempfile.tempdir = str(sb.tmp)
            try:
                with mock.patch.dict(os.environ, af.isolated_env(sb.home, sb.tmp, project), clear=True), watch_fake_host(touched):
                    os.chdir(str(project))
                    decision, reason = old_guard.decide("Read", {"file_path": str(project / "src" / "Thing.cs")},
                                                        {"session_id": sid(), "cwd": str(project / "src"),
                                                         "transcript_path": str(af.closed_transcript(sb.root / "w13-tr"))})
            except Exception as exc:  # noqa: BLE001
                decision, reason = "raised", repr(exc)
            finally:
                os.chdir(saved_cwd)
                tempfile.tempdir = saved_temp
            check(f"W-13 decide: beside the base commit's helper a Read is a {tag}", decision == want, "%s: %s" % (decision, reason))
            check(f"W-13 decide [{tag}]: and nothing under the fake host is probed", not touched, "probed: %s" % touched)

        # the installer beside the same helper: a bridge copy that sits next to the base commit's helper treats the tree as undecidable
        scripts = sb.root / "older" / "scripts"
        scripts.mkdir(parents=True)
        shutil.copyfile(SCRIPTS_DIR / "_claude_paths.py", scripts / "_claude_paths.py")
        try:
            with helper_folder_first(folder):
                bridge = load_module(scripts / "_claude_paths.py", "claude_paths_beside_head_helper")
        except Exception as exc:  # noqa: BLE001
            skip("W-13 installer: the bridge beside the base commit's helper", "it does not import beside that helper: %r" % (exc,))
            return
        fi = load_installer()
        project = hostile("fi", True)
        touched = []
        try:
            with watch_fake_host(touched), mock.patch.object(fi, "_launcher_api", lambda: bridge):
                notes = fi._codegraph_index_notes(project)
        except Exception as exc:  # noqa: BLE001
            check("W-13 installer: _codegraph_index_notes runs beside the base commit's helper", False, "raised %r" % (exc,))
            return
        check("W-13 installer: beside the base commit's helper nothing under the fake host is probed", not touched, "probed: %s" % touched)
        check("W-13 installer: and the preview says the tree cannot be decided (one plain note)",
              notes == [fi.UNDECIDABLE_TREE_NOTE], "notes %r" % (notes,))


# --------------------------------------------------------------------------------------------------------------
# W-14: the pruner's known-name pattern has an escaped dot (the guard's KNOWN_FILE_RE)
# --------------------------------------------------------------------------------------------------------------
def run_ticket_pattern(w: World) -> None:
    mod = load_module(w.guard, "codegraph_guard_known_names")
    known = ("turn.json", "ticket-" + "b" * 64, ".tmp-0123456789abcdef", "availability.json", "mcp-seen", "pruned",
             "transcript-cursor.json", "transcript-cursor.12345.tmp")
    lookalikes = ("xtmp-0123456789abcdef", "Ttmp-0123456789abcdef", "-tmp-0123456789abcdef", "turnXjson", "ticket-" + "b" * 63,
                  "transcript-cursor.abc.tmp", "transcript-cursorXjson")
    check("W-14: every known session-folder name matches the pruner's pattern",
          all(mod.KNOWN_FILE_RE.fullmatch(n) for n in known), [n for n in known if not mod.KNOWN_FILE_RE.fullmatch(n)])
    check("W-14: no look-alike name matches (the dots are escaped), so a folder holding one is kept whole",
          not any(mod.KNOWN_FILE_RE.fullmatch(n) for n in lookalikes), [n for n in lookalikes if mod.KNOWN_FILE_RE.fullmatch(n)])
    check("W-14: the guard has no function that deletes a ticket or a marker at a prompt (no hook clears tickets any more)",
          not hasattr(mod, "_delete_marker_and_tickets") and not hasattr(mod, "_delete_legacy_sentinels"))


def run_review_round_three(w: World) -> None:
    run_review_round_three_hops(w)
    run_older_helper_real(w)
    run_ticket_pattern(w)


# --------------------------------------------------------------------------------------------------------------
# Q-*: issue #271 (contract 2026-11-06-session-folder-owner-and-tool-named): the Per-user session parent, fail closed,
# the Foreign marker, the banner by reason and the Hop proof.
#
# SEAMS these rows require of the implementation (named by this suite because the contract fixes behaviour, not names):
#   * each of the three hooks defines  session_parent_base(env, os_name) -> (base or None, problem or None)
#     the pure Parent base rule; the problem is one of unset / not-absolute / remote (the text rules and the Remote rule)
#   * the guard, tracker and reset hook keep their `main()` and, for the guard, `_atomic_write(final, data) -> bool`
#   * the reset hook keeps `prune_session_folders(root, before_remove=..., now=None)`
# --------------------------------------------------------------------------------------------------------------
UNUSABLE_BANNER_FORBIDDEN = ("repeat this exact call", "through the shell")


def parent_problem_events(project: Path, reason: str, event: str = "block") -> list:
    return [rec for rec in events(project, event) if reason in json.dumps(rec)]


def unusable_records(project: Path) -> list:
    """The ``problem`` field of every ``session-state-unusable`` block record of ``project`` (exact values, in order)."""
    return [(rec.get("details") or {}).get("problem") for rec in events(project, "block")
            if (rec.get("details") or {}).get("reason") == "session-state-unusable"]


def names_problem(stderr: str, project: Path, token: str) -> bool:
    """Review fix round T-M3: the problem token is printed DELIMITED, ``(<token>)``, in the block message (the guard prints it
    verbatim), AND the block's log record carries it as its ``problem`` field exactly. A different diagnosis, or the token
    only inside a longer one ((link) vs (session-link)), does not satisfy it."""
    return ("(%s)" % token) in stderr and token in unusable_records(project)


def run_inproc(mod, payload: dict, env: dict, lstat_for: Path | None = None, stat_over: dict | None = None,
               no_access: tuple = (), fake_uid: int | None = None, argv: list | None = None) -> tuple:
    """Run ``mod.main()`` in this process on ``payload`` with ``env`` as the whole environment; return (exit code, stderr).
    ``lstat_for``: os.lstat raises ValueError for that path and everything inside it, and delegates for any other path
    (the check-failed row: one path only, so no earlier step can answer first).
    Review fix round T-H1 (runs on EVERY OS): ``fake_uid`` makes ``os.getuid`` exist and answer that id (create=True);
    ``stat_over`` maps a path to ``{"st_uid": n, "st_mode": m}``: os.lstat of exactly that path answers its real result
    with those two fields replaced; ``no_access`` lists paths for which ``os.access(path, W_OK)`` answers False."""
    import contextlib
    import io
    real_lstat = os.lstat
    real_access = os.access
    fenced = os.path.normcase(os.path.abspath(str(lstat_for))) if lstat_for is not None else None
    over = {os.path.normcase(os.path.abspath(str(k))): v for k, v in (stat_over or {}).items()}
    denied = {os.path.normcase(os.path.abspath(str(p))) for p in no_access}

    def where_of(path) -> str:
        try:
            return os.path.normcase(os.path.abspath(os.fspath(path)))
        except TypeError:
            return ""

    def fake_lstat(path, *args, **kwargs):
        if fenced is not None:
            where = where_of(path)
            if where == fenced or where.startswith(fenced + os.sep):
                raise ValueError("embedded null byte (fixture)")
        result = real_lstat(path, *args, **kwargs)
        patch = over.get(where_of(path)) if over else None
        if patch:
            fields = list(result)[:10]
            fields[0] = patch.get("st_mode", fields[0])
            fields[4] = patch.get("st_uid", fields[4])
            core = ("st_mode", "st_ino", "st_dev", "st_nlink", "st_uid", "st_gid", "st_size", "st_atime", "st_mtime", "st_ctime")
            named = {k: getattr(result, k) for k in dir(result) if k.startswith("st_") and k not in core}
            return os.stat_result(fields, named)  # the extra named fields (st_file_attributes ...) are kept
        return result

    def fake_access(path, mode, *args, **kwargs):
        if denied and where_of(path) in denied and mode == os.W_OK:
            return False
        return real_access(path, mode, *args, **kwargs)

    err = io.StringIO()
    code = 0
    # _error_log binds LOG_DIR once at first import, so an in-process main() would append to the REAL log. Point the module's
    # LOG_DIR at the sandbox project's log folder for the duration of main(); record any growth of the real logs.
    log_globals = getattr(getattr(mod, "log_event", None), "__globals__", None)
    real_dirs = {Path.home() / ".claude" / "logs"}
    patched_log = {}
    if log_globals is not None and "LOG_DIR" in log_globals:
        real_dirs.add(Path(log_globals["LOG_DIR"]))
        patched_log = {"LOG_DIR": Path(payload["cwd"]) / ".claude" / "logs"}
        if "LOG_PATH" in log_globals:
            patched_log["LOG_PATH"] = patched_log["LOG_DIR"] / "errors.jsonl"
    before = {d: real_log_size(d) for d in real_dirs}
    # tempfile.tempdir is pinned to the fixture TMP, so even a hook that still uses the temp folder cannot reach the REAL one
    with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), \
            mock.patch.object(sys, "argv", [getattr(mod, "__file__", "guard")] + list(argv or [])), \
            contextlib.redirect_stderr(err), mock.patch("os.lstat", fake_lstat), \
            mock.patch.object(tempfile, "tempdir", env.get("TMP")), \
            mock.patch.dict(log_globals if patched_log else {}, patched_log), \
            mock.patch("os.access", fake_access), contextlib.ExitStack() as extra:
        if fake_uid is not None:
            extra.enter_context(mock.patch.object(os, "getuid", create=True, return_value=fake_uid))
        try:
            mod.main()
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    for d in real_dirs:
        if real_log_size(d) != before[d]:
            INPROC_LEAKS.append(str(d))
    return code, err.getvalue()


INPROC_LEAKS: list = []  # real log folders that grew during any run_inproc call (must stay empty)


def real_log_size(folder: Path) -> int:
    try:
        return (folder / "errors.jsonl").stat().st_size
    except OSError:
        return -1


def guard_payload(project: Path, session: str, **extra) -> dict:
    """A guard payload with a CLOSED transcript (the guard decides from the transcript: a payload with none fails open)."""
    transcript = af.closed_transcript(Path(project).parent / "guard-payload-transcripts", "closed-%s.jsonl" % session)
    body = {"session_id": session, "cwd": str(project), "hook_event_name": "PreToolUse", "tool_name": "Read",
            "tool_input": read_cs(project), "transcript_path": str(transcript)}
    body.update(extra)
    return body


# ---- criterion 2: a planted Session folder in the shared temp folder opens no gate --------------------------------
def run_planted_state(w: World) -> None:
    with af.Sandbox("cgq2-") as sb:
        project = project_of(sb, "plant")
        make_logs(project)
        guard_mod = load_module(w.guard, "codegraph_first_guard_planted")
        victim = sid()
        planted = af.write_marker(sb.tmp, victim)  # an attacker's turn.json in the SHARED temp folder (stamped even)
        planted_ticket = planted.parent / ("ticket-" + guard_mod.call_fingerprint("Read", read_cs(project)))
        planted_ticket.write_text("{}\n", encoding="utf-8")
        proc = run_hook(w.guard, sb, project, "Read", read_cs(project), victim)
        check("Q-2: a turn.json planted in auto-improve-codegraph-<victim session>/ in the shared temp folder does NOT "
              "open the victim's gate: the first source Read is BLOCKED (source-target)",
              blocked(proc) and "allowed (" not in proc.stderr, describe(proc))
        check("Q-2: and a retry ticket planted there is not honoured either (no retry-escape-used)",
              "retry-escape-used" not in proc.stderr, describe(proc))
        check("Q-2: and the planted files are left exactly as planted (nothing in the temp folder is read, written or "
              "removed)", planted.is_file() and planted_ticket.is_file(), "planted files changed")
        mine = sid()
        af.write_marker(af.session_parent(sb.home), mine)
        still = run_hook(w.guard, sb, project, "Read", read_cs(project), mine)
        check("Q-2 [control]: a turn.json under the Per-user session parent opens nothing either (the marker is retired): BLOCKED",
              blocked(still), describe(still))
        mine2 = sid()
        ok = run_hook(w.guard, sb, project, "Read", read_cs(project), mine2, transcript=af.open_transcript(sb.root / "q2"))
        check("Q-2 [control]: an open transcript opens the gate (silent allow)", silent_allow(ok), describe(ok))
        before = sorted(p.name for p in sb.tmp.iterdir())
        session = sid()
        run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        run_hook(w.guard, sb, project, "", {}, session, event="UserPromptSubmit", payload_extra={"prompt": "next"}, argv=["notice"])
        after = sorted(p.name for p in sb.tmp.iterdir())
        check("Q-2: no hook creates or removes anything in the system temp folder (guard, prompt row)",
              before == after, "before %s / after %s" % (before, after))
        check("Q-2 [control]: the hooks did keep this session's state under the Per-user session parent",
              pfolder(sb, session).is_dir(), "no folder at %s" % pfolder(sb, session))


# ---- criterion 3: the pruner touches only the caller's own per-user parent ------------------------------------------
def run_parent_pruner(w: World) -> None:
    with af.Sandbox("cgq3-") as sb:
        project = project_of(sb, "prune3")
        parent = af.session_parent(sb.home)
        foreign_tmp = old_session(sb.tmp, "tmp-old")  # a leftover folder of someone else in the shared temp folder
        own_old = old_session(parent, "own-old")  # control: this user's own old folder
        link_target = old_session(sb.tmp, "link-target")  # old known files, in the temp folder
        link = parent / (af.CODEGRAPH_SESSION_PREFIX + "linked")
        linked = af.make_dir_link(link, link_target)
        session = sid()
        done = run_hook(w.guard, sb, project, "", {}, session, event="UserPromptSubmit", payload_extra={"prompt": "one"}, argv=["notice"])
        check("Q-3: the prompt row exits 0 on a first prompt", done.returncode == 0, describe(done))
        check("Q-3 [control]: it prunes this user's own old known-file folder in the Per-user session parent",
              not own_old.exists(), "own old folder still exists")
        check("Q-3: an old known-file folder in the shared TEMP folder is left alone (the temp folder is never listed)",
              foreign_tmp.is_dir() and all((foreign_tmp / n).exists() for n in KNOWN),
              "temp folder entry changed: %s" % sorted(p.name for p in foreign_tmp.iterdir()) if foreign_tmp.exists() else "gone")
        if linked:
            check("Q-3: a folder LINK inside the parent pointing into the temp folder is kept", af.is_link(link),
                  "the link was removed")
            check("Q-3: and the link's target is untouched (every known file still there)",
                  link_target.is_dir() and all((link_target / n).exists() for n in KNOWN),
                  "target holds: %s" % (sorted(p.name for p in link_target.iterdir()) if link_target.is_dir() else "<gone>"))
            try:
                os.rmdir(str(link))
            except OSError:
                pass
        else:
            skip("Q-3: a folder link in the parent", "the OS refused to create a folder link")
        # the unit seam: prune_session_folders(<parent>) lists the parent only
        mod = load_reset_module(sb, w)
        prune = getattr(mod, "prune_session_folders", None)
        if prune is None:
            check("Q-3: the guard defines prune_session_folders", False, "not defined")
        else:
            temp_only = old_session(sb.tmp, "temp-only")
            prune(str(parent), before_remove=lambda p: None)
            check("Q-3: prune_session_folders(<parent>) never reaches a sibling folder in the temp folder",
                  temp_only.is_dir(), "temp folder entry removed")
        # a foreign-owner folder is kept: only root can plant one on POSIX
        if os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() != 0:
            skip("Q-3: a foreign-owned folder in the parent is kept", "needs root on POSIX to chown a fixture folder")
        else:
            foreign = old_session(parent, "foreign-owner")
            for entry in [foreign] + list(foreign.iterdir()):
                os.chown(str(entry), 12345, 12345)
            run_hook(w.guard, sb, project, "", {}, sid(), event="UserPromptSubmit", payload_extra={"prompt": "two"}, argv=["notice"])
            check("Q-3: a folder owned by another user is kept", foreign.is_dir(), "foreign-owned folder was removed")


# ---- criterion 4 (retired by issue #262): a leftover turn.json of ANY shape opens nothing and is never judged ---------------
def run_foreign_marker(w: World) -> None:
    with af.Sandbox("cgq4-") as sb:
        parent = af.session_parent(sb.home)

        def other_session(session: str) -> None:
            marker = af.write_marker(parent, session)
            data = json.loads(marker.read_text(encoding="utf-8"))
            data["session"] = "s" + "0" * 32
            marker.write_text(json.dumps(data) + "\n", encoding="utf-8")

        def unreadable(session: str) -> None:
            folder = af.session_folder(parent, session)
            folder.mkdir()
            (folder / "turn.json").write_text("{not json\n", encoding="utf-8")

        cases = [("an unstamped (0.15.2 shape) marker", lambda s: af.write_marker(parent, s, stamped=False)),
                 ("a marker stamped for another session", other_session), ("an unreadable marker", unreadable),
                 ("a stamped OWN marker", lambda s: af.write_marker(parent, s))]
        for number, (label, setup) in enumerate(cases):
            project = project_of(sb, "fm-%d" % number)
            make_logs(project)
            session = sid()
            setup(session)
            first = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
            second = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
            check(f"Q-4 [{label}]: a leftover turn.json opens nothing: the first call BLOCKS and the identical retry is the escape",
                  blocked(first) and allowed(second, "retry-escape-used"), describe(first) + " / " + describe(second))
            check(f"Q-4 [{label}]: and no foreign-marker record or line exists any more", events(project, "foreign-marker") == []
                  and "turn marker" not in first.stderr + second.stderr, repr(events(project, "foreign-marker")))


# ---- the Parent base rule: a pure table over both OS branches, and parity of the three hooks -------------------------
def rule_rows() -> list:
    """(label, os_name, env, want_problem, want_base, realpath_map). want_base is checked only when want_problem is None."""
    srv = "\\\\srv\\s\\x"
    return [
        ("nt: LOCALAPPDATA unset", "nt", {}, "unset", None, {}),
        ("nt: LOCALAPPDATA empty", "nt", {"LOCALAPPDATA": ""}, "unset", None, {}),
        ("nt: LOCALAPPDATA relative", "nt", {"LOCALAPPDATA": "rel\\dir"}, "not-absolute", None, {}),
        ("nt: an absolute local folder", "nt", {"LOCALAPPDATA": "C:\\Users\\u\\AppData\\Local"}, None,
         "C:\\Users\\u\\AppData\\Local", {}),
        ("nt: \\\\host\\share is remote", "nt", {"LOCALAPPDATA": "\\\\host-271.invalid\\share"}, "remote", None, {}),
        ("nt: \\\\?\\UNC\\host\\share is remote", "nt", {"LOCALAPPDATA": "\\\\?\\UNC\\host-271.invalid\\share"}, "remote",
         None, {}),
        ("nt: \\\\?\\C:\\x is local", "nt", {"LOCALAPPDATA": "\\\\?\\C:\\x"}, None, "\\\\?\\C:\\x", {}),
        ("nt: \\\\?\\Volume{0}\\x (empty host) is remote", "nt", {"LOCALAPPDATA": "\\\\?\\Volume{0}\\x"}, "remote", None, {}),
        ("nt: a mapped drive whose realpath is \\\\srv\\s is remote", "nt", {"LOCALAPPDATA": "Z:\\x"}, "remote", None,
         {"Z:\\x": srv}),
        # review fix round S-M1: a device path whose '..' climbs into a UNC path, and a mapped drive in device form, are remote
        ("nt: \\\\.\\C:\\..\\UNC\\h\\s is remote (Win32 collapses the '..')", "nt",
         {"LOCALAPPDATA": "\\\\.\\C:\\..\\UNC\\host-271.invalid\\s"}, "remote", None, {}),
        ("nt: //./C:/../UNC/h/s is remote", "nt", {"LOCALAPPDATA": "//./C:/../UNC/host-271.invalid/s"}, "remote", None, {}),
        ("nt: \\\\.\\C:\\..\\..\\UNC\\h\\s is remote", "nt",
         {"LOCALAPPDATA": "\\\\.\\C:\\..\\..\\UNC\\host-271.invalid\\s"}, "remote", None, {}),
        ("nt: \\\\?\\C:\\..\\UNC\\h\\s is remote", "nt",
         {"LOCALAPPDATA": "\\\\?\\C:\\..\\UNC\\host-271.invalid\\s"}, "remote", None, {}),
        ("nt: a device path with '..' that stays local is still refused (fail closed)", "nt",
         {"LOCALAPPDATA": "\\\\?\\C:\\x\\..\\y"}, "remote", None, {}),
        ("nt: \\\\?\\Z:\\ on a mapped drive is remote", "nt", {"LOCALAPPDATA": "\\\\?\\Z:\\"}, "remote", None,
         {"drive:Z": "\\\\srv\\s"}),
        ("nt: \\\\.\\Z:\\ on a mapped drive is remote", "nt", {"LOCALAPPDATA": "\\\\.\\Z:\\"}, "remote", None,
         {"drive:Z": "\\\\srv\\s"}),
        ("nt: \\\\?\\Z:\\x on a mapped drive is remote", "nt", {"LOCALAPPDATA": "\\\\?\\Z:\\x"}, "remote", None,
         {"drive:Z": "\\\\srv\\s"}),
        ("nt [control]: \\\\?\\C:\\x stays local while Z: is mapped", "nt", {"LOCALAPPDATA": "\\\\?\\C:\\x"}, None,
         "\\\\?\\C:\\x", {"drive:Z": "\\\\srv\\s"}),
        ("nt [control]: \\\\.\\C:\\x stays local while Z: is mapped", "nt", {"LOCALAPPDATA": "\\\\.\\C:\\x"}, None,
         "\\\\.\\C:\\x", {"drive:Z": "\\\\srv\\s"}),
        # review pass 2 (round 3) M1: the canonical form is judged, never raw[4:] offsets. A doubled separator after the
        # device prefix, and the NT object-manager prefix, both reach the mapped drive / a UNC share in Win32
        ("nt: \\\\.\\\\Z:\\x (doubled separator after \\\\.\\) on a mapped drive is remote", "nt",
         {"LOCALAPPDATA": "\\\\.\\\\Z:\\x"}, "remote", None, {"drive:Z": "\\\\srv\\s"}),
        ("nt: \\\\?\\\\Z:\\x (doubled separator after \\\\?\\) on a mapped drive is remote", "nt",
         {"LOCALAPPDATA": "\\\\?\\\\Z:\\x"}, "remote", None, {"drive:Z": "\\\\srv\\s"}),
        ("nt: //.//Z:/x on a mapped drive is remote", "nt", {"LOCALAPPDATA": "//.//Z:/x"}, "remote", None,
         {"drive:Z": "\\\\srv\\s"}),
        ("nt: \\\\.\\/Z:\\x (mixed separators) on a mapped drive is remote", "nt", {"LOCALAPPDATA": "\\\\.\\/Z:\\x"},
         "remote", None, {"drive:Z": "\\\\srv\\s"}),
        ("nt: \\??\\Z:\\x (NT prefix) on a mapped drive is remote", "nt", {"LOCALAPPDATA": "\\??\\Z:\\x"}, "remote", None,
         {"drive:Z": "\\\\srv\\s"}),
        ("nt: \\??\\C:\\Windows (NT prefix, even on a fixed drive) is remote", "nt", {"LOCALAPPDATA": "\\??\\C:\\Windows"},
         "remote", None, {"drive:Z": "\\\\srv\\s"}),
        ("nt: \\??\\UNC\\h\\s (NT prefix, UNC) is remote", "nt", {"LOCALAPPDATA": "\\??\\UNC\\host-271.invalid\\s"}, "remote",
         None, {}),
        ("nt [control]: C:\\x stays local while Z: is mapped", "nt", {"LOCALAPPDATA": "C:\\x"}, None, "C:\\x",
         {"drive:Z": "\\\\srv\\s"}),
        # review pass 3 (round 4) M1/L1: a rooted base with no drive letter resolves against the cwd's drive (which may be a
        # mapped network drive), and a drive designator that is not an ASCII letter reaches realpath with no drive-table
        # question: both are 'not-absolute' on every Python version, whatever the cwd's drive is
        ("nt: \\x (rooted, no drive) is not-absolute", "nt", {"LOCALAPPDATA": "\\x"}, "not-absolute", None, {}),
        ("nt: /x/y (rooted, no drive) is not-absolute", "nt", {"LOCALAPPDATA": "/x/y"}, "not-absolute", None, {}),
        ("nt: \\AppData\\Local (rooted, no drive) is not-absolute", "nt", {"LOCALAPPDATA": "\\AppData\\Local"},
         "not-absolute", None, {"drive:Z": "\\\\srv\\s"}),
        ("nt: 1:\\x (the drive designator is a digit) is not-absolute", "nt", {"LOCALAPPDATA": "1:\\x"}, "not-absolute", None, {}),
        ("nt: ' :\\x' (the drive designator is a space) is not-absolute", "nt", {"LOCALAPPDATA": " :\\x"}, "not-absolute",
         None, {}),
        # review pass 3 (round 4) L2: leading separators that are not exactly the \\?\ or \\.\ device prefix are remote
        ("nt: \\\\\\?\\Z:\\x (three separators before the ?) is remote", "nt", {"LOCALAPPDATA": "\\\\\\?\\Z:\\x"}, "remote",
         None, {}),
        ("nt: \\\\\\.\\Z:\\x (three separators before the .) is remote", "nt", {"LOCALAPPDATA": "\\\\\\.\\Z:\\x"}, "remote",
         None, {}),
        ("nt: \\\\?z:\\x (a UNC server named ?z:) is remote", "nt", {"LOCALAPPDATA": "\\\\?z:\\x"}, "remote", None, {}),
        ("nt: //?z:/x (a UNC server named ?z:) is remote", "nt", {"LOCALAPPDATA": "//?z:/x"}, "remote", None, {}),
        ("nt: \\/\\?\\C:\\x (mixed separators, three before the ?) is remote", "nt", {"LOCALAPPDATA": "\\/\\?\\C:\\x"},
         "remote", None, {}),
        ("nt: ////?/C:/x (four separators before the ?) is remote", "nt", {"LOCALAPPDATA": "////?/C:/x"}, "remote", None, {}),
        ("nt: LOCALAPPDATA is never skipped to HOME or XDG", "nt", {"XDG_CACHE_HOME": "/c", "HOME": "/h"}, "unset", None, {}),
        ("posix: XDG_CACHE_HOME set", "posix", {"XDG_CACHE_HOME": "/x/cache", "HOME": "/h"}, None, "/x/cache", {}),
        ("posix: XDG_CACHE_HOME empty falls to HOME/.cache", "posix", {"XDG_CACHE_HOME": "", "HOME": "/h"}, None,
         "/h/.cache", {}),
        ("posix: XDG_CACHE_HOME unset falls to HOME/.cache", "posix", {"HOME": "/h"}, None, "/h/.cache", {}),
        ("posix: XDG_CACHE_HOME relative is not-absolute (never skipped to HOME)", "posix",
         {"XDG_CACHE_HOME": "rel/cache", "HOME": "/h"}, "not-absolute", None, {}),
        ("posix: both unset", "posix", {}, "unset", None, {}),
        ("posix: both empty", "posix", {"XDG_CACHE_HOME": "", "HOME": ""}, "unset", None, {}),
    ]


PROBLEM_NAMES = ("unset", "not-absolute", "remote", "cannot-create", "link", "not-a-folder", "foreign-owner",
                 "open-mode", "unwritable", "check-failed")

#: Review fix round C-W2: the shared verdict code every hook carries inline; the three copies must stay textually identical.
SHARED_VERDICT_FUNCTIONS = ("session_parent_base", "_base_shown", "_create_parent", "resolve_session_parent",
                            "session_folder_problem", "_remote_host", "_own_spellings")


#: Review pass 2 (round 3): the helper that decides "link" for the Parent and the Session folder, and the module constants the
#: shared verdict code reads. ``_is_link_stat`` is compared without its docstring (the three docstrings differ in wording).
SHARED_NODOC_FUNCTIONS = ("_is_link_stat",)
SHARED_CONSTANTS = ("_LOCAL_DEVICE_HOST_RE", "PARENT_NAME", "_REPARSE_POINT", "PARENT_PROBLEMS")


def function_source(path: Path, name: str) -> str | None:
    """The source text of the top-level function ``name`` in ``path`` (decorators and docstring included), else None."""
    import ast
    text = Path(path).read_text(encoding="utf-8")
    for node in ast.parse(text).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(text, node)
    return None


def function_source_nodoc(path: Path, name: str) -> str | None:
    """Like function_source, but the docstring is dropped: the code alone is compared."""
    import ast
    text = Path(path).read_text(encoding="utf-8")
    for node in ast.parse(text).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            body = list(node.body)
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant)                     and isinstance(body[0].value.value, str):
                body = body[1:]
            node.body = body or [ast.Pass()]
            node.decorator_list = list(node.decorator_list)
            return ast.unparse(node)
    return None


def constant_source(path: Path, name: str) -> str | None:
    """The source text of the top-level assignment of ``name`` in ``path``, else None."""
    import ast
    text = Path(path).read_text(encoding="utf-8")
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.get_source_segment(text, node)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.get_source_segment(text, node)
    return None


def parity_differences(paths: list) -> list:
    """The names of the shared verdict functions, helpers and constants whose source differs between ``paths`` (or is missing)."""
    out = [name for name in SHARED_VERDICT_FUNCTIONS if len({function_source(p, name) for p in paths}) != 1
           or function_source(paths[0], name) is None]
    out += [name for name in SHARED_NODOC_FUNCTIONS if len({function_source_nodoc(p, name) for p in paths}) != 1
            or function_source_nodoc(paths[0], name) is None]
    out += [name for name in SHARED_CONSTANTS if len({constant_source(p, name) for p in paths}) != 1
            or constant_source(paths[0], name) is None]
    return out


def run_verdict_function_parity(w: World) -> None:
    """C-6: the Per-user session parent code has ONE active copy, in the guard. The disabled tracker and reset copies left the parity
    set; they stay byte-identical to their last release (a released hash of their ``disabled`` entry), and the guard's block
    still defines every function and constant the three hooks used to share."""
    present = [n for n in SHARED_VERDICT_FUNCTIONS + SHARED_NODOC_FUNCTIONS if function_source(w.guard, n) is not None]
    missing = [n for n in SHARED_VERDICT_FUNCTIONS + SHARED_NODOC_FUNCTIONS if n not in present]
    check("Q-parity: the guard defines resolve_session_parent, _create_parent, session_folder_problem, _base_shown, "
          "session_parent_base, _remote_host, _own_spellings and _is_link_stat", not missing, "missing in the guard: %s" % missing)
    check("Q-parity: and the constants _LOCAL_DEVICE_HOST_RE, PARENT_NAME, _REPARSE_POINT and PARENT_PROBLEMS",
          all(constant_source(w.guard, n) is not None for n in SHARED_CONSTANTS),
          [n for n in SHARED_CONSTANTS if constant_source(w.guard, n) is None])
    disabled = {e[af.DISABLED_HOOK]: e for e in af.disabled_entries(ADD_ON)}
    for name, path in ((TRACKER_FILE, w.tracker), (RESET_FILE, w.reset)):
        digest = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        check(f"Q-parity [{name}]: the disabled copy is byte-identical (folded) to a released copy, so no active edit ever reached it",
              digest in disabled[name][af.DISABLED_HASHES], digest)
    # (the parity set is the guard alone: a later edit to the guard's block is not held to the frozen copies)


def run_parent_rule_table(w: World) -> None:
    hooks = [("guard", w.guard)]  # the one active copy (C-6)
    answers: dict = {}
    decoy = {"LOCALAPPDATA": "C:\\decoy-from-os-environ", "XDG_CACHE_HOME": "/decoy-from-os-environ",
             "HOME": "/decoy-home-from-os-environ"}
    for name, path in hooks:
        mod = load_module(path, "codegraph_rule_" + name)
        fn = getattr(mod, "session_parent_base", None)
        if fn is None:
            check(f"Q-rule [{name}]: defines session_parent_base(env, os_name) (the pure Parent base rule)", False,
                  "%s has no session_parent_base" % path.name)
            continue
        for label, os_name, env, want_problem, want_base, realmap in rule_rows():
            def fake_realpath(p, *a, _map=realmap, **k):
                # review fix round S-M1: ``drive:Z`` in the map means "drive Z: is a mapped network drive": any spelling of a
                # path on it (X:\..., \\?\X:\..., \\.\X:\...) resolves to the share (the CPython realpath behaviour assumed)
                text = os.fspath(p)
                if text in _map:
                    return _map[text]
                drive = re.match(r"^(?:[\\/]{2}[?.][\\/])?([A-Za-z]):", text)
                if drive and ("drive:" + drive.group(1).upper()) in _map:
                    return _map["drive:" + drive.group(1).upper()] + text[drive.end():].replace("/", "\\").rstrip("\\")
                return text

            def fake_drive_type(root, _map=realmap):
                # the other seam an implementation may use to learn a drive is remote: kernel32.GetDriveTypeW (4 = DRIVE_REMOTE)
                drive = re.match(r"^(?:[\\/]{2}[?.][\\/])?([A-Za-z]):", str(root))
                return 4 if drive and ("drive:" + drive.group(1).upper()) in _map else 3
            windll = types.SimpleNamespace(kernel32=types.SimpleNamespace(GetDriveTypeW=fake_drive_type))
            try:
                with mock.patch.dict(os.environ, decoy), mock.patch("os.path.realpath", fake_realpath), \
                        mock.patch("ctypes.windll", windll, create=True):
                    got = tuple(fn(dict(env), os_name))
            except Exception as exc:  # noqa: BLE001
                got = ("raised %r" % (exc,), None)
            answers.setdefault(label, {})[name] = got
            ok = len(got) == 2 and got[1] == want_problem and (want_problem is not None or got[0] == want_base)
            check(f"Q-rule [{name}] {label}: problem {want_problem!r}" + (f", base {want_base!r}" if want_problem is None else ""),
                  ok, "got %r" % (got,))
    for label, per_hook in answers.items():
        if len(per_hook) == 3:
            check(f"Q-parity: the three hooks answer alike on [{label}]",
                  len({repr(v) for v in per_hook.values()}) == 1, repr(per_hook))
    for name, path in hooks:
        text = path.read_text(encoding="utf-8")
        missing = [p for p in PROBLEM_NAMES if ('"%s"' % p) not in text and ("'%s'" % p) not in text]
        check(f"Q-parity [{name}]: the hook knows the whole Parent problem set", not missing, "missing: %s" % missing)
        import ast
        calls_temp = [node.lineno for node in ast.walk(ast.parse(text))
                      if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "gettempdir"]
        check(f"Q-parity [{name}]: the hook no longer CALLS gettempdir() (a comment may still name it)",
              not calls_temp, "gettempdir() is called in %s at line(s) %s" % (path.name, calls_temp))


# ---- criterion 9: every Parent problem fails closed, on disk ----------------------------------------------------------
def run_unusable_parent(w: World) -> None:
    nt = os.name == "nt"

    def make_base(sb: af.Sandbox) -> Path:
        base = sb.home / "AppData" / "Local" if nt else sb.home / ".cache"
        if not base.is_dir():
            os.mkdir(str(base), 0o700)
            os.chmod(str(base), 0o700)
        return base

    def file_parent(sb):
        (make_base(sb) / "auto-improve-codegraph").write_text("x\n", encoding="utf-8")
        return {}, str(make_base(sb)), None

    def link_parent(sb):
        target = sb.root / "parent-link-target"
        target.mkdir()
        if not af.make_dir_link(make_base(sb) / "auto-improve-codegraph", target):
            return None
        return {}, str(make_base(sb)), target

    def open_mode(sb):
        parent = make_base(sb) / "auto-improve-codegraph"
        os.mkdir(str(parent), 0o755)
        os.chmod(str(parent), 0o755)
        return {}, str(make_base(sb)), None

    def cannot_create(sb):
        missing = sb.home / "missing-a" / "missing-b" / ("Local" if nt else ".cache")
        return {("LOCALAPPDATA" if nt else "XDG_CACHE_HOME"): str(missing)}, str(missing), None

    def unset(sb):
        return ({"LOCALAPPDATA": ""} if nt else {"XDG_CACHE_HOME": "", "HOME": ""}), "", None

    def relative(sb):
        return {("LOCALAPPDATA" if nt else "XDG_CACHE_HOME"): "relative-271"}, "relative-271", None

    def remote(sb):
        return {"LOCALAPPDATA": "\\\\remote-host-271.invalid\\share"}, "remote-host-271.invalid", None

    scenarios = [("the parent is a plain file", "not-a-folder", file_parent, "", False),
                 ("the parent is a link", "link", link_parent, "remove the link", False),
                 ("the parent is open to other users (mode 0755)", "open-mode", open_mode, "chmod 700", True),
                 ("the base folder is missing", "cannot-create", cannot_create, "", False),
                 ("the base variable is unset or empty", "unset", unset, "LOCALAPPDATA" if nt else "XDG_CACHE_HOME", False),
                 ("the base variable is relative", "not-absolute", relative, "", False),
                 ("the base is a network path (Windows)", "remote", remote, "", None)]
    for label, problem, build, fix, posix_only in scenarios:
        if posix_only is True and nt:
            skip(f"Q-9 [{label}]", "POSIX only (mode bits)")
            continue
        if posix_only is None and not nt:
            skip(f"Q-9 [{label}]", "Windows only (the Remote rule)")
            continue
        with af.Sandbox("cgq9-") as sb:
            built = build(sb)
            if built is None:
                skip(f"Q-9 [{label}]", "the OS refused to create a folder link")
                continue
            extra, shown, link_target = built
            project = project_of(sb, "u9")
            make_logs(project)
            first = run_hook(w.guard, sb, project, "Read", read_cs(project), sid(), extra_env=extra)
            second = run_hook(w.guard, sb, project, "Read", read_cs(project), sid(), extra_env=extra)
            text = first.stderr
            check(f"Q-9 [{label}]: the guard BLOCKS a source Read (fails closed) and names the problem {problem}",
                  blocked(first) and names_problem(text, project, problem), describe(first))
            check(f"Q-9 [{label}]: the message names the path or variable concerned", (not shown) or shown in text, text)
            check(f"Q-9 [{label}]: and the fix", (not fix) or fix.lower() in text.lower(), text)
            check(f"Q-9 [{label}]: and the uninstall skill, with a new session", "/auto-improve-codegraph-uninstall" in text
                  and "new session" in text.lower(), text)
            check(f"Q-9 [{label}]: it offers NO retry, advises no shell route (no 'cat ', no 'through the shell')",
                  not any(p in text for p in UNUSABLE_BANNER_FORBIDDEN) and re.search(r"\b(cat|sed)\s", text) is None, text)
            blocks = parent_problem_events(project, "session-state-unusable")
            check(f"Q-9 [{label}]: one block record per blocked call (two calls, two records)", len(blocks) == 2,
                  "records: %r" % blocks)
            check(f"Q-9 [{label}]: and each record's problem field is exactly {problem}",
                  unusable_records(project) == [problem, problem], "problem fields: %r" % unusable_records(project))
            check(f"Q-9 [{label}]: the second identical-shape call is still blocked (no ticket was ever written)",
                  blocked(second) and "allowed (" not in second.stderr, describe(second))
            check(f"Q-9 [{label}]: nothing was created in the fixture temp folder", sorted(sb.tmp.iterdir()) == [],
                  "temp holds: %s" % [p.name for p in sb.tmp.iterdir()])
            if link_target is not None:
                check(f"Q-9 [{label}]: and nothing was written through the link", not any(link_target.iterdir()),
                      "target holds: %s" % [p.name for p in link_target.iterdir()])
            # steps 4-6 still apply: a subagent and a project without an index are let through, and no log record is written
            sub = run_hook(w.guard, sb, project, "Read", read_cs(project), sid(), extra_env=extra,
                           payload_extra={"agent_id": "a-271", "agent_type": "general-purpose"})
            noidx = project_of(sb, "u9-noidx", index=False)
            make_logs(noidx)
            free = run_hook(w.guard, sb, noidx, "Read", read_cs(noidx), sid(), extra_env=extra)
            check(f"Q-9 [{label}]: a subagent payload is still let through (fail-open:subagent) and writes no log record",
                  allowed(sub, "fail-open:subagent") and events(project, "fail-open") == [], describe(sub))
            if clean_above("Q-9 no-index", noidx):
                check(f"Q-9 [{label}]: a project with no index is still let through (fail-open:no-index), with no log record",
                      allowed(free, "fail-open:no-index") and events(noidx, "fail-open") == [], describe(free))
            # the prompt row prunes nothing through the unusable parent, says why in one line (no claim about the gate), exits 0
            # and leaves the legacy sentinel alone (nothing deletes it since the cut-over)
            legacy = project / ".claude" / ".codegraph-used-this-turn"
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text("legacy\n", encoding="utf-8")
            bait = old_session(link_target, "bait") if link_target is not None else None
            reset = run_hook(w.guard, sb, project, "", {}, sid(), extra_env=extra, event="UserPromptSubmit",
                             payload_extra={"prompt": "next"}, argv=["notice"])
            check(f"Q-9 [{label}]: the prompt row exits 0, prints the one line naming the problem, makes no 'gate stays shut' claim",
                  reset.returncode == 0 and "cannot be used" in reset.stderr and ("(" + problem + ")") in reset.stderr
                  and "gate stays shut" not in reset.stderr, describe(reset))
            check(f"Q-9 [{label}]: and deletes no legacy sentinel", legacy.exists(), describe(reset))
            if bait is not None:
                check(f"Q-9 [{label}]: and prunes nothing through the unusable parent", bait.is_dir()
                      and all((bait / n).exists() for n in KNOWN), "the folder behind the link was touched")
    # control: a usable parent keeps today's source-target block and its retry
    with af.Sandbox("cgq9c-") as sb:
        project = project_of(sb, "u9c")
        session = sid()
        first = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        retry = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        check("Q-9 [control]: with a usable parent the same call blocks as source-target and the retry is allowed",
              blocked(first) and "session-state-unusable" not in first.stderr and allowed(retry, "retry-escape-used"),
              describe(first) + " / " + describe(retry))


# ---- criterion 9b (merge order): an unusable Session state still lets a NON-source call through, silently -------------
# Merged step order: session check -> marker -> targets -> subagent/index/server -> ticket. The verdict runs BEFORE the
# targets, so the silent allow of a README read, a read with no target and a `**/*.md` glob depends on step 1 skipping the
# marker read and step 2 still running after an unusable verdict. A "fail fast" edit (block on an unusable state before
# classifying) would break it; these rows pin it. `a.py` blocks as the control in the same fixture.
def run_unusable_nonsource(w: World) -> None:
    nt = os.name == "nt"
    variable = "LOCALAPPDATA" if nt else "XDG_CACHE_HOME"

    def relative_base(sb, session):
        return {variable: "relative-271"}, "not-absolute", None

    def session_link(sb, session):
        target = sb.root / "nonsource-link-target"
        target.mkdir()
        af.session_parent(sb.home)  # a usable Per-user session parent
        if not af.make_dir_link(pfolder(sb, session), target):
            return None
        return {}, "session-link", target

    for label, build in (("LOCALAPPDATA/XDG_CACHE_HOME relative", relative_base), ("the Session folder is a link", session_link)):
        with af.Sandbox("cgq9n-") as sb:
            session = sid()
            built = build(sb, session)
            if built is None:
                skip(f"Q-9n [{label}]", "the OS refused to create a folder link")
                continue
            extra, problem, link_target = built
            project = project_of(sb, "u9n")
            make_logs(project)
            calls_ = (("a README Read", "Read", {"file_path": str(project / "README.md")}),
                      ("a Read with no target", "Read", {}),
                      ("a **/*.md Glob", "Glob", {"pattern": "**/*.md"}))
            for what, tool, tool_input in calls_:
                proc = run_hook(w.guard, sb, project, tool, tool_input, session, extra_env=extra)
                check(f"Q-9n [{label}]: {what} exits 0 with EMPTY stderr", proc.returncode == 0 and proc.stderr == "", describe(proc))
            check(f"Q-9n [{label}]: and none of the three wrote a block record", events(project, "block") == [],
                  repr(events(project, "block")))
            control = run_hook(w.guard, sb, project, "Read", {"file_path": str(project / "a.py")}, session, extra_env=extra)
            check(f"Q-9n [{label}] [control]: a.py in the same fixture BLOCKS as session-state-unusable ({problem})",
                  blocked(control) and names_problem(control.stderr, project, problem), describe(control))
            if link_target is not None:
                check(f"Q-9n [{label}]: and nothing was written through the link", not any(link_target.iterdir()),
                      "target holds: %s" % [p.name for p in link_target.iterdir()])
    # in-process: decide() allows a non-source target with the Session folder a link, and writes nothing through it
    with af.Sandbox("cgq9d-") as sb:
        session = sid()
        target = sb.root / "decide-link-target"
        target.mkdir()
        af.session_parent(sb.home)
        project = project_of(sb, "u9d")
        make_logs(project)
        if not af.make_dir_link(pfolder(sb, session), target):
            skip("Q-9n decide: non-source-target with a link Session folder", "the OS refused to create a folder link")
        else:
            guard_mod = load_module(w.guard, "codegraph_first_guard_nonsource_decide")
            saved_cwd = os.getcwd()
            try:
                with mock.patch.dict(os.environ, af.isolated_env(sb.home, sb.tmp, project), clear=True), \
                        mock.patch.object(tempfile, "tempdir", str(sb.tmp)):
                    os.chdir(str(project))
                    got = guard_mod.decide("Read", {"file_path": str(project / "n.md")}, {"session_id": session, "cwd": str(project)})
            except Exception as exc:  # noqa: BLE001
                got = ("raised", repr(exc))
            finally:
                os.chdir(saved_cwd)
            check("Q-9n decide: a .md Read with the Session folder a link is ('allow', 'non-source-target')",
                  tuple(got) == ("allow", "non-source-target"), repr(got))
            check("Q-9n decide: and the link target is unchanged (empty)", list(target.iterdir()) == [],
                  "target holds: %s" % [p.name for p in target.iterdir()])


# ---- check-failed: an exception while computing the verdict is a block, never the I-4 allow ---------------------------
def run_check_failed(w: World) -> None:
    with af.Sandbox("cgq9f-") as sb:
        project = project_of(sb, "cf")
        make_logs(project)
        parent = af.session_parent(sb.home)
        old_in_parent = old_session(parent, "cf-old")
        env = af.isolated_env(sb.home, sb.tmp, project)
        guard_mod = load_module(w.guard, "codegraph_first_guard_checkfailed")
        code, err = run_inproc(guard_mod, guard_payload(project, sid()), env, lstat_for=parent)
        check("Q-9f: os.lstat raising ValueError for the parent path only: the guard BLOCKS (exit 2), not the I-4 allow",
              code == 2 and "BLOCKED" in err and "internal error" not in err and "repeat this exact call" not in err,
              "exit=%s stderr=%r" % (code, err[-500:]))
        check("Q-9f: the message names the exception type (ValueError) and the problem check-failed (message or log record)",
              "ValueError" in err and names_problem(err, project, "check-failed"), err[-500:])
        check("Q-9f: and the block is logged with reason session-state-unusable",
              parent_problem_events(project, "session-state-unusable") != [], repr(events(project, "block")))
        legacy = project / ".claude" / ".codegraph-used-this-turn"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text("legacy\n", encoding="utf-8")
        notice_mod = load_module(w.guard, "codegraph_guard_notice_checkfailed")
        code, err = run_inproc(notice_mod, {"session_id": sid(), "cwd": str(project), "prompt": "next"}, env, lstat_for=parent,
                               argv=["notice"])
        check("Q-9f: the prompt row prunes nothing under the parent (exit 0) and leaves the legacy sentinel alone",
              code == 0 and old_in_parent.is_dir() and legacy.exists(), "exit=%s old exists=%s legacy=%s %r"
              % (code, old_in_parent.is_dir(), legacy.exists(), err))
        # control: the same wrapper with no index still lets the read through (step 4 runs), writing no log record
        noidx = project_of(sb, "cf-noidx", index=False)
        make_logs(noidx)
        env2 = af.isolated_env(sb.home, sb.tmp, noidx)
        code, err = run_inproc(load_module(w.guard, "codegraph_first_guard_checkfailed2"), guard_payload(noidx, sid()),
                               env2, lstat_for=parent)
        check("Q-9f [control]: the same wrapper with no index allows (fail-open:no-index) and writes no log record",
              code == 0 and "fail-open:no-index" in err and events(noidx, "fail-open") == [] and events(noidx, "block") == [],
              "exit=%s stderr=%r records=%r" % (code, err[-300:], events(noidx)))
        check("Q-9f [isolation]: no in-process run wrote to the real errors.jsonl (its size is unchanged)",
              INPROC_LEAKS == [], repr(INPROC_LEAKS))


# ---- announce: a no-index allow with an unusable parent writes nothing through it -------------------------------------
def run_announce_unusable(w: World) -> None:
    with af.Sandbox("cgq9a-") as sb:
        base = sb.home / "AppData" / "Local" if os.name == "nt" else sb.home / ".cache"
        if os.name != "nt":
            os.mkdir(str(base), 0o700)
            os.chmod(str(base), 0o700)
        target = sb.root / "announce-target"
        target.mkdir()
        if not af.make_dir_link(base / "auto-improve-codegraph", target):
            skip("Q-announce: the parent is a link", "the OS refused to create a folder link")
        else:
            noidx = project_of(sb, "an", index=False)
            make_logs(noidx)
            if clean_above("Q-announce", noidx):
                proc = run_hook(w.guard, sb, noidx, "Read", read_cs(noidx), sid())
                check("Q-announce: a no-index allow still prints its line (fail-open:no-index)",
                      allowed(proc, "fail-open:no-index"), describe(proc))
                check("Q-announce: and creates nothing inside or through the unusable parent (no logged-* flag)",
                      list(target.iterdir()) == [], "target holds: %s" % [p.name for p in target.iterdir()])
                check("Q-announce: and writes no log record (no state exists to rate-limit it)",
                      events(noidx, "fail-open") == [], repr(events(noidx, "fail-open")))
        with af.Sandbox("cgq9b-") as sb2:
            noidx = project_of(sb2, "an-ctl", index=False)
            make_logs(noidx)
            if clean_above("Q-announce control", noidx):
                run_hook(w.guard, sb2, noidx, "Read", read_cs(noidx), sid())
                check("Q-announce [control]: with a usable parent the same allow writes its one log record",
                      len(events(noidx, "fail-open")) == 1, repr(events(noidx, "fail-open")))


# ---- retry-ticket-unwritten and the link swap ------------------------------------------------------------------------
def run_ticket_unwritten(w: World) -> None:
    with af.Sandbox("cgq8-") as sb:
        project = project_of(sb, "tk")
        make_logs(project)
        guard_mod = load_module(w.guard, "codegraph_first_guard_ticket")
        session = sid()
        folder = pfolder(sb, session, True)
        folder.mkdir()
        ticket = folder / ("ticket-" + guard_mod.call_fingerprint("Read", read_cs(project)))
        ticket.mkdir()
        proc = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        text = proc.stderr
        check("Q-8: a ticket that cannot be written BLOCKS with retry-ticket-unwritten", blocked(proc), describe(proc))
        check("Q-8: the message names the Session folder", af.CODEGRAPH_SESSION_PREFIX + session in text, text)
        check("Q-8: it says the usual cause is a passing lock (an antivirus or indexer) or a full disk",
              ("antivirus" in text.lower() or "indexer" in text.lower()) and "disk" in text.lower(), text)
        check("Q-8: its retry line says the guard 'tries again to record the retry'",
              "tries again to record the retry" in text, text)
        check("Q-8: and it does not say 'it will be allowed and logged'", "will be allowed and logged" not in text, text)
        check("Q-8: it names LOCALAPPDATA, chmod and links nowhere", not any(n in text for n in ("LOCALAPPDATA", "chmod"))
              and re.search(r"\blink\b", text, re.IGNORECASE) is None, text)
        check("Q-8: it names a CodeGraph tool call (mcp__codegraph__*) and the uninstall skill as the other ways out",
              "mcp__codegraph__*" in text and "/auto-improve-codegraph-uninstall" in text, text)
        check("Q-8: the block is logged with reason retry-ticket-unwritten",
              parent_problem_events(project, "retry-ticket-unwritten") != [], repr(events(project, "block")))
        os.rmdir(str(ticket))  # the write works again
        again = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        check("Q-8: once the write works again, the repeat blocks as source-target (with its usual retry line)",
              blocked(again) and "repeat this exact call once; it will be allowed and logged" in again.stderr
              and "retry-ticket-unwritten" not in again.stderr, describe(again))
        retry = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        check("Q-8: and the identical call after it is allowed (retry-escape-used)", allowed(retry, "retry-escape-used"),
              describe(retry))

        # link swap: the Session folder becomes a link between step 2 and step 8
        target = sb.root / "swap-target"
        target.mkdir()
        project2 = project_of(sb, "tk-swap")
        make_logs(project2)
        session2 = sid()
        folder2 = pfolder(sb, session2)
        swapped: list = []
        guard2 = load_module(w.guard, "codegraph_first_guard_swap")
        real_write = guard2._atomic_write

        def swap_then_fail(final, data):
            if os.path.basename(final).startswith("ticket-") and not swapped:
                shutil.rmtree(str(folder2), ignore_errors=True)
                swapped.append(af.make_dir_link(folder2, target))
                return False
            return real_write(final, data)

        env = af.isolated_env(sb.home, sb.tmp, project2)
        with mock.patch.object(guard2, "_atomic_write", swap_then_fail):
            code, err = run_inproc(guard2, guard_payload(project2, session2), env)
        if not swapped or not swapped[0]:
            skip("Q-8 link swap", "the ticket write was never attempted, or the OS refused to create a folder link")
        else:
            check("Q-8 link swap: the folder replaced by a link when the write fails: BLOCK session-state-unusable, "
                  "problem session-link (not retry-ticket-unwritten)",
                  code == 2 and names_problem(err, project2, "session-link") and "retry-ticket-unwritten" not in err
                  and parent_problem_events(project2, "session-state-unusable") != [], "exit=%s %r" % (code, err[-500:]))
            check("Q-8 link swap: and nothing was written through the link", not any(target.iterdir()),
                  "target holds: %s" % [p.name for p in target.iterdir()])
            check("Q-8 link swap [isolation]: no in-process run wrote to the real errors.jsonl (its size is unchanged)",
                  INPROC_LEAKS == [], repr(INPROC_LEAKS))
            try:
                os.rmdir(str(folder2))
            except OSError:
                pass


# ---- the banner chooses its retry line by reason ---------------------------------------------------------------------
def run_banner_by_reason(w: World) -> None:
    with af.Sandbox("cgqb-") as sb:
        project = project_of(sb, "bn")
        src = project / "src"
        for label, tool, tool_input in (("source-target (Read .cs)", "Read", read_cs(project)),
                                        ("ambiguous-target (Glob **/*)", "Glob", {"pattern": "**/*", "path": str(src)})):
            proc = run_hook(w.guard, sb, project, tool, tool_input, sid())
            check(f"Q-banner [{label}]: keeps today's retry lines 'repeat this exact call once; it will be allowed and logged'",
                  blocked(proc) and "repeat this exact call once; it will be allowed and logged" in proc.stderr, describe(proc))
            check(f"Q-banner [{label}]: and the uninstall lines", "/auto-improve-codegraph-uninstall" in proc.stderr
                  and "new session" in proc.stderr.lower(), describe(proc))


# ---- the Hop proof: TREE_HOP_REFUSAL, or the 0.15.2 helper's shape -----------------------------------------------------
def helper_text_at(commit: str) -> tuple:
    try:
        probe = subprocess.run(["git", "-C", str(af.PROJECT_ROOT), "cat-file", "-e", commit + "^{commit}"],
                               capture_output=True, timeout=60)
        if probe.returncode != 0:
            return None, "commit %s is not available (shallow clone?)" % commit
        proc = subprocess.run(["git", "-C", str(af.PROJECT_ROOT), "show", "%s:%s" % (commit, BASE_HELPER_PATH)],
                              capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, repr(exc)
    if proc.returncode != 0:
        return None, proc.stderr.decode("utf-8", "replace").strip()[:200]
    return proc.stdout.decode("utf-8"), ""


def run_hop_proof(w: World) -> None:
    pp = load_module(af.HOOKS_DIR / "_project_paths.py", "project_paths_hop_proof")
    check("Q-hop: _project_paths.py declares TREE_HOP_REFUSAL = True", getattr(pp, "TREE_HOP_REFUSAL", None) is True,
          "TREE_HOP_REFUSAL is %r" % (getattr(pp, "TREE_HOP_REFUSAL", "missing"),))
    import inspect
    source = inspect.getsource(pp._git_file_kind).lower() if hasattr(pp, "_git_file_kind") else ""
    check("Q-hop: _git_file_kind carries the probe-order comment above the commondir hop (realpath only after the text "
          "checks, isdir last)", "probe order" in source and "realpath" in source and "isdir" in source,
          "no 'probe order' comment naming realpath and isdir in _git_file_kind")
    bridge_now = load_module(SCRIPTS_DIR / "_claude_paths.py", "claude_paths_hop_proof")
    check("Q-hop: the bridge beside the current helper exports TREE_HOP_REFUSAL True and no WORKTREE_OWN_ROOT_NATIVE",
          getattr(bridge_now, "TREE_HOP_REFUSAL", None) is True and not hasattr(bridge_now, "WORKTREE_OWN_ROOT_NATIVE"),
          "TREE_HOP_REFUSAL=%r, WORKTREE_OWN_ROOT_NATIVE present=%s"
          % (getattr(bridge_now, "TREE_HOP_REFUSAL", "missing"), hasattr(bridge_now, "WORKTREE_OWN_ROOT_NATIVE")))
    guard_now = load_module(w.guard, "codegraph_first_guard_hop_now")
    check("Q-hop [current helper]: the guard binds tree_kind and main_checkout_root",
          getattr(guard_now, "_pp_tree_kind", None) is not None and getattr(guard_now, "_pp_main_checkout_root", None) is not None,
          "tree_kind %r, main_checkout_root %r" % (getattr(guard_now, "_pp_tree_kind", None),
                                                 getattr(guard_now, "_pp_main_checkout_root", None)))
    fi = load_installer()
    rows = [("0.15.2 helper (e4f392c)", "e4f392c", True), ("older helper (643b667)", "643b667", False)]
    for label, commit, bound in rows:
        text, why = helper_text_at(commit)
        if text is None:
            skip(f"Q-hop [{label}]", "%s: %s" % (commit, why))
            print("        " + why)
            continue
        with af.Sandbox("cgqh-") as sb:
            folder = sb.root / "helper" / "hooks"
            folder.mkdir(parents=True)
            (folder / "_project_paths.py").write_text(text, encoding="utf-8")
            shutil.copyfile(af.HOOKS_DIR / "_error_log.py", folder / "_error_log.py")
            shutil.copyfile(w.guard, folder / HOOK_FILE)
            scripts = sb.root / "helper" / "scripts"
            scripts.mkdir()
            shutil.copyfile(SCRIPTS_DIR / "_claude_paths.py", scripts / "_claude_paths.py")
            with helper_folder_first(folder):
                old_guard = load_module(folder / HOOK_FILE, "codegraph_guard_hop_" + commit)
                try:
                    bridge = load_module(scripts / "_claude_paths.py", "claude_paths_hop_" + commit)
                except Exception as exc:  # noqa: BLE001
                    bridge = None
                    check(f"Q-hop [{label}]: the bridge imports beside that helper", False, repr(exc))
            is_bound = getattr(old_guard, "_pp_tree_kind", None) is not None \
                and getattr(old_guard, "_pp_main_checkout_root", None) is not None
            check(f"Q-hop [{label}]: the guard {'binds' if bound else 'does not bind'} tree_kind and main_checkout_root",
                  is_bound is bound, "bound=%s" % is_bound)
            info = af.make_linked_worktree(sb.root / "lw", layout="inside", gitdir_form="absolute")
            af.plant_index(info["main"])
            af.plant_server(info["main"])
            af.plant_server(info["worktree"])
            cwd = info["worktree"] / "src" / "deep"
            proc = run_hook(folder / HOOK_FILE, sb, info["worktree"], "Read", read_cs(info["worktree"]), sid(), cwd=cwd)
            if bound:
                check(f"Q-hop [{label}]: in a linked worktree with no index of its own the guard gives index-other-tree",
                      allowed(proc, "fail-open:index-other-tree"), describe(proc))
            else:
                check(f"Q-hop [{label}]: the same worktree keeps the gate (BLOCKED, the helper cannot be trusted)",
                      blocked(proc), describe(proc))
            if bridge is not None:
                check(f"Q-hop [{label}]: the bridge's TREE_HOP_REFUSAL is {bound}",
                      getattr(bridge, "TREE_HOP_REFUSAL", None) is bound and not hasattr(bridge, "WORKTREE_OWN_ROOT_NATIVE"),
                      "TREE_HOP_REFUSAL=%r" % (getattr(bridge, "TREE_HOP_REFUSAL", "missing"),))
                with mock.patch.object(fi, "_launcher_api", lambda: bridge):
                    notes = fi._codegraph_index_notes(info["worktree"])
                if bound:
                    check(f"Q-hop [{label}]: the installer decides the tree (no undecidable note)",
                          notes != [fi.UNDECIDABLE_TREE_NOTE], "notes %r" % (notes,))
                else:
                    check(f"Q-hop [{label}]: the installer says the tree is undecidable (one plain note)",
                          notes == [fi.UNDECIDABLE_TREE_NOTE], "notes %r" % (notes,))


# --------------------------------------------------------------------------------------------------------------
REVIEW_BANNER_BOTH = "`source-target` or `ambiguous-target`"


def folded(text: str) -> str:
    return re.sub(r"\s+", " ", text)


# ---- review fix round S-M1 (recorded row): what a REAL mapped drive resolves to --------------------------------------------
def run_recorded_mapped_drive(w: World) -> None:
    """Records (does not assert) what os.path.realpath answers for a real mapped network drive on this machine. Skips with a
    printed reason when the OS is not Windows or no drive of type DRIVE_REMOTE exists. It touches no network host by itself:
    GetDriveTypeW reads the local drive table, and realpath of a drive root runs in a thread with a 10 second limit."""
    if os.name != "nt":
        skip("S-M1 [recorded]: realpath of a mapped network drive", "not Windows: there are no mapped drives")
        return
    import ctypes
    import threading
    remote = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        try:
            if ctypes.windll.kernel32.GetDriveTypeW(letter + ":\\") == 4:
                remote.append(letter)
        except Exception:  # noqa: BLE001
            break
    if not remote:
        skip("S-M1 [recorded]: realpath of a mapped network drive", "no drive of type DRIVE_REMOTE on this machine (net use is empty)")
        return
    for letter in remote:
        answer: list = []
        worker = threading.Thread(target=lambda: answer.append(os.path.realpath(letter + ":\\")), daemon=True)
        worker.start()
        worker.join(10)
        print("        recorded: os.path.realpath(%r) -> %r" % (letter + ":\\", answer[0] if answer else "<no answer in 10 s>"))
        check("S-M1 [recorded]: a mapped drive %s: was found and its realpath recorded (not asserted)" % letter, True)


# ---- review pass 2 (round 3): the no-I/O verdicts come BEFORE any realpath --------------------------------------------------
_DRIVE_RE = re.compile(r"^(?:[\\/]{2}[?.][\\/])?([A-Za-z]):")


def call_base_with_seams(fn, raw: str, drive_types: dict, realpath_raises_on) -> tuple:
    """session_parent_base(env, "nt") with BOTH I/O seams faked and recorded. ``drive_types`` maps a drive letter to its
    GetDriveTypeW answer (default 3, fixed). ``realpath_raises_on(text)`` says when the fake realpath must RAISE (a slow or
    network call): the text is recorded first, so a swallowed exception is still seen. Seams: ``os.path.realpath`` and
    ``ctypes.windll.kernel32.GetDriveTypeW``. Returns (answer, realpath calls, drive calls)."""
    rp_calls: list = []
    dr_calls: list = []

    def fake_realpath(p, *a, **k):
        text = os.fspath(p)
        rp_calls.append(text)
        if realpath_raises_on(text):
            raise AssertionError("realpath was called on %r: that is the slow / network call this row forbids" % text)
        return text

    def fake_drive_type(root):
        dr_calls.append(str(root))
        match = _DRIVE_RE.match(str(root))
        return drive_types.get(match.group(1).upper(), 3) if match else 3
    windll = types.SimpleNamespace(kernel32=types.SimpleNamespace(GetDriveTypeW=fake_drive_type))
    try:
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": "C:\\decoy-from-os-environ"}), \
                mock.patch("os.path.realpath", fake_realpath), mock.patch("ctypes.windll", windll, create=True):
            got = tuple(fn({"LOCALAPPDATA": raw}, "nt"))
    except Exception as exc:  # noqa: BLE001
        got = ("raised %r" % (exc,), None)
    return got, rp_calls, dr_calls


def run_remote_before_realpath(w: World) -> None:
    """M1 (security pass 2) and F1 (code review pass 2): a base that the local tables or the text already prove remote is
    refused WITHOUT a realpath call (a disconnected mapped drive costs 21 s per call, a \\??\\UNC base opens an SMB session)."""
    answers: dict = {}
    z_text = lambda text: bool(re.match(r"^(?:[\\/]{2}[?.][\\/]+)?Z:", text, re.I)) or "??" in text  # noqa: E731
    any_text = lambda text: True  # noqa: E731
    for name, path in (("guard", w.guard),):
        fn = getattr(load_module(path, "codegraph_pre_" + name), "session_parent_base", None)
        if fn is None:
            check(f"Q-pre [{name}]: defines session_parent_base", False, "missing")
            continue
        # -- the NT prefix: refused from the text alone, realpath never called (it would open \\h\s before the verdict) --
        for raw in ("\\??\\UNC\\host-271.invalid\\s", "\\??\\unc\\host-271.invalid\\s", "\\??\\Z:\\x", "\\??\\C:\\Windows"):
            got, rp, dr = call_base_with_seams(fn, raw, {"Z": 4}, any_text)
            answers.setdefault("nt-prefix " + raw, {})[name] = (got, rp)
            check(f"Q-pre [{name}] {raw}: judged remote", got == (None, "remote"), "got %r" % (got,))
            check(f"Q-pre [{name}] {raw}: and realpath is NEVER called on it", rp == [], "realpath calls: %r" % rp)
        # -- the drive table first: a remote / unknown / no-root drive is refused with realpath never called --
        for raw in ("Z:\\x", "\\\\?\\Z:\\x", "\\\\.\\Z:\\x", "z:\\x"):
            for kind, kind_name in ((4, "DRIVE_REMOTE"), (0, "DRIVE_UNKNOWN"), (1, "DRIVE_NO_ROOT_DIR")):
                got, rp, dr = call_base_with_seams(fn, raw, {"Z": kind}, z_text)
                answers.setdefault("drive %s %s" % (raw, kind), {})[name] = (got, rp)
                check(f"Q-pre [{name}] {raw} with GetDriveTypeW={kind} ({kind_name}): judged remote",
                      got == (None, "remote"), "got %r" % (got,))
                check(f"Q-pre [{name}] {raw} with GetDriveTypeW={kind} ({kind_name}): and realpath is NEVER called (no slow "
                      "call before the verdict)", rp == [], "realpath calls: %r" % rp)
        # -- doubled separator after the device prefix on a REMOTE drive: also no realpath --
        for raw in ("\\\\.\\\\Z:\\x", "\\\\?\\\\Z:\\x", "//.//Z:/x", "\\\\.\\/Z:\\x"):
            got, rp, dr = call_base_with_seams(fn, raw, {"Z": 4}, z_text)
            check(f"Q-pre [{name}] {raw} with GetDriveTypeW=4: judged remote and realpath never called",
                  got == (None, "remote") and rp == [], "got %r, realpath calls %r" % (got, rp))
        # -- controls: a local drive proceeds (realpath is allowed to run) --
        for kind, kind_name in ((3, "DRIVE_FIXED"), (2, "DRIVE_REMOVABLE"), (6, "DRIVE_RAMDISK")):
            for raw in ("Z:\\x", "\\\\?\\Z:\\x", "\\\\.\\Z:\\x"):
                got, rp, dr = call_base_with_seams(fn, raw, {"Z": kind}, lambda text: False)
                check(f"Q-pre [{name}] [control] {raw} with GetDriveTypeW={kind} ({kind_name}): proceeds, local",
                      got == (raw, None), "got %r" % (got,))
        for raw in ("C:\\x", "\\\\?\\C:\\x", "\\\\.\\C:\\x"):
            got, rp, dr = call_base_with_seams(fn, raw, {"C": 3, "Z": 4}, lambda text: False)
            check(f"Q-pre [{name}] [control] {raw} on a fixed C: while Z: is remote: stays local (realpath allowed)",
                  got == (raw, None), "got %r" % (got,))

        # -- review pass 3 (round 4) M1/L1: a rooted base without a drive, or a non-letter drive designator, is judged from
        # the text: not-absolute, and realpath (which would resolve it against the cwd's drive) is never called --
        for raw in ("\\x", "/x/y", "\\AppData\\Local", "/AppData/Local", "1:\\x", " :\\x", ".:\\x"):
            got, rp, dr = call_base_with_seams(fn, raw, {"Z": 4}, any_text)
            answers.setdefault("no-drive " + raw, {})[name] = (got, rp)
            check(f"Q-pre [{name}] {raw!r}: judged not-absolute", got == (None, "not-absolute"), "got %r" % (got,))
            check(f"Q-pre [{name}] {raw!r}: and realpath is NEVER called on it (it would resolve against the cwd's drive)",
                  rp == [], "realpath calls: %r" % rp)
        # -- review pass 3 (round 4) L2: '//' or '\\' text that is not exactly the \\?\ or \\.\ device prefix is remote --
        for raw in ("\\\\\\?\\Z:\\x", "\\\\\\.\\Z:\\x", "\\\\?z:\\x", "//?z:/x", "\\/\\?\\C:\\x", "////?/C:/x", "\\\\\\\\?\\C:\\x"):
            got, rp, dr = call_base_with_seams(fn, raw, {"Z": 3}, any_text)
            answers.setdefault("leading-sep " + raw, {})[name] = (got, rp)
            check(f"Q-pre [{name}] {raw!r}: judged remote", got == (None, "remote"), "got %r" % (got,))
            check(f"Q-pre [{name}] {raw!r}: and realpath is NEVER called on it", rp == [], "realpath calls: %r" % rp)
        for raw in ("\\\\?\\C:\\x", "\\\\.\\C:\\x", "//?/C:/x", "//./C:/x"):
            got, rp, dr = call_base_with_seams(fn, raw, {"C": 3, "Z": 4}, lambda text: False)
            check(f"Q-pre [{name}] [control] {raw!r}: exactly the device prefix on C: stays local",
                  got == (raw, None), "got %r" % (got,))
        # -- review pass 3 (round 4) L4: only DRIVE_REMOVABLE (2), DRIVE_FIXED (3) and DRIVE_RAMDISK (6) proceed --
        for kind, kind_name in ((5, "DRIVE_CDROM"), (7, "undefined 7"), (99, "undefined 99"), (-1, "negative")):
            for raw in ("Z:\\x", "\\\\?\\Z:\\x"):
                got, rp, dr = call_base_with_seams(fn, raw, {"Z": kind}, z_text)
                answers.setdefault("drive-allowlist %s %s" % (raw, kind), {})[name] = (got, rp)
                check(f"Q-pre [{name}] {raw} with GetDriveTypeW={kind} ({kind_name}): judged remote (allow-list 2, 3, 6)",
                      got == (None, "remote"), "got %r" % (got,))
                check(f"Q-pre [{name}] {raw} with GetDriveTypeW={kind} ({kind_name}): and realpath is NEVER called",
                      rp == [], "realpath calls: %r" % rp)

        # -- an undecidable drive table is refused as ``check-failed`` (a true diagnosis), never as ``remote``, never allowed --
        def broken(root):
            raise OSError("no kernel32 271-marker")
        windll_broken = types.SimpleNamespace(kernel32=types.SimpleNamespace(GetDriveTypeW=broken))
        for how, patches in (("GetDriveTypeW raises", {"ctypes.windll": windll_broken}), ("ctypes cannot be imported", None)):
            try:
                if patches is not None:
                    with mock.patch("os.path.realpath", lambda p, *a, **k: os.fspath(p)), \
                            mock.patch("ctypes.windll", windll_broken, create=True):
                        got = tuple(fn({"LOCALAPPDATA": "Z:\\x"}, "nt"))
                else:
                    with mock.patch("os.path.realpath", lambda p, *a, **k: os.fspath(p)), \
                            mock.patch.dict(sys.modules, {"ctypes": None}):
                        got = tuple(fn({"LOCALAPPDATA": "Z:\\x"}, "nt"))
            except Exception as exc:  # noqa: BLE001
                got = ("raised %r" % (exc,), None)
            answers.setdefault("undecidable " + how, {})[name] = (got, [])
            check(f"Q-pre [{name}]: {how} gives check-failed (undecidable is refused, and not called a network path)",
                  len(got) in (2, 3) and got[0] is None and got[1] == "check-failed",
                  "got %r (a 2-tuple, or a 3-tuple whose third item is the exception text)" % (got,))
        # the exception text reaches resolve_session_parent's detail (the banner and the log carry it)
        resolver = getattr(load_module(path, "codegraph_pre_resolve_" + name), "resolve_session_parent", None)
        if os.name != "nt" or resolver is None:
            skip(f"Q-pre [{name}]: check-failed detail from a failing GetDriveTypeW", "needs Windows os.name and resolve_session_parent")
        else:
            try:
                with mock.patch.dict(os.environ, {"LOCALAPPDATA": "Z:\\x"}), \
                        mock.patch("os.path.realpath", lambda p, *a, **k: os.fspath(p)), \
                        mock.patch("ctypes.windll", windll_broken, create=True):
                    resolved = tuple(resolver())
            except Exception as exc:  # noqa: BLE001
                resolved = ("raised %r" % (exc,), None, "")
            check(f"Q-pre [{name}]: resolve_session_parent reports check-failed with the exception text as its detail",
                  len(resolved) == 3 and resolved[1] == "check-failed" and "no kernel32 271-marker" in str(resolved[2]),
                  "got %r" % (resolved,))
    for label, per_hook in answers.items():
        if len(per_hook) == 3:
            check(f"Q-pre parity: the three hooks answer alike on [{label}]",
                  len({repr(v) for v in per_hook.values()}) == 1, repr(per_hook))


# ---- review pass 2 (round 3): block() builds its message inside its try; a non-string tool_input field cannot allow ---------
def run_block_non_string_fields(w: World) -> None:
    with af.Sandbox("cgqns-") as sb:
        project = project_of(sb, "nonstr")
        make_logs(project)
        src = project / "src"
        ctrl = run_hook(w.guard, sb, project, "Read", {"file_path": str(src / "Thing.cs")}, sid())
        check("S-L1 [control]: an ordinary Read of source blocks (exit 2)", blocked(ctrl), describe(ctrl))
        rows = (
            ("a Read with a numeric file_path and a string path", "Read", {"file_path": 1, "path": str(src / "Thing.cs")}),
            ("a Read with a list file_path and a string path", "Read", {"file_path": ["x"], "path": str(src / "Thing.cs")}),
            ("a Read with a numeric filePath and a string path", "Read", {"filePath": 7, "path": str(src / "Thing.cs")}),
            ("a Grep with a numeric pattern", "Grep", {"pattern": 5, "path": str(src), "glob": "*.cs"}),
            ("a Grep with a list pattern", "Grep", {"pattern": ["a"], "path": str(src), "glob": "*.cs"}),
            ("a Glob with a numeric pattern and a source path", "Glob", {"pattern": 5, "path": str(src / "Thing.cs")}),
        )
        for index, (label, tool, tool_input) in enumerate(rows):
            proj = project_of(sb, "nonstr-%d" % index)
            make_logs(proj)
            proc = run_hook(w.guard, sb, proj, tool, tool_input, sid())
            check(f"S-L1 [{label}]: the guard still BLOCKS (exit 2), never the catch-all allow",
                  blocked(proc) and "internal error" not in proc.stderr, describe(proc))
            check(f"S-L1 [{label}]: and the block is logged", len(events(proj, "block")) == 1, repr(events(proj, "block")))
        # the same verdict with string values only (the message builder is the only difference)
        for index, (label, tool, tool_input) in enumerate(rows):
            if tool == "Read":
                strings = {"file_path": str(src / "Thing.cs")}
            elif tool == "Grep":
                strings = {"pattern": "plain", "path": str(src), "glob": "*.cs"}
            else:
                strings = {"pattern": "**/*.cs", "path": str(src / "Thing.cs")}
            proj = project_of(sb, "nonstr-ok-%d" % index)
            make_logs(proj)
            proc = run_hook(w.guard, sb, proj, tool, strings, sid())
            check(f"S-L1 [control, {tool} with string values only]: blocks, so the verdict is not what the non-string field "
                  "changed", blocked(proc), describe(proc))


# ---- review fix round S-M2: a lone surrogate in the banner text must not turn the block into an allow ----------------------
def run_block_survives_surrogates(w: World) -> None:
    with af.Sandbox("cgqsur-") as sb:
        project = project_of(sb, "sur")
        make_logs(project)
        src = project / "src"
        ctrl = run_hook(w.guard, sb, project, "Grep", {"pattern": "plain", "path": str(src), "glob": "*.cs"}, sid())
        check("S-M2 [control]: an ordinary Grep pattern blocks as source-target (exit 2)", blocked(ctrl), describe(ctrl))
        for label, tool, tool_input in (
                ("a Grep pattern holding a lone surrogate", "Grep", {"pattern": "a\ud800b", "path": str(src), "glob": "*.cs"}),
                ("a Glob pattern holding a lone surrogate", "Glob", {"pattern": "**/\udc80*.cs", "path": str(src)}),
                ("a Read file name holding a lone surrogate", "Read", {"file_path": str(src / "Th\ud800ing.cs")})):
            proj = project_of(sb, "sur-" + tool)
            make_logs(proj)
            proc = run_hook(w.guard, sb, proj, tool, tool_input, sid())
            check(f"S-M2 [{label}]: the guard still BLOCKS (exit 2), never the catch-all allow",
                  blocked(proc) and "internal error" not in proc.stderr, describe(proc))
            check(f"S-M2 [{label}]: and the block is still logged", len(events(proj, "block")) == 1, repr(events(proj, "block")))
        # the environment route: LOCALAPPDATA / XDG_CACHE_HOME holding a lone surrogate -> session-state-unusable, exit 2
        missing = sb.home / "missing-a" / "missing-b" / ("Local" if os.name == "nt" else ".cache")
        variable = "LOCALAPPDATA" if os.name == "nt" else "XDG_CACHE_HOME"
        proj = project_of(sb, "sur-env")
        make_logs(proj)
        try:
            proc = run_hook(w.guard, sb, proj, "Read", read_cs(proj), sid(), extra_env={variable: str(missing) + "\udc80"})
        except (ValueError, UnicodeError, OSError) as exc:
            skip("S-M2 [%s holding a lone surrogate]" % variable, "this OS cannot pass such an environment value: %r" % (exc,))
        else:
            check(f"S-M2 [{variable} holding a lone surrogate]: the guard BLOCKS (exit 2) with session-state-unusable, not the "
                  "catch-all allow", blocked(proc) and "internal error" not in proc.stderr
                  and len(unusable_records(proj)) == 1, describe(proc) + " / " + repr(events(proj, "block")))
        # the same shape without a surrogate is the control for the environment route
        proc = run_hook(w.guard, sb, proj, "Read", read_cs(proj), sid(), extra_env={variable: str(missing)})
        check(f"S-M2 [control]: {variable} at the same missing folder, no surrogate, blocks with (cannot-create)",
              blocked(proc) and "(cannot-create)" in proc.stderr, describe(proc))


# ---- review fix round T-H1 / T-H2: the owner, mode, writable and session-level verdicts, on every OS -----------------------
def run_verdict_matrix(w: World) -> None:
    import stat as stat_module
    uid = 4242
    own_dir_mode = stat_module.S_IFDIR | 0o700
    open_dir_mode = stat_module.S_IFDIR | 0o755
    # (label, parent override, session override, parent unwritable, session unwritable, expected token)
    rows = [("parent owned by another user", {"st_uid": uid + 1, "st_mode": own_dir_mode}, None, False, False, "foreign-owner"),
            ("parent open to other users (mode 0755)", {"st_uid": uid, "st_mode": open_dir_mode}, None, False, False, "open-mode"),
            ("parent not writable", {"st_uid": uid, "st_mode": own_dir_mode}, None, True, False, "unwritable"),
            ("Session folder owned by another user", {"st_uid": uid, "st_mode": own_dir_mode},
             {"st_uid": uid + 1, "st_mode": own_dir_mode}, False, False, "session-foreign-owner"),
            ("Session folder not writable", {"st_uid": uid, "st_mode": own_dir_mode},
             {"st_uid": uid, "st_mode": own_dir_mode}, False, True, "session-unwritable"),
            (None, {"st_uid": uid, "st_mode": own_dir_mode}, {"st_uid": uid, "st_mode": own_dir_mode}, False, False, None)]
    guard_mod = load_module(w.guard, "codegraph_first_guard_matrix")
    for label, parent_patch, session_patch, parent_denied, session_denied, token in rows:
        with af.Sandbox("cgqmx-") as sb:
            project = project_of(sb, "mx")
            make_logs(project)
            parent = af.session_parent(sb.home)
            session = sid()
            folder = pfolder(sb, session)
            os.mkdir(str(folder), 0o700)
            over = {parent: parent_patch}
            if session_patch is not None:
                over[folder] = session_patch
            denied = tuple(p for p, flag in ((parent, parent_denied), (folder, session_denied)) if flag)
            env = af.isolated_env(sb.home, sb.tmp, project)
            code, err = run_inproc(guard_mod, guard_payload(project, session), env, stat_over=over, no_access=denied, fake_uid=uid)
            if token is None:
                check("T-H1 [control]: with a faked uid and every owner, mode and access fact fine, the guard blocks as "
                      "source-target (no session-state-unusable)", code == 2 and "BLOCKED" in err
                      and "session-state-unusable" not in err and unusable_records(project) == [], "exit=%s %r" % (code, err[-400:]))
                continue
            check(f"T-H1 [{label}]: the guard BLOCKS fail-closed (exit 2) with (%s) in the message and a retry-free banner" % token,
                  code == 2 and "BLOCKED" in err and ("(%s)" % token) in err and "repeat this exact call" not in err,
                  "exit=%s %r" % (code, err[-500:]))
            check(f"T-H1 [{label}]: and the log record's problem field is exactly {token}",
                  unusable_records(project) == [token], repr(events(project, "block")))
            check(f"T-H1 [{label}]: and no turn.json was written (nothing writes one any more)", not (folder / "turn.json").exists())
    # T-H2: the Session folder alone fails to be checked -> session-check-failed, distinct from the parent-level check-failed
    with af.Sandbox("cgqsf-") as sb:
        project = project_of(sb, "sf")
        make_logs(project)
        af.session_parent(sb.home)
        session = sid()
        env = af.isolated_env(sb.home, sb.tmp, project)
        code, err = run_inproc(load_module(w.guard, "codegraph_first_guard_sessionfailed"), guard_payload(project, session), env,
                               lstat_for=pfolder(sb, session))
        check("T-H2: os.lstat raising ValueError for the SESSION folder only: the guard BLOCKS (exit 2), not the I-4 allow",
              code == 2 and "BLOCKED" in err and "internal error" not in err, "exit=%s %r" % (code, err[-500:]))
        check("T-H2: the message says (session-check-failed) and names ValueError, and never the parent-level (check-failed)",
              "(session-check-failed)" in err and "ValueError" in err and "(check-failed)" not in err, err[-500:])
        check("T-H2: and the record's problem field is exactly session-check-failed",
              unusable_records(project) == ["session-check-failed"], repr(events(project, "block")))
        check("T-H2: and no marker or ticket was written", not (pfolder(sb, session)).exists(), "folder exists")
        noidx = project_of(sb, "sf-noidx", index=False)
        make_logs(noidx)
        env2 = af.isolated_env(sb.home, sb.tmp, noidx)
        code, err = run_inproc(load_module(w.guard, "codegraph_first_guard_sessionfailed2"), guard_payload(noidx, session), env2,
                               lstat_for=pfolder(sb, session))
        check("T-H2 [control]: the same fence with no index still allows (fail-open:no-index)",
              code == 0 and "fail-open:no-index" in err, "exit=%s %r" % (code, err[-300:]))
        check("T-H2 [isolation]: no in-process run wrote to the real errors.jsonl", INPROC_LEAKS == [], repr(INPROC_LEAKS))


# ---- review fix round T-M1: the cannot-create boundary ---------------------------------------------------------------------
def run_base_boundaries(w: World) -> None:
    import stat as stat_module
    if os.name == "nt":
        with af.Sandbox("cgqbb-") as sb:
            (sb.home / "AppData").mkdir(exist_ok=True)
            base = sb.home / "AppData" / "LocalMissing"  # its own parent exists; the base itself does not
            project = project_of(sb, "bb")
            make_logs(project)
            proc = run_hook(w.guard, sb, project, "Read", read_cs(project), sid(), extra_env={"LOCALAPPDATA": str(base)})
            check("T-M1: Windows, a base that is missing while ITS parent exists is never created: the guard blocks "
                  "(cannot-create)", blocked(proc) and names_problem(proc.stderr, project, "cannot-create"), describe(proc))
            check("T-M1: and the base folder is still absent afterwards", not base.exists(), "the base was created: %s" % base)
        skip("T-M1: POSIX creates the base exactly one level, mode 0700", "Windows: the base is never created")
        return
    skip("T-M1: Windows never creates a missing base", "POSIX: the base is created one level")
    with af.Sandbox("cgqbb-") as sb:
        base = sb.home / "onelevel-cache"
        project = project_of(sb, "bb")
        make_logs(project)
        proc = run_hook(w.guard, sb, project, "Read", read_cs(project), sid(), extra_env={"XDG_CACHE_HOME": str(base)})
        check("T-M1: POSIX, a base missing while its parent exists is created (one level) and the state is usable",
              base.is_dir() and blocked(proc) and "session-state-unusable" not in proc.stderr, describe(proc))
        check("T-M1: and the base and the Per-user session parent are mode 0700",
              stat_module.S_IMODE(base.stat().st_mode) == 0o700
              and stat_module.S_IMODE((base / "auto-improve-codegraph").stat().st_mode) == 0o700, "modes differ")


# ---- review fix round T-L1 (kept for the cli-fallback record, C-4): the flag only after the record landed ------------------------------
def run_foreign_marker_order(w: World) -> None:
    with af.Sandbox("cgqfo-") as sb:
        parent = af.session_parent(sb.home)
        guard_mod = load_module(w.guard, "codegraph_first_guard_fallback_order")
        for label, returns, flag_expected in (("the record is written", True, True), ("the record could not be written", False, False)):
            project = project_of(sb, "fo-%s" % returns)
            make_logs(project)
            session = sid()
            transcript = fresh_transcript(sb, [af.t_human(1), af.t_bash_use("codegraph explore Thing")])
            flag = af.session_folder(parent, session) / "logged-cli-fallback"
            seen: list = []

            def spy(**kwargs):
                seen.append((kwargs.get("event"), flag.exists()))
                return returns
            env = af.isolated_env(sb.home, sb.tmp, project)
            with mock.patch.object(guard_mod, "log_event", spy):
                code, err = run_inproc(guard_mod, guard_payload(project, session, transcript_path=str(transcript)), env)
            check(f"T-L1 [{label}]: the gate is open (exit 0) with no stderr line", code == 0 and "allowed (" not in err, "exit=%s %r" % (code, err))
            check(f"T-L1 [{label}]: the cli-fallback record is written while the flag does NOT exist yet",
                  seen == [("cli-fallback", False)], repr(seen))
            check(f"T-L1 [{label}]: and the flag exists afterwards only when the record did not fail", flag.exists() is flag_expected,
                  "flag exists=%s" % flag.exists())
            if flag_expected:
                with mock.patch.object(guard_mod, "log_event", spy):
                    code, err = run_inproc(guard_mod, guard_payload(project, session, transcript_path=str(transcript)), env)
                check("T-L1: the second call writes no second record", code == 0 and len(seen) == 1, "exit=%s %r seen=%r" % (code, err, seen))
            else:
                with mock.patch.object(guard_mod, "log_event", spy):
                    run_inproc(guard_mod, guard_payload(project, session, transcript_path=str(transcript)), env)
                check("T-L1: a record that failed is tried again on the next call", len(seen) == 2, repr(seen))
        check("T-L1 [isolation]: no in-process run wrote to the real errors.jsonl", INPROC_LEAKS == [], repr(INPROC_LEAKS))


# ---- review fix round C-W1: the repeat after retry-ticket-unwritten may be ambiguous-target --------------------------------
def run_ambiguous_after_unwritten(w: World) -> None:
    with af.Sandbox("cgqaw-") as sb:
        project = project_of(sb, "aw")
        make_logs(project)
        guard_mod = load_module(w.guard, "codegraph_first_guard_ambiguous")
        session = sid()
        folder = pfolder(sb, session, True)
        folder.mkdir()
        # a Grep on a folder with no glob: the class is 'unknown' (a pattern-only Grep has no target at all and is allowed)
        tool_input = {"pattern": "Thing", "path": str(project / "src")}
        ticket = folder / ("ticket-" + guard_mod.call_fingerprint("Grep", tool_input))
        ticket.mkdir()
        first = run_hook(w.guard, sb, project, "Grep", tool_input, session)
        check("C-W1: an unknown-class Grep (a folder, no glob) whose ticket cannot be written blocks as retry-ticket-unwritten",
              blocked(first) and parent_problem_events(project, "retry-ticket-unwritten") != [], describe(first))
        check("C-W1: and its banner says the repeat blocks as `source-target` or `ambiguous-target`",
              REVIEW_BANNER_BOTH in folded(first.stderr), first.stderr[-700:])
        os.rmdir(str(ticket))
        again = run_hook(w.guard, sb, project, "Grep", tool_input, session)
        reasons = [(rec.get("details") or {}).get("reason") for rec in events(project, "block")]
        check("C-W1 [control]: once the write works again the repeat of the unknown-class Grep blocks as ambiguous-target, "
              "not source-target", blocked(again) and reasons[-1:] == ["ambiguous-target"], "reasons %r / %s" % (reasons, describe(again)))
        # and the same banner for a source Read, with its own session
        project2 = project_of(sb, "aw2")
        make_logs(project2)
        session2 = sid()
        folder2 = pfolder(sb, session2)
        folder2.mkdir()
        (folder2 / ("ticket-" + guard_mod.call_fingerprint("Read", read_cs(project2)))).mkdir()
        proc = run_hook(w.guard, sb, project2, "Read", read_cs(project2), session2)
        check("C-W1: the same two-reason sentence is in the banner for a source Read", blocked(proc)
              and REVIEW_BANNER_BOTH in folded(proc.stderr), proc.stderr[-700:])


# ---- review fix round S-L6: the bridge never binds worktree_own_root to None ----------------------------------------------
def run_bridge_without_own_root(w: World) -> None:
    helper_text = (af.HOOKS_DIR / "_project_paths.py").read_text(encoding="utf-8")
    for label, tail in (("the helper declares TREE_HOP_REFUSAL and has no worktree_own_root at all",
                         "\nTREE_HOP_REFUSAL = True\ndel worktree_own_root\n"),
                        ("the helper declares TREE_HOP_REFUSAL and worktree_own_root is not callable",
                         "\nTREE_HOP_REFUSAL = True\nworktree_own_root = None\n")):
        with af.Sandbox("cgqbr-") as sb:
            folder = sb.root / "helper" / "hooks"
            folder.mkdir(parents=True)
            (folder / "_project_paths.py").write_text(helper_text + tail, encoding="utf-8")
            shutil.copyfile(af.HOOKS_DIR / "_error_log.py", folder / "_error_log.py")
            scripts = sb.root / "helper" / "scripts"
            scripts.mkdir()
            shutil.copyfile(SCRIPTS_DIR / "_claude_paths.py", scripts / "_claude_paths.py")
            bridge = None
            with helper_folder_first(folder):
                try:
                    bridge = load_module(scripts / "_claude_paths.py", "claude_paths_no_own_root_%d" % len(label))
                except Exception as exc:  # noqa: BLE001
                    check(f"S-L6 [{label}]: the bridge imports beside that helper", False, repr(exc))
            if bridge is not None:
                check(f"S-L6 [{label}]: the bridge's worktree_own_root is callable (its inline copy), never None",
                      callable(getattr(bridge, "worktree_own_root", None)),
                      "worktree_own_root is %r" % (getattr(bridge, "worktree_own_root", "missing"),))


# ---- review fix round T-L3: the real-folder snapshot catches a created parent or a non-prefixed entry ----------------------
def run_real_parent_snapshot_selfcheck(w: World) -> None:
    snapshot = getattr(af, "real_parent_snapshot", None)
    if snapshot is None:
        check("T-L3: the fixture offers real_parent_snapshot()", False, "not defined")
        return
    with af.Sandbox("cgql3-") as sb:
        fake_parent = sb.root / "never-created" / "auto-improve-codegraph"
        with mock.patch.object(af, "REAL_PARENT", fake_parent):
            absent = snapshot()
            fake_parent.mkdir(parents=True)
            created = snapshot()
            (fake_parent / ".tmp-abc").write_text("x", encoding="utf-8")
            extra = snapshot()
        check("T-L3: the snapshot tells an absent parent from a newly created (empty) one", absent != created, "%r / %r" % (absent, created))
        check("T-L3: and sees a non-prefixed entry (.tmp-*) appear in an existing parent", created != extra, "%r / %r" % (created, extra))

# Issue #295 (contract 2026-11-07-295-codegraph-gate-dropped-mcp): the command-line route, the two-route banner, the
# connection probe and notice, the cli-fallback record, AC7/AC8, the bench's --reset-budget mode.
#
# The payload shapes are the LIVE TRIAL shapes (L1, L3, L7), not the contract's working rule:
#   * a successful Bash call arrives as event PostToolUse with tool_response {stdout, stderr, interrupted, isImage,
#     noOutputExpected} and NO exit-code field; a FAILED Bash call arrives as event PostToolUseFailure with `error`
#     ("Exit code N ...") and `is_interrupt`, and no tool_response. The success signal is the event name.
#   * a successful MCP call is a PostToolUse whose tool_response is a LIST of {type: text, text}; a hard-errored MCP
#     call is a PostToolUseFailure with `error`.
#   * the host's `if: "Bash(codegraph *)"` also fires for compound commands and VAR=val prefixes, so the TRACKER applies
#     its own strict token-0 test; those payloads are fed straight to it here.
# Names this suite pins (the implementer must provide them): reset hook module-level `connection_probe(table, start_pid)`
# -> "present" | "absent" | "undecidable" over a list of (pid, parent_pid, image, command line or None);
# `read_process_table()` -> that list (the ONLY thing tests replace, R-4); `notice_section(payload)` -> one of the closed
# outcomes, printing the notice JSON itself when it is "shown"; guard module-level `server_starts_process(path)` -> bool.
# --------------------------------------------------------------------------------------------------------------
BASH_OK_RESPONSE = {"stdout": "", "stderr": "", "interrupted": False, "isImage": False, "noOutputExpected": False}
MCP_EXPLORE = "mcp__codegraph__" + "codegraph_explore"
SENTENCE = "A project instruction or a skill's explicit gate that forbids shell commands wins over this notice; follow that rule instead."


# (the tracker-driven helpers bash_ok, bash_failed, mcp_ok, mcp_errored, marker_of, flag_exists and tracker_events were removed with the
# tracker: the guard counts a CodeGraph call from the transcript, so a row writes transcript lines instead, see af.t_*)


def shadow_records(project: Path) -> list[dict]:
    out = []
    try:
        lines = (project / ".claude" / "logs" / "codegraph-shadow.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


COUNTED_FORMS = [
    ("query", "codegraph query Thing"),
    ("explore", 'codegraph explore "how does X work"'),
    ("context", 'codegraph context "fix the login"'),
    ("node", "codegraph node Thing"),
    ("callers", "codegraph callers Thing"),
    ("callees", "codegraph callees Thing"),
    ("impact", "codegraph impact Thing"),
    ("files", "codegraph files src"),
    ("explore", "codegraph explore Thing 2>&1"),
]
NOT_COUNTED_FORMS = [
    "codegraph status", "codegraph init -i", "codegraph index", "codegraph sync", "codegraph serve --mcp",
    "codegraph daemon", "codegraph", "codegraph --version",
    "codegraph explore x; cat a.cs", "codegraph explore x | head", "codegraph explore x & ls",
    "codegraph explore $(whoami)", "codegraph explore `id`", "codegraph explore x > out.txt",
    "codegraph explore x 2>&1 2>&1", "codegraph explore x\ncat a.cs",
    "cd x && codegraph explore y", "ls && codegraph explore y", "npx codegraph explore y",
    "VAR=1 codegraph explore y", "codegraph.exe explore y", "codegraph.cmd explore y",
    "/c/bin/codegraph explore y", "C:\\x\\codegraph explore y", "./codegraph explore y", 'codegraph explore "unterminated',
]


def run_cli_route(w: World) -> None:
    """The command-line route is counted from the transcript (C-1): the strict Counted test moved verbatim from the tracker."""
    with af.Sandbox("cg295c-") as sb:
        project = project_of(sb, "cli")
        make_logs(project)
        H = af.t_human
        for sub, command in COUNTED_FORMS:
            session = sid()
            transcript = fresh_transcript(sb, [H(1)])
            before = cut(w, sb, project, None, session, path=transcript)
            check(f"CLI-1 [{command}]: control: a source Read is blocked before the call", blocked(before), describe(before))
            prefixed = cut(w, sb, project, [H(1), af.t_bash_use("FOO=1 " + command)])
            check(f"CLI-1 [{command}]: the same command behind a VAR=val prefix is NOT counted (the strict token-0 test)",
                  blocked(prefixed), describe(prefixed))
            append_lines(transcript, af.t_bash_use(command))
            after = cut(w, sb, project, None, session, path=transcript)
            check(f"CLI-1 [{command}]: after the Bash tool use the same Read is allowed by the TRANSCRIPT (no `allowed (` line)",
                  silent_allow(after), describe(after))
            recs = shadow_records(project)
            rec = recs[-1] if recs else {}
            check(f"CLI-1 [{command}]: the record names route cli", rec.get("turn_route") == "cli", repr(rec))
        for command in NOT_COUNTED_FORMS:
            proc = cut(w, sb, project, [H(1), af.t_bash_use(command)])
            check(f"CLI-2 [{command!r}]: leaves the turn closed (not a Counted command in the strict form)", blocked(proc), describe(proc))
        proc = cut(w, sb, project, [H(1), af.t_bash_use("codegraph explore Thing"), af.t_assistant({"type": "text", "text": "it failed"})])
        check("CLI-3: a Counted command counts when the main session ISSUES it, whether or not it succeeded (Q1: the transcript "
              "holds the tool use, not its outcome)", silent_allow(proc), describe(proc))
        proc = cut(w, sb, project, [H(1), af.t_bash_use("codegraph explore Thing", background=True)])
        check("CLI-4: a run_in_background call leaves the turn closed", blocked(proc), describe(proc))
        # a subagent's own Bash call is in another file: the main session's gate is opened by its dispatch (C-7), not by it
        proc = cut(w, sb, project, [H(1), af.t_agent_use()])
        check("CLI-5: a subagent dispatch opens the gate for the main session", silent_allow(proc), describe(proc))
        # no kill switch: the route works, and the gate still closes, with every plausible switch set (R-4)
        extra = {"CLAUDE_SKIP_CG": "1", "CODEGRAPH_OFF": "1", "CLAUDE_CODEGRAPH_ROUTE": "off"}
        opened = run_hook(w.guard, sb, project, "Read", read_cs(project), sid(), extra_env=extra,
                          transcript=fresh_transcript(sb, [H(1), af.t_bash_use("codegraph explore Thing")]))
        closed = run_hook(w.guard, sb, project, "Read", read_cs(project), sid(), extra_env=extra)
        check("CLI-6: no environment variable turns the command-line route or the gate off", silent_allow(opened) and blocked(closed),
              describe(opened) + " / " + describe(closed))


def run_marker_routes(w: World) -> None:
    """The route of a turn: mcp beats cli beats agent, whatever the order (C-1)."""
    with af.Sandbox("cg295r-") as sb:
        project = project_of(sb, "routes")
        make_logs(project)
        H, B, M, A = af.t_human, af.t_bash_use, af.t_mcp_use, af.t_agent_use
        cases = [
            ("cli then mcp -> mcp", [B("codegraph explore Thing"), M()], "mcp", True),
            ("mcp then cli -> mcp", [M(), B("codegraph explore Thing")], "mcp", True),
            ("cli alone -> cli", [B("codegraph explore Thing")], "cli", False),
            ("mcp alone -> mcp", [M()], "mcp", True),
            ("agent then cli -> cli", [A(), B("codegraph explore Thing")], "cli", False),
            ("cli then agent -> cli", [B("codegraph explore Thing"), A()], "cli", False),
            ("agent alone -> agent", [A()], "agent", False),
        ]
        for label, lines, route, seen in cases:
            session = sid()
            proc = cut(w, sb, project, [H(1)] + lines, session)
            rec = (shadow_records(project) or [{}])[-1]
            cursor = json.loads((pfolder(sb, session) / "transcript-cursor.json").read_text(encoding="utf-8"))
            check(f"RT-1 [{label}]: the record's route is {route}", rec.get("turn_route") == route, repr(rec))
            check(f"RT-1 [{label}]: the cursor's mcp_seen is {seen} (sticky: set only by an mcp use)", cursor.get("mcp_seen") is seen,
                  repr(cursor))
            check(f"RT-1 [{label}]: the gate is open (any route opens it)", silent_allow(proc), describe(proc))
        routes = {(shadow_records(project) or [{}])[-1].get("turn_route")}
        check("RT-2: route values are only mcp, cli and agent", {r for c in cases for r in (c[2],)} == {"mcp", "cli", "agent"}, repr(routes))
        # a tool_use of another tool, a failed text and a sidechain entry never set a route
        proc = cut(w, sb, project, [H(1), json.dumps({"type": "assistant", "isSidechain": True, "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t", "name": "mcp__codegraph__codegraph_explore", "input": {}}]}})])
        check("RT-3: a sidechain CodeGraph tool use (another file's entries) opens nothing", blocked(proc), describe(proc))


def run_cli_fallback_record(w: World) -> None:
    """The cli-fallback record moved from the tracker into the guard (C-4): at the turn's first guarded call."""
    with af.Sandbox("cg295f-") as sb:
        H, B, M = af.t_human, af.t_bash_use, af.t_mcp_use

        def fresh():
            project = project_of(sb, "r5-%s" % uuid.uuid4().hex[:6])
            make_logs(project)
            return project

        project, session = fresh(), sid()
        transcript = fresh_transcript(sb, [H(1), B("codegraph explore Thing")])
        cut(w, sb, project, None, session, path=transcript)
        got = events(project, "cli-fallback")
        check("R5-1: an accepted counted CLI turn with no mcp use writes exactly ONE cli-fallback record at the first guarded call",
              len(got) == 1, repr(events(project)))
        detail = got[0].get("details", {}) if got else {}
        check("R5-1: the record carries reason mcp-unavailable and the subcommand, nothing else of the command",
              detail.get("reason") == "mcp-unavailable" and detail.get("command") == "explore", repr(got))
        check("R5-1: and the logged-cli-fallback flag exists after the record landed", (pfolder(sb, session) / "logged-cli-fallback").exists())
        cut(w, sb, project, None, session, path=transcript)
        append_lines(transcript, H(2), B("codegraph impact Thing"))
        cut(w, sb, project, None, session, path=transcript)
        check("R5-2: a second guarded call, and a cli turn in a second prompt, add no further record",
              len(events(project, "cli-fallback")) == 1, repr(events(project)))

        project, session = fresh(), sid()
        cut(w, sb, project, [H(1), M(), B("codegraph explore Thing")], session)
        check("R5-3: an mcp use before the CLI call: no record", len(events(project, "cli-fallback")) == 0, repr(events(project)))

        project, session = fresh(), sid()
        cut(w, sb, project, [H(1), B("codegraph status"), B("cd x && codegraph explore y"), B("codegraph explore Thing", background=True)], session)
        check("R5-5: an uncounted, a compound and a background call write no record", len(events(project, "cli-fallback")) == 0,
              repr(events(project)))
        cut(w, sb, project, [H(1), af.t_agent_use()], sid())
        check("R5-5b: an agent route writes no record either", len(events(project, "cli-fallback")) == 0, repr(events(project)))

        # log_event returns False (no logs folder): the flag is NOT set, and the next guarded call records
        project = project_of(sb, "r5-nolog")
        session = sid()
        transcript = fresh_transcript(sb, [H(1), B("codegraph explore Thing")])
        cut(w, sb, project, None, session, path=transcript)
        check("R5-6: when nothing could be logged (no logs folder) no logged-cli-fallback flag is set",
              not (pfolder(sb, session) / "logged-cli-fallback").exists())
        make_logs(project)
        cut(w, sb, project, None, session, path=transcript)
        check("R5-6: and once the log can be written the next guarded call records exactly once",
              len(events(project, "cli-fallback")) == 1 and (pfolder(sb, session) / "logged-cli-fallback").exists(),
              repr(events(project)))

        # the pruner knows mcp-seen and logged-cli-fallback
        reset = load_reset_module(sb, w)
        names = ("turn.json", "mcp-seen", "logged-cli-fallback", "pruned")
        check("R5-7: KEY: mcp-seen is a known name of the pruner", reset.KNOWN_FILE_RE.fullmatch("mcp-seen") is not None)
        check("R5-7: logged-cli-fallback is a known name", reset.KNOWN_FILE_RE.fullmatch("logged-cli-fallback") is not None)
        folder = old_session(af.session_parent(sb.home), "r5-old", files=names)
        removed = reset.prune_session_folders(af.session_parent(sb.home))
        check("R5-7: an old session folder holding mcp-seen and logged-cli-fallback is pruned whole",
              af.CODEGRAPH_SESSION_PREFIX + "r5-old" in removed and not folder.exists(), "removed %r; left %s" % (
                  removed, sorted(os.listdir(folder)) if folder.exists() else []))
        session = sid()
        project = fresh()
        cut(w, sb, project, [H(1), M()], session)
        run_hook(w.guard, sb, project, "", {}, session, event="UserPromptSubmit", payload_extra={"prompt": "again"}, argv=["notice"])
        check("R5-8: the next prompt row deletes nothing of this session's state (no turn.json, mcp-seen or cursor is removed)",
              (pfolder(sb, session) / "transcript-cursor.json").exists() and (pfolder(sb, session) / "pruned").exists())


def run_cli_ac2(w: World) -> None:
    with af.Sandbox("cg295a-") as sb:
        project = project_of(sb, "ac2-main")
        make_logs(project)
        proc = cut(w, sb, project, [af.t_human(1), af.t_bash_use("codegraph explore Thing")])
        recs = shadow_records(project)
        check("AC2 [main session]: no MCP call, index present, server configured, one counted CLI call: a source Read is allowed",
              allowed(proc) and "BLOCKED" not in proc.stderr, describe(proc))
        check("AC2 [main session]: with reason transcript-open and turn_route cli (the Measurement record)",
              bool(recs) and recs[-1].get("live_reason") == "transcript-open" and recs[-1].get("turn_route") == "cli",
              repr(recs[-1:]) + describe(proc))
        stranger = cut(w, sb, project, [af.t_human(1)])
        check("AC2 [main session]: another session with a closed transcript is still BLOCKED [control]", blocked(stranger), describe(stranger))
        sub = cut(w, sb, project, [af.t_human(1), af.t_bash_use("codegraph explore Thing")],
                  extra={"agent_id": "a1", "agent_type": "general-purpose"})
        check("AC2 [subagent (agent_id)]: a subagent's own Read is allowed at step 3 (its transcript is another file)",
              allowed(sub, "fail-open:subagent"), describe(sub))


def banner_term(stderr: str):
    found = re.findall(r'codegraph explore "([^"\n]*)"', stderr)
    return found[0] if len(found) == 1 else None


def run_banner(w: World) -> None:
    with af.Sandbox("cg295b-") as sb:
        project = project_of(sb, "banner")
        for label, tool, tool_input in calls(project)[::2]:
            proc = run_hook(w.guard, sb, project, tool, tool_input, sid())
            text = proc.stderr
            check(f"AC3 [{label}]: the banner still names the MCP route (mcp__codegraph__*)", blocked(proc) and "mcp__codegraph__*" in text, text)
            check(f"AC3 [{label}]: and holds exactly one copyable command: codegraph explore \"<term>\"",
                  blocked(proc) and banner_term(text) is not None, text)
            check(f"AC3 [{label}]: and names which index a worktree reads (the main checkout's, unless one was built there)",
                  re.search(r"worktree", text, re.I) is not None and re.search(r"main checkout", text, re.I) is not None, text)
            check(f"AC3 [{label}]: I-2 holds: no `cat`/`sed`, no 'through the shell', no individual tool name",
                  re.search(r"\b(cat|sed)\s", text) is None and "through the shell" not in text
                  and "mcp__codegraph__codegraph_" not in text and LEGACY_NAME_RE.search(text) is None, text)
        proc = run_hook(w.guard, sb, project, "Read", read_cs(project), sid())
        check("AC3: a Read of Thing.cs yields codegraph explore \"Thing\"", banner_term(proc.stderr) == "Thing", proc.stderr)
        hostile = [("foo; rm -rf /", "foo rm -rf"), ("$(whoami)", "whoami"), ("`id`", "id"), ("a|b", "a b"), ("a\nb", "a b"),
                   ("-x", "x"), ("--help", "help"), (".hidden", "hidden"), ("---", "Symbol"), ("!!!", "Symbol"),
                   ("A" * 200, "A" * 80)]
        for pattern, want in hostile:
            proc = run_hook(w.guard, sb, project, "Grep", {"pattern": pattern, "path": str(project / "src"), "glob": "*.cs"}, sid())
            term = banner_term(proc.stderr)
            tidy = " ".join(term.split()) if term is not None else None
            check(f"AC3 [Grep pattern {pattern[:12]!r}]: the term is neutralised to {want[:20]!r}: only [A-Za-z0-9_.- ], no leading - or ., "
                  "at most 80 characters",
                  blocked(proc) and term is not None and re.fullmatch(r"[A-Za-z0-9_. \-]+", term) is not None
                  and len(term) <= 80 and not term.lstrip().startswith(("-", ".")) and tidy == want,
                  "term=%r\n%s" % (term, proc.stderr))
        long_name = "B" * 200
        proc = run_hook(w.guard, sb, project, "Read", {"file_path": str(project / "src" / (long_name + ".cs"))}, sid())
        term = banner_term(proc.stderr)
        check("AC3 [Read of a 200-character file name]: the term is at most 80 characters",
              term is not None and 0 < len(term) <= 80, "term=%r" % term)


# ---- the connection probe over a synthetic process table --------------------------------------------------------
SERVER_CMD = 'C:\\WINDOWS\\system32\\cmd.exe /d /s /c "codegraph ^"serve^" ^"--mcp^""'
SERVER_NODE_1 = ('"C:\\Users\\u\\AppData\\Local\\codegraph\\current\\bin\\..\\node.exe" --liftoff-only '
                 '--disable-warning=ExperimentalWarning "C:\\Users\\u\\AppData\\Local\\codegraph\\current\\bin\\..\\lib\\dist\\bin\\codegraph.js" "serve" "--mcp"')
SERVER_NODE_2 = ('C:\\Users\\u\\AppData\\Local\\codegraph\\current\\node.exe --liftoff-only --disable-warning=ExperimentalWarning '
                 'C:\\Users\\u\\AppData\\Local\\codegraph\\current\\lib\\dist\\bin\\codegraph.js serve --mcp --path D:\\proj')


def host_chain(me: int, hops: int = 4, host: str = "claude.exe") -> tuple[list, int]:
    """Rows for the hook (pid ``me``, python) up to a host ``hops`` parents above it, and one process above the host.
    The processes between are bash.exe (the L4 shape for hops=4: python <- py <- bash <- bash <- claude)."""
    images = ["python.exe"] + (["py.exe"] if hops > 1 else []) + ["bash.exe"] * max(0, hops - 2)
    images = images[:hops]
    rows, pid = [], me
    for i, image in enumerate(images):
        parent = me + 1000 + i
        rows.append((pid, parent, image, "C:\\x\\%s fixture-%d" % (image, i)))
        pid = parent
    rows.append((pid, pid + 500, host, "C:\\Users\\u\\.local\\bin\\claude.exe -p"))
    rows.append((pid + 500, 1, "powershell.exe", "powershell.exe -NoProfile"))
    return rows, pid


def chain_to_host(me: int, depth_images: list, host: str = "claude.exe") -> tuple[list, int]:
    rows, pid = [], me
    for i, image in enumerate(depth_images):
        parent = me + 2000 + i
        rows.append((pid, parent, image, "C:\\x\\%s hop-%d" % (image, i)))
        pid = parent
    rows.append((pid, pid + 500, host, "C:\\Users\\u\\.local\\bin\\claude.exe"))
    return rows, pid


def real_servers(host_pid: int, which=("cmd", "n1", "n2")) -> list:
    rows = []
    if "cmd" in which:
        rows.append((host_pid + 11, host_pid, "cmd.exe", SERVER_CMD))
    if "n1" in which:
        rows.append((host_pid + 12, host_pid + 11 if "cmd" in which else host_pid, "node.exe", SERVER_NODE_1))
    if "n2" in which:
        rows.append((host_pid + 13, host_pid + 12 if "n1" in which else host_pid, "node.exe", SERVER_NODE_2))
    return rows


def fn_of(mod, name: str):
    return getattr(mod, name, None)


def run_probe_rows(w: World) -> None:
    with af.Sandbox("cg295p-") as sb:
        reset = load_reset_module(sb, w)
        probe = fn_of(reset, "connection_probe")
        check("PR-0: the guard defines connection_probe(table, start_pid)", callable(probe),
              "no module-level connection_probe in %s" % w.guard.name)
        if not callable(probe):
            return
        me = 5000

        def verdict(table, label, want):
            try:
                got = probe(table, me)
            except Exception as exc:  # noqa: BLE001
                got = "raised %r" % exc
            check(f"PR [{label}]: {want}", got == want, "got %r" % (got,))

        base, host_pid = host_chain(me, 4)
        verdict(base + real_servers(host_pid), "the real L4 table: cmd.exe + two node.exe, quotes and carets", "present")
        for which in (("cmd",), ("n1",), ("n2",)):
            verdict(base + real_servers(host_pid, which), "only %s of the three server processes" % which[0], "present")
        verdict(base, "host trusted, no server process", "absent")
        verdict(base + [(host_pid + 20, host_pid, "node.exe", "node.exe C:\\x\\codegraph\\dist\\bin\\codegraph.js daemon --root D:\\proj")],
                "a daemon only (no serve --mcp)", "absent")
        verdict(base + [(host_pid + 21, host_pid, "codegraph.exe", "codegraph serve")], "serve without --mcp", "absent")
        verdict(base + [(host_pid + 22, host_pid, "codegraph.exe", "codegraph serve --mcp")], "native 'codegraph serve --mcp'", "present")
        verdict(base + [(host_pid + 23, host_pid, "node.exe",
                         "node C:\\Users\\u\\AppData\\Roaming\\npm\\node_modules\\@x\\codegraph\\dist\\x.js serve --mcp")],
                "npm: node ...\\node_modules\\...\\codegraph\\dist\\x.js serve --mcp (a codegraph folder segment)", "present")
        verdict(base + [(host_pid + 24, host_pid, "node.exe", "node other.js serve --mcp")],
                "node other.js serve --mcp (no CodeGraph token)", "undecidable")
        verdict(base + [(host_pid + 25, host_pid, "node.exe", None)], "a candidate with an unreadable command line", "undecidable")
        verdict(base + [(host_pid + 25, host_pid, "node.exe", None)] + real_servers(host_pid, ("cmd",)),
                "an unreadable candidate beside a matching server: the match wins", "present")
        # the hook's own ancestor chain is never a candidate
        chain_rows = list(base)
        chain_rows[2] = (chain_rows[2][0], chain_rows[2][1], "bash.exe", 'bash -c "codegraph serve --mcp"')
        verdict(chain_rows, "the hook's own ancestor (a bash whose command line says codegraph serve --mcp) is not a server", "absent")
        # host image set: .exe stripped, case-insensitive; an unknown image is undecidable
        for image, want in (("claude", "present"), ("CLAUDE.EXE", "present"), ("Claude.exe", "present"),
                            ("node.exe", "undecidable"), ("code.exe", "undecidable"), ("claude-helper.exe", "undecidable")):
            rows, hp = host_chain(me, 4, host=image)
            verdict(rows + real_servers(hp), "host image %r with a matching server" % image, want)
        rows, hp = host_chain(me, 4, host="mystery.exe")
        verdict(rows, "an unknown host image and no server", "undecidable")
        # skip list: shells and launchers between the hook and the host
        for image in ("python", "python3", "pythonw", "py", "bash", "sh", "dash", "zsh", "cmd", "powershell", "pwsh", "env"):
            rows, hp = chain_to_host(me, ["python.exe", image + ".exe", "bash.exe"])
            verdict(rows + real_servers(hp), "skip list: %s.exe between the hook and the host" % image, "present")
        # hop limit: the host at 8 hops is found, at 9 it is not
        rows, hp = chain_to_host(me, ["python.exe"] + ["bash.exe"] * 7)
        verdict(rows + real_servers(hp), "the host exactly 8 hops above the hook", "present")
        rows, hp = chain_to_host(me, ["python.exe"] + ["bash.exe"] * 8)
        verdict(rows + real_servers(hp), "the host 9 hops above the hook: not found", "undecidable")
        # depth 4 below the host
        deep = [(host_pid + 31, host_pid, "cmd.exe", "cmd.exe /c x"), (host_pid + 32, host_pid + 31, "cmd.exe", "cmd.exe /c y"),
                (host_pid + 33, host_pid + 32, "cmd.exe", "cmd.exe /c z")]
        verdict(base + deep + [(host_pid + 34, host_pid + 33, "codegraph.exe", "codegraph serve --mcp")],
                "a server at depth 4 below the host", "present")
        verdict(base + deep + [(host_pid + 34, host_pid + 33, "cmd.exe", "cmd.exe /c w"),
                               (host_pid + 35, host_pid + 34, "codegraph.exe", "codegraph serve --mcp")],
                "a server at depth 5 is not a candidate", "absent")
        # another session's server (a different host) is not ours
        other = [(9000, 1, "claude.exe", "claude.exe"), (9001, 9000, "codegraph.exe", "codegraph serve --mcp")]
        verdict(base + other, "a server under ANOTHER claude.exe is not this session's", "absent")


# ---- the notice -------------------------------------------------------------------------------------------------
@contextmanager
def notice_env(sb: af.Sandbox, project: Path, extra: dict | None = None):
    saved_temp, saved_cwd, saved_bytecode = tempfile.tempdir, os.getcwd(), sys.dont_write_bytecode
    tempfile.tempdir = str(sb.tmp)
    try:
        with mock.patch.dict(os.environ, af.isolated_env(sb.home, sb.tmp, project, extra), clear=True):
            os.chdir(str(project))
            yield
    finally:
        os.chdir(saved_cwd)
        tempfile.tempdir = saved_temp
        sys.dont_write_bytecode = saved_bytecode


@contextmanager
def bytecode_allowed():
    """sys.dont_write_bytecode False for the block (so a stray __pycache__ would show), restored in a finally."""
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = False
    try:
        yield
    finally:
        sys.dont_write_bytecode = saved


def load_fresh_hooks(sb: af.Sandbox, tag: str):
    """A new installed copy of the add-on's hooks (its own folder, no bytecode yet) and the guard module loaded from it
    with bytecode writing OFF, so any __pycache__ later is the notice section's doing. (The notice moved from the reset hook
    into the guard's file at the cut-over, so the variable keeps the name ``reset`` in the rows below.)"""
    paths = {p.name: p for p in af.install(ADD_ON, sb.root / ("inst-" + tag))}
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        reset = load_module(paths[HOOK_FILE], "cg295_guard_" + tag)
    finally:
        sys.dont_write_bytecode = saved
    return reset, paths


def table_reader(reset, rows=None, exc=None, delay: float = 0.0):
    def reader(*args, **kwargs):
        if delay:
            time.sleep(delay)
        if exc is not None:
            raise exc
        return list(rows)
    return mock.patch.object(reset, "read_process_table", reader, create=True)


def call_notice(reset, payload: dict) -> tuple:
    fn = fn_of(reset, "notice_section")
    if not callable(fn):
        return None, ""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        try:
            outcome = fn(payload)
        except BaseException as exc:  # noqa: BLE001
            outcome = "raised %r" % (exc,)
    return outcome, out.getvalue()


def run_reset_main(reset, payload: dict) -> tuple:
    """The guard's prompt row, in-process: ``main()`` with the argument ``notice`` (the row the install writes)."""
    out, err = io.StringIO(), io.StringIO()
    code = None
    with mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), contextlib.redirect_stdout(out), \
            mock.patch.object(sys, "argv", [str(getattr(reset, "__file__", "guard")), "notice"]), \
            contextlib.redirect_stderr(err):
        try:
            reset.main()
        except SystemExit as exc:
            code = exc.code if exc.code is not None else 0
    return code, out.getvalue(), err.getvalue()


def run_notice_rows(w: World) -> None:
    with af.Sandbox("cg295n-") as sb:
        reset, paths = load_fresh_hooks(sb, "a")
        check("NT-0: the guard defines notice_section(payload)", callable(fn_of(reset, "notice_section")),
              "no module-level notice_section in " + HOOK_FILE)
        project = project_of(sb, "nt-ok")
        me = os.getpid()
        chain, host_pid = host_chain(me, 4)
        absent_table = chain
        present_table = chain + real_servers(host_pid)
        prompt_text = "SECRET-PROMPT-TEXT-123"

        def payload(proj=project, **extra):
            body = {"session_id": sid(), "cwd": str(proj), "prompt": prompt_text, "hook_event_name": "UserPromptSubmit"}
            body.update(extra)
            return body

        def outcome_for(rows, proj=project, label="", **extra):
            with notice_env(sb, proj):
                with table_reader(reset, rows):
                    return call_notice(reset, payload(proj, **extra))

        outcome, out = outcome_for(present_table)
        check("NT-1: a server process under this session's host: silent:probe-present, nothing printed",
              outcome == "silent:probe-present" and out == "", "%r %r" % (outcome, out))
        outcome, out = outcome_for(absent_table)
        check("NT-2: no server process, all preconditions met: outcome shown", outcome == "shown", "%r %r" % (outcome, out))
        parsed = None
        try:
            parsed = json.loads(out)
        except ValueError:
            pass
        check("NT-2: and stdout is ONE JSON object", isinstance(parsed, dict) and out.strip().count("\n") == 0, repr(out))
        if isinstance(parsed, dict):
            hso = parsed.get("hookSpecificOutput") or {}
            msg, ctx = parsed.get("systemMessage"), hso.get("additionalContext")
            check("NT-2: it carries systemMessage and hookSpecificOutput.hookEventName UserPromptSubmit with additionalContext",
                  isinstance(msg, str) and msg and hso.get("hookEventName") == "UserPromptSubmit" and isinstance(ctx, str), repr(parsed))
            check("NT-2: the user text and the model text are the same fixed text", msg == ctx, repr(parsed))
            check("NT-2: it ends with the exact precedence sentence", isinstance(ctx, str) and ctx.endswith(SENTENCE), repr(ctx))
            check("NT-2: it echoes nothing from the prompt or the payload",
                  prompt_text not in out and str(project) not in out and "SECRET" not in out, out)
            low = (ctx or "").lower()
            for needle in ("serve --mcp", "/mcp", "bash", "codegraph explore", "main checkout", "worktree"):
                check(f"NT-2: the notice says {needle!r}", needle in low, repr(ctx))
            check("NT-2: it advises no shell route to source files (no `cat`)", re.search(r"\bcat\b", low) is None, repr(ctx))
        # silent cases
        cases = [
            ("agent_id present (a subagent)", dict(table=absent_table, extra={"agent_id": "a1"}), "silent:precondition"),
            ("undecidable: an unknown host image", dict(table=host_chain(me, 4, host="mystery.exe")[0]), "silent:host-untrusted"),
            ("undecidable: a candidate whose command line cannot be read",
             dict(table=absent_table + [(host_pid + 50, host_pid, "node.exe", None)]), "silent:undecidable"),
            ("undecidable: serve --mcp with no CodeGraph token",
             dict(table=absent_table + [(host_pid + 51, host_pid, "node.exe", "node other.js serve --mcp")]), "silent:undecidable"),
        ]
        for label, spec, want in cases:
            outcome, out = outcome_for(spec["table"], **spec.get("extra", {}))
            check(f"NT-3 [{label}]: {want}, nothing printed", outcome == want and out == "", "%r %r" % (outcome, out))
        no_index = project_of(sb, "nt-noidx", index=False)
        if clean_above("NT-3 no-index", no_index):
            outcome, out = outcome_for(absent_table, no_index)
            check("NT-3 [no project index]: silent:precondition", outcome == "silent:precondition" and out == "", "%r %r" % (outcome, out))
        no_server = project_of(sb, "nt-nosrv", server=False)
        outcome, out = outcome_for(absent_table, no_server)
        check("NT-3 [server not configured]: silent:precondition", outcome == "silent:precondition" and out == "", "%r %r" % (outcome, out))
        disabled = project_of(sb, "nt-dis", server=False)
        af.plant_server(disabled, disabled=True)
        outcome, out = outcome_for(absent_table, disabled)
        check("NT-3 [server disabled]: silent:precondition", outcome == "silent:precondition" and out == "", "%r %r" % (outcome, out))
        url_only = project_of(sb, "nt-url", server=False)
        (url_only / ".mcp.json").write_text(json.dumps({"mcpServers": {"codegraph": {"url": "http://localhost:1/mcp"}}}), encoding="utf-8")
        outcome, out = outcome_for(absent_table, url_only)
        check("NT-3 [url-only server: nothing for the session to start]: silent:precondition", outcome == "silent:precondition" and out == "",
              "%r %r" % (outcome, out))
        # the closed-set outcomes for the failure paths
        with notice_env(sb, project):
            with table_reader(reset, absent_table, delay=0.4):
                outcome, out = call_notice(reset, payload())
        check("NT-4: a table read that takes longer than the 100 ms budget: silent:budget, nothing printed",
              outcome == "silent:budget" and out == "", "%r %r" % (outcome, out))
        for exc in (RuntimeError("boom"), OSError("denied"), ValueError("bad")):
            with notice_env(sb, project):
                with table_reader(reset, exc=exc):
                    outcome, out = call_notice(reset, payload())
            check(f"NT-4: a table reader raising {type(exc).__name__}: silent:error, nothing printed",
                  outcome == "silent:error" and out == "", "%r %r" % (outcome, out))
        check("NT-4: the notice calls the guard's own functions: no load by path and no import-failed outcome any more",
              "_load_guard" not in w.guard.read_text(encoding="utf-8") and "silent:import-failed" not in w.guard.read_text(encoding="utf-8"))
        # no kill switch (R-4): every plausible switch set, the notice still shows
        with notice_env(sb, project, {"CLAUDE_SKIP_CG": "1", "CODEGRAPH_NOTICE": "off", "CLAUDE_CODEGRAPH_NOTICE": "0"}):
            with table_reader(reset, absent_table):
                outcome, out = call_notice(reset, payload())
        check("NT-5: no environment variable silences the notice", outcome == "shown", "%r %r" % (outcome, out))
        # nothing written: the notice section creates no __pycache__ in the hooks folder
        with bytecode_allowed(), notice_env(sb, project):
            with table_reader(reset, absent_table):
                call_notice(reset, payload())
        check("NT-6: the notice section writes no bytecode (no __pycache__ in the hooks folder)",
              not (paths[HOOK_FILE].parent / "__pycache__").exists(),
              "found %s" % sorted(p.name for p in (paths[HOOK_FILE].parent / "__pycache__").glob("*")))


def run_notice_main_rows(w: World) -> None:
    with af.Sandbox("cg295m-") as sb:
        reset, paths = load_fresh_hooks(sb, "m")
        project = project_of(sb, "nm")
        me = os.getpid()
        chain, host_pid = host_chain(me, 4)
        folder_of = lambda session: pfolder(sb, session)  # noqa: E731
        ticket = "ticket-" + "c" * 64

        def seed(session):
            af.write_marker(af.session_parent(sb.home), session)
            (folder_of(session) / ticket).write_text("{}\n", encoding="utf-8")

        body = lambda session: {"session_id": session, "cwd": str(project), "prompt": "go"}  # noqa: E731
        for label, kwargs in (("a table reader raising SystemExit", dict(exc=SystemExit(7))),
                              ("a table reader raising RuntimeError", dict(exc=RuntimeError("boom"))),
                              ("a table reader raising KeyboardInterrupt", dict(exc=KeyboardInterrupt()))):
            session = sid()
            seed(session)
            with bytecode_allowed(), notice_env(sb, project):
                with table_reader(reset, **kwargs):
                    code, out, err = run_reset_main(reset, body(session))
            check(f"NM-1 [{label}]: main exits 0 with an empty stdout", code == 0 and out == "", "code=%r out=%r err=%r" % (code, out, err))
            check(f"NM-1 [{label}]: and the marker and the ticket were NOT deleted (the prompt row deletes neither)",
                  (folder_of(session) / "turn.json").exists() and (folder_of(session) / ticket).exists(),
                  str(sorted(os.listdir(folder_of(session)))))
            check(f"NM-1 [{label}]: and no __pycache__ appeared in the hooks folder", not (paths[HOOK_FILE].parent / "__pycache__").exists())
        session = sid()
        seed(session)
        with notice_env(sb, project):
            with table_reader(reset, chain):
                code, out, err = run_reset_main(reset, body(session))
        check("NM-2: main with no session server prints ONE notice JSON object and exits 0; marker and ticket are left alone",
              code == 0 and out.strip().startswith("{") and out.count("\n") <= 1
              and (folder_of(session) / "turn.json").exists() and (folder_of(session) / ticket).exists(),
              "code=%r out=%r err=%r" % (code, out, err))
        session = sid()
        with notice_env(sb, project):
            with table_reader(reset, chain + real_servers(host_pid)):
                code, out, err = run_reset_main(reset, body(session))
        check("NM-3: main with a session server present prints nothing", code == 0 and out == "", "code=%r out=%r" % (code, out))
        for outcome in ("silent:probe-present", "silent:precondition", "silent:host-untrusted", "silent:undecidable",
                        "silent:import-failed", "silent:budget", "silent:error"):
            session = sid()
            with notice_env(sb, project):
                with mock.patch.object(reset, "notice_section", lambda payload, _o=outcome: _o, create=True):
                    code, out, err = run_reset_main(reset, body(session))
            check(f"NM-4: main prints nothing when the section returns {outcome}", code == 0 and out == "", "code=%r out=%r" % (code, out))
        # a subprocess row with the real probe: only exit 0 and 'empty or one JSON object' can be asserted
        project2 = project_of(sb, "nm-sub")
        proc = run_hook(w.guard, sb, project2, "", {}, sid(), event="UserPromptSubmit", payload_extra={"prompt": "hi"}, argv=["notice"])
        ok = proc.returncode == 0
        if proc.stdout.strip():
            try:
                ok = ok and isinstance(json.loads(proc.stdout), dict)
            except ValueError:
                ok = False
        check("NM-5: the prompt row as a process (real probe) exits 0 and prints nothing or one JSON object", ok, describe(proc))


def run_server_starts_process(w: World) -> None:
    with af.Sandbox("cg295s-") as sb:
        guard = load_module(w.guard, "cg295_guard_ssp")
        fn = fn_of(guard, "server_starts_process")
        check("SSP-0: the guard defines server_starts_process(path)", callable(fn), "missing")
        if not callable(fn):
            return
        cases = []
        cmd = project_of(sb, "ssp-cmd")
        cases.append(("a command server", cmd, True))
        url = project_of(sb, "ssp-url", server=False)
        (url / ".mcp.json").write_text(json.dumps({"mcpServers": {"codegraph": {"url": "http://x/mcp"}}}), encoding="utf-8")
        cases.append(("a url-only server", url, False))
        both = project_of(sb, "ssp-both", server=False)
        (both / ".mcp.json").write_text(json.dumps({"mcpServers": {"codegraph": {"command": "codegraph", "url": "http://x"}}}), encoding="utf-8")
        cases.append(("command and url", both, True))
        blank = project_of(sb, "ssp-blank", server=False)
        (blank / ".mcp.json").write_text(json.dumps({"mcpServers": {"codegraph": {"command": "  ", "url": "http://x"}}}), encoding="utf-8")
        cases.append(("an empty command with a url", blank, False))
        none = project_of(sb, "ssp-none", server=False)
        cases.append(("no server entry", none, False))
        for label, project, want in cases:
            with notice_env(sb, project):
                try:
                    got = fn(str(project))
                except Exception as exc:  # noqa: BLE001
                    got = "raised %r" % exc
            check(f"SSP [{label}]: server_starts_process is {want}", got is want, "got %r" % (got,))


# ---- AC7 / AC8 text scans --------------------------------------------------------------------------------------
ENV_READ_RE = re.compile(r"""(?:environ\.get\(\s*|environ\[\s*|getenv\(\s*)["']([A-Za-z_][A-Za-z0-9_]*)["']""")
ALLOWED_HOOK_ENV = {"CLAUDE_PROJECT_DIR", "CLAUDE_CONFIG_DIR"}


def run_ac7_ac8(w: World) -> None:
    texts = {p.name: p.read_text(encoding="utf-8") for p in (w.guard, w.tracker, w.reset)}
    for name, text in texts.items():
        found = set(ENV_READ_RE.findall(text))
        check(f"AC7 [{name}]: reads no environment variable beyond the #259 allow-list {sorted(ALLOWED_HOOK_ENV)}",
              found <= ALLOWED_HOOK_ENV, "reads %s" % sorted(found - ALLOWED_HOOK_ENV))
        check(f"AC7 [{name}]: names no kill-switch variable", re.search(r"CLAUDE_SKIP|CODEGRAPH_(?:OFF|DISABLE|SKIP|NOTICE)|NO_CODEGRAPH", text) is None)
    check("AC7: the tracker implements the route (it mentions the cli route and mcp-seen) - non-vacuity for the scan above",
          '"cli"' in texts[TRACKER_FILE] and "mcp-seen" in texts[TRACKER_FILE],
          "tracker text lacks the cli route / mcp-seen")
    check("AC7: the guard implements the notice (notice_section) and the Counted test (counted_subcommand) - non-vacuity",
          "notice_section" in texts[HOOK_FILE] and "counted_subcommand" in texts[HOOK_FILE])
    manifest = af.manifest(ADD_ON, HOOK_FILE)
    check("AC8: addon.json lists exactly one hook (the guard); the tracker and the reset hook are disabled hooks",
          manifest.get("hooks") == [HOOK_FILE]
          and sorted(e.get("hook") for e in manifest.get("disabled", [])) == sorted([TRACKER_FILE, RESET_FILE]),
          repr((manifest.get("hooks"), [e.get("hook") for e in manifest.get("disabled", [])])))
    writer = re.compile(r"(?:create_flag|os\.replace|write\w*|open|replace|touch|mkdir|rename|symlink|link)\s*\("
                        r"[^)\n]*(?:MARKER_NAME|MCP_SEEN_NAME|turn\.json|mcp-seen|MCP_SEEN|\btarget\b)")

    def writes(text: str) -> list:
        return [ln.strip() for ln in text.splitlines() if writer.search(ln) and not ln.strip().startswith(("#", "def "))]

    found = writes(texts[TRACKER_FILE])
    check("AC8 positive control: the pattern finds the tracker's os.replace onto the marker target",
          any("os.replace" in ln for ln in found), repr(found))
    check("AC8 positive control: and its create_flag(..., MCP_SEEN_NAME)",
          any("create_flag" in ln and "MCP_SEEN_NAME" in ln for ln in found), repr(found))
    for name in (HOOK_FILE, RESET_FILE):
        lines = writes(texts[name])
        check(f"AC8 [{name}]: writes neither turn.json nor mcp-seen (only the retired tracker did)",
              not lines, "\n".join(lines))
    check("AC8 [tracker]: the tracker is the writer of mcp-seen", "mcp-seen" in texts[TRACKER_FILE])


# ---- review follow-ups (issue #295 code review), kept for the guard's transcript rule (issue #262) ------------------------------------
def run_review_followups(w: World) -> None:
    with af.Sandbox("cg295v-") as sb:
        project = project_of(sb, "rv")
        make_logs(project)
        H = af.t_human

        def block_in(entry: dict) -> str:
            return json.dumps(entry)

        # (4) the dict-shaped error flags of the old tracker do not matter: only the tool use is read
        for key in ("isError", "is_error"):
            line = block_in({"type": "assistant", "isSidechain": False, "isError": True, "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t", "name": "mcp__codegraph__codegraph_explore", "input": {}, key: True}]}})
            proc = cut(w, sb, project, [H(1), line])
            check(f"TB-3: an MCP tool use carrying {key}: true still counts (a failed attempt counts, Q1)", silent_allow(proc), describe(proc))
        # (5) a Bash tool use whose input is not an object, or whose command is not text, is not a Counted command
        for label, tool_input in (("a list input", ["codegraph explore x"]), ("a numeric command", {"command": 5}), ("no command", {})):
            line = af.t_assistant({"type": "tool_use", "id": "t", "name": "Bash", "input": tool_input})
            proc = cut(w, sb, project, [H(1), line])
            check(f"TB-4: a Bash tool use with {label} leaves the turn closed (and never raises)", blocked(proc), describe(proc))
        # (6) an assistant entry with a non-list content, and a tool_use with no name, never open anything
        proc = cut(w, sb, project, [H(1), json.dumps({"type": "assistant", "isSidechain": False, "message": {"role": "assistant", "content": "x"}}),
                                    af.t_assistant({"type": "tool_use", "id": "t", "input": {}})])
        check("TB-5: an assistant entry with text content and a tool_use with no name open nothing", blocked(proc), describe(proc))


def run_process_table_real(w: World) -> None:
    """The real Windows reader sees a real child: its pid, its parent, a python image and, through the module-level
    ``command_line(pid)``, its exact command line (F1)."""
    if sys.platform != "win32":
        skip("PT-1 real process table with a codegraph serve --mcp look-alike child", "Windows-only row (Toolhelp32 + NtQueryInformationProcess)")
        return
    with af.Sandbox("cg295w-") as sb:
        reset = load_reset_module(sb, w)
        args = [sys.executable, "-c", "import time;time.sleep(5)", "codegraph", "serve", "--mcp"]
        expected = subprocess.list2cmdline(args)
        child = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(0.3)
            table = reset.read_process_table()
            rows = [r for r in table if r[0] == child.pid]
            check("PT-1: the real read_process_table() holds the child, with this process as its parent and a python image",
                  len(rows) == 1 and rows[0][1] == os.getpid() and str(rows[0][2]).lower().startswith("python"),
                  "rows=%r (me=%d)" % (rows, os.getpid()))
            check("PT-1: and its command-line column is the child's exact command line (or None when not examined)",
                  len(rows) == 1 and rows[0][3] in (None, expected), "got %r want %r" % (rows[0][3] if rows else None, expected))
            fn = getattr(reset, "command_line", None)
            check("PT-2: the reset hook has a MODULE-LEVEL command_line(pid)", callable(fn), "no module-level command_line")
            if callable(fn):
                got = fn(child.pid)
                check("PT-2: command_line(child_pid) returns the child's exact command line", got == expected, "got %r want %r" % (got, expected))
        finally:
            child.kill()
            try:
                child.wait(timeout=10)
            except Exception:  # noqa: BLE001
                pass


# ---- the bench's --reset-budget mode (unit rows) ---------------------------------------------------------------
def run_bench_rows(w: World) -> None:
    bench_path = Path(__file__).resolve().parent / "bench_codegraph_guard.py"
    spec = importlib.util.spec_from_file_location("cg295_bench", bench_path)
    bench = importlib.util.module_from_spec(spec)
    sys.modules["cg295_bench"] = bench  # @dataclass reads the module back from sys.modules
    saved_bytecode, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(bench)
    finally:
        sys.dont_write_bytecode = saved_bytecode
        sys.modules.pop("cg295_bench", None)
    check("BN-1: the bench pins its baseline: RESET_BASELINE_REF == 'db61fd7'", getattr(bench, "RESET_BASELINE_REF", None) == "db61fd7",
          repr(getattr(bench, "RESET_BASELINE_REF", None)))
    check("BN-1: db61fd7 (the 0.16.1 baseline) is present in this checkout (a missing commit FAILS, never skips)",
          subprocess.run(["git", "cat-file", "-e", "db61fd7^{commit}"], cwd=str(af.PROJECT_ROOT), capture_output=True).returncode == 0,
          "fetch the full history")
    err, out = io.StringIO(), io.StringIO()
    code = None

    class NoWorkspace:
        def __init__(self, *args, **kwargs):
            raise AssertionError("--reset-budget must never build the #259 Workspace")

    with mock.patch.object(bench, "RESET_BASELINE_REF", "0" * 40, create=True), mock.patch.object(bench, "Workspace", NoWorkspace), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = bench.main(["--reset-budget"])
        except SystemExit as exc:
            code = "SystemExit(%r)" % (exc.code,)
        except BaseException as exc:  # noqa: BLE001
            code = "raised %r" % (exc,)
    check("BN-2: --reset-budget with the baseline commit absent exits 1 (not an argparse error, not a Workspace build)",
          code == 1, "code=%r stderr=%r" % (code, err.getvalue()[-300:]))
    check("BN-2: and the message says to fetch the full history", "fetch the full history" in (err.getvalue() + out.getvalue()),
          err.getvalue()[-300:])
    helped, herr = io.StringIO(), io.StringIO()
    code = None
    with contextlib.redirect_stdout(helped), contextlib.redirect_stderr(herr):
        try:
            bench.main(["--help"])
        except SystemExit as exc:
            code = exc.code
    usage = helped.getvalue()
    check("BN-3: the default mode is untouched: the bench's parser still accepts --old-ref, --runs, --sizes, --json, --keep "
          "(--help exits 0 and lists them) and now also --reset-budget",
          code == 0 and all(opt in usage for opt in ("--old-ref", "--runs", "--sizes", "--json", "--keep", "--reset-budget")),
          "exit=%r usage=%r" % (code, usage[-300:]))


# --------------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------------
# CO-*: the cut-over (issue #262). The guard decides from the Transcript turn state; the tracker's route, the pruning
# and the Connection notice moved into the guard's file. Contract: .claude/concepts/2026-11-09-codegraph-hooks-cutover.md
# --------------------------------------------------------------------------------------------------------------
MEASUREMENT_KEYS = {"ts", "session", "agent", "tool", "target_class", "live_decision", "live_reason", "turn_marker",
                    "turn_route", "transcript_turn", "session_seen", "shadow_decision", "shadow_reason", "outcome", "fp",
                    "prompt_key", "shadow_ms", "bytes_read", "skipped_long_line"}


def fresh_transcript(sb: af.Sandbox, lines: list) -> Path:
    return af.write_transcript(sb.root / "tr" / (uuid.uuid4().hex + ".jsonl"), lines)


def cut(w: World, sb: af.Sandbox, project: Path, lines: list | None, session: str | None = None, tool: str = "Read",
        tool_input: dict | None = None, extra: dict | None = None, path: Path | None = None) -> subprocess.CompletedProcess:
    """One guarded call whose transcript holds ``lines`` (None: the payload carries no transcript_path; ``path``: use that file)."""
    transcript = None if (lines is None and path is None) else (path or fresh_transcript(sb, lines))
    return run_hook(w.guard, sb, project, tool, tool_input if tool_input is not None else read_cs(project),
                    session or sid(), payload_extra=extra, transcript=transcript)


def one_line_notice(proc: subprocess.CompletedProcess, reason: str) -> bool:
    return proc.returncode == 0 and proc.stderr.count("allowed (") == 1 and reason in proc.stderr


def run_cutover_states(w: World) -> None:
    with af.Sandbox("cgco-") as sb:
        project = project_of(sb, "co")
        make_logs(project)
        H, M, B = af.t_human, af.t_mcp_use, af.t_bash_use
        # open by the three routes, each counted when the main session issues the call
        proc = cut(w, sb, project, [H(1), M(), af.t_tool_result()])
        check("CO-1 open via mcp: a source Read is allowed with no stderr line (transcript-open)", silent_allow(proc), describe(proc))
        rec = (shadow_records(project) or [{}])[-1]
        check("CO-1 open via mcp: the Measurement record says enforced, transcript-open, route mcp",
              rec.get("outcome") == "enforced" and rec.get("live_reason") == "transcript-open"
              and rec.get("turn_route") == "mcp" and rec.get("transcript_turn") == "open", rec)
        for command in ("codegraph explore Thing", 'codegraph query "a b"', "codegraph files src", "codegraph explore Thing 2>&1"):
            proc = cut(w, sb, project, [H(1), B(command)])
            check(f"CO-2 open via a Bash Counted command [{command}]: allowed, silent", silent_allow(proc), describe(proc))
        rec = (shadow_records(project) or [{}])[-1]
        check("CO-2 open via Bash: the record names route cli", rec.get("turn_route") == "cli", rec)
        for command in ("codegraph explore X && ls", "codegraph explore X | head", "codegraph explore X; ls", "codegraph status",
                        "codegraph init -i", "echo codegraph explore X", " codegraph explore X", "FOO=1 codegraph explore X",
                        "codegraph explore $(whoami)", "npx codegraph explore X"):
            proc = cut(w, sb, project, [H(1), B(command)])
            check(f"CO-3 a non-Counted command [{command!r}] leaves the turn closed: BLOCKED", blocked(proc), describe(proc))
        proc = cut(w, sb, project, [H(1), B("codegraph explore Thing", background=True)])
        check("CO-3 a background run of a Counted command leaves the turn closed: BLOCKED", blocked(proc), describe(proc))
        for name in ("Agent", "Task"):
            proc = cut(w, sb, project, [H(1), af.t_agent_use(name), af.t_tool_result()])
            check(f"CO-4 a {name} dispatch in the current turn opens it (C-7): allowed, silent", silent_allow(proc), describe(proc))
        rec = (shadow_records(project) or [{}])[-1]
        check("CO-4 the record names route agent", rec.get("turn_route") == "agent", rec)
        proc = cut(w, sb, project, [H(1), af.t_agent_use(), H(2)])
        check("CO-5 a dispatch BEFORE the last human prompt does not open the new turn: BLOCKED", blocked(proc), describe(proc))
        proc = cut(w, sb, project, [H(1), M(), H(2), af.t_filler()])
        check("CO-6 closed after a new human prompt: BLOCKED", blocked(proc), describe(proc))
        proc = cut(w, sb, project, [H(1), M(), af.t_tool_result(), af.t_task_notification()])
        check("CO-7 a background task notification does not close the turn: allowed", silent_allow(proc), describe(proc))
        proc = cut(w, sb, project, [H(1), af.t_task_notification()])
        check("CO-7 a task notification does not open a turn either: BLOCKED", blocked(proc), describe(proc))


def run_cutover_unknown(w: World) -> None:
    with af.Sandbox("cgcu-") as sb:
        project = project_of(sb, "cu")
        make_logs(project)
        session = sid()
        first = cut(w, sb, project, None, session)
        second = cut(w, sb, project, None, session)
        check("CO-8 no transcript_path: allowed with one stderr line fail-open:transcript-no-transcript, on each call",
              one_line_notice(first, "fail-open:transcript-no-transcript")
              and one_line_notice(second, "fail-open:transcript-no-transcript"), describe(first) + " / " + describe(second))
        got = [r for r in events(project, "fail-open") if "no-transcript" in json.dumps(r)]
        check("CO-8 ...and ONE log record per session per cause", len(got) == 1, repr(events(project, "fail-open")))
        proc = cut(w, sb, project, None, None, path=sb.root / "tr" / "missing.jsonl")
        check("CO-8 a missing transcript file: fail-open:transcript-no-transcript",
              one_line_notice(proc, "fail-open:transcript-no-transcript"), describe(proc))
        bad = sb.root / "tr" / "bad.jsonl"
        bad.parent.mkdir(exist_ok=True)
        bad.write_bytes(b'{"type": "user", broken\n' + af.t_human(1).encode() + b"\n")
        proc = cut(w, sb, project, None, None, path=bad)
        check("CO-8 an unparseable line: fail-open:transcript-parse-error", one_line_notice(proc, "fail-open:transcript-parse-error"),
              describe(proc))
        big = sb.root / "tr" / "big.jsonl"
        big.write_bytes((af.t_filler(1000) + "\n").encode() * 2600)
        proc = cut(w, sb, project, None, None, path=big)
        check("CO-8 a window with no boundary: fail-open:transcript-window-exceeded",
              one_line_notice(proc, "fail-open:transcript-window-exceeded"), describe(proc))
        s2 = sid()
        longer = fresh_transcript(sb, [af.t_human(1), af.t_filler(2000)])
        cut(w, sb, project, None, s2, path=longer)
        af.write_transcript(longer, [af.t_human(1)])
        proc = cut(w, sb, project, None, s2, path=longer)
        check("CO-8 a rewritten (shorter) transcript: fail-open:transcript-rewritten", one_line_notice(proc, "fail-open:transcript-rewritten"),
              describe(proc))
        # an allowlisted target with an unknown state prints nothing
        proc = cut(w, sb, project, None, None, tool_input={"file_path": str(project / "docs" / "notes.md")})
        check("CO-9 an allowlisted target with an unknown state prints nothing (exit 0, no stderr line)",
              silent_allow(proc) and proc.stderr.strip() == "", describe(proc))
        # a subagent: no transcript is read, the step-3 allow stands
        proc = cut(w, sb, project, [af.t_human(1)], None, extra={"agent_id": "a1", "agent_type": "general-purpose"})
        check("CO-9b a subagent call is allowed at step 3 (fail-open:subagent), not at the transcript step",
              allowed(proc, "fail-open:subagent") and "transcript" not in proc.stderr, describe(proc))
        # a planted turn.json no longer opens anything
        s3 = sid()
        af.write_marker(af.session_parent(sb.home), s3)
        proc = cut(w, sb, project, [af.t_human(1)], s3)
        check("CO-10 a turn.json in the Session folder opens nothing (the marker is neither read nor written): BLOCKED",
              blocked(proc), describe(proc))


def run_cutover_state_and_tickets(w: World) -> None:
    with af.Sandbox("cgct-") as sb:
        project = project_of(sb, "ct")
        make_logs(project)
        H = af.t_human
        link_target = sb.root / "ct-target"
        link_target.mkdir()
        session = sid()
        af.session_parent(sb.home)
        link = pfolder(sb, session)
        if af.make_dir_link(link, link_target):
            proc = cut(w, sb, project, [H(1), af.t_mcp_use()], session)
            check("CO-11 an unusable Session folder: no transcript is read, the call blocks session-state-unusable (as today)",
                  blocked(proc) and "session-state-unusable" in proc.stderr, describe(proc))
            rec = (shadow_records(project) or [{}])[-1]
            check("CO-11 ...and the record shows nothing was read", rec.get("bytes_read") == 0 and rec.get("live_reason") == "session-state-unusable", rec)
            check("CO-11 ...and nothing was written through the link", not any(link_target.iterdir()), [p.name for p in link_target.iterdir()])
            try:
                os.rmdir(str(link))
            except OSError:
                pass
        else:
            skip("CO-11 an unusable Session folder", "the OS refused to create a folder link")
        # tickets are keyed to the prompt
        t = fresh_transcript(sb, [H(1)])
        s = sid()
        first = cut(w, sb, project, None, s, path=t, extra={"prompt_id": "prompt-A"})
        again = cut(w, sb, project, None, s, path=t, extra={"prompt_id": "prompt-A"})
        check("CO-12 a block and its identical retry in the same prompt: the retry is allowed (retry-escape-used)",
              blocked(first) and allowed(again, "retry-escape-used"), describe(first) + " / " + describe(again))
        s = sid()
        cut(w, sb, project, None, s, path=t, extra={"prompt_id": "prompt-A"})
        other = cut(w, sb, project, None, s, path=t, extra={"prompt_id": "prompt-B"})
        check("CO-12 a ticket from another prompt reads as absent: the identical call is BLOCKED again", blocked(other), describe(other))
        s = sid()
        cut(w, sb, project, None, s, path=t, extra={"prompt_id": "prompt-A"})
        tickets = list(pfolder(sb, s).glob("ticket-*"))
        body = json.loads(tickets[0].read_text(encoding="utf-8")) if tickets else {}
        check("CO-12 the ticket body carries ts, tool, fingerprint and a 12-hex prompt_key",
              {"ts", "tool", "fingerprint", "prompt_key"} <= set(body) and re.fullmatch(r"[0-9a-f]{12}", str(body.get("prompt_key"))) is not None, body)
        if tickets:
            tickets[0].write_text(json.dumps({"ts": 1, "tool": "Read", "fingerprint": body.get("fingerprint")}) + "\n", encoding="utf-8")
        old = cut(w, sb, project, None, s, path=t, extra={"prompt_id": "prompt-A"})
        check("CO-12 a ticket with no prompt_key reads as absent: BLOCKED, and the block overwrites it with a keyed one",
              blocked(old) and tickets and "prompt_key" in tickets[0].read_text(encoding="utf-8"), describe(old))
        s = sid()
        cut(w, sb, project, None, s, path=t)
        keyless = cut(w, sb, project, None, s, path=t)
        check("CO-12 a host that sends no prompt_id: a ticket keyed 'none' may match", allowed(keyless, "retry-escape-used"), describe(keyless))


def run_cutover_fallback_and_record(w: World) -> None:
    with af.Sandbox("cgcf-") as sb:
        project = project_of(sb, "cf")
        make_logs(project)
        H, M, B = af.t_human, af.t_mcp_use, af.t_bash_use
        s = sid()
        t = fresh_transcript(sb, [H(1), B("codegraph explore Thing")])
        cut(w, sb, project, None, s, path=t)
        cut(w, sb, project, None, s, path=t)
        got = events(project, "cli-fallback")
        check("CO-13 a cli-opened turn with no mcp use this session writes ONE cli-fallback record per session",
              len(got) == 1 and got[0].get("details", {}).get("reason") == "mcp-unavailable"
              and got[0].get("details", {}).get("command") == "explore", repr(got))
        check("CO-13 ...and the logged-cli-fallback flag is set after the record landed",
              (pfolder(sb, s) / "logged-cli-fallback").exists())
        before = len(events(project, "cli-fallback"))
        cut(w, sb, project, [H(1), M(), B("codegraph explore Thing")])
        cut(w, sb, project, [H(1), af.t_agent_use()])
        check("CO-13 no record when mcp was seen this session, and none for an agent route",
              len(events(project, "cli-fallback")) == before, repr(events(project, "cli-fallback")))
        s = sid()
        t2 = fresh_transcript(sb, [H(1), M(), af.t_tool_result(), H(2), B("codegraph explore Thing")])
        cut(w, sb, project, None, s, path=t2)
        check("CO-13 mcp_seen is sticky across prompts: [prompt, mcp, prompt, bash] writes no record",
              len(events(project, "cli-fallback")) == before, repr(events(project, "cli-fallback")))
        # the Measurement record shape
        cut(w, sb, project, [H(1)])
        rec = (shadow_records(project) or [{}])[-1]
        check("CO-14 the enforced Measurement record has exactly the contract's keys", set(rec) == MEASUREMENT_KEYS, sorted(set(rec) ^ MEASUREMENT_KEYS))
        check("CO-14 outcome enforced, shadow_* equal live_*, turn_marker null, turn_route null on a closed turn",
              rec.get("outcome") == "enforced" and rec.get("shadow_decision") == rec.get("live_decision")
              and rec.get("shadow_reason") == rec.get("live_reason") and rec.get("turn_marker") is None
              and rec.get("turn_route") is None and rec.get("live_decision") == "block", rec)
        guard_text = w.guard.read_text(encoding="utf-8")
        check("CO-15 the turn read is timed with time.perf_counter (time.monotonic ticks in 15.6 ms steps on Windows)",
              "perf_counter" in guard_text and "monotonic" not in guard_text)
        check("CO-16 the guard neither reads nor writes the Turn marker (no marker name, no Foreign marker code)",
              "MARKER_NAME" not in guard_text and "note_foreign_marker" not in guard_text and "foreign-marker" not in guard_text)


def run_cutover_late_effects(w: World) -> None:
    with af.Sandbox("cgcl-") as sb:
        project = project_of(sb, "cl")
        make_logs(project)
        env = af.isolated_env(sb.home, sb.tmp, project)

        def once(patches: dict, lines: list) -> tuple:
            mod = load_module(w.guard, "codegraph_first_guard_late_" + uuid.uuid4().hex[:8])
            transcript = fresh_transcript(sb, lines)
            payload = guard_payload(project, sid(), transcript_path=str(transcript), prompt_id="p")
            with contextlib.ExitStack() as stack:
                for name, value in patches.items():
                    stack.enter_context(mock.patch.object(mod, name, value, create=True))
                return run_inproc(mod, payload, env)

        def boom(*args, **kwargs):
            raise RuntimeError("forced")

        def exits(*args, **kwargs):
            raise SystemExit(9)

        class Weird(BaseException):
            pass

        def weird(*args, **kwargs):
            raise Weird()

        for label, lines in (("a block", [af.t_human(1)]), ("an allow through the gate", [af.t_human(1), af.t_mcp_use()])):
            base_code, base_err = once({}, lines)
            for effect in ("_write_cursor", "_append_shadow_line"):
                for fn in (boom, exits, weird):
                    code, err = once({effect: fn}, lines)
                    check(f"CO-17 {label}: {effect} forced to raise {fn.__name__} leaves exit code and stderr unchanged",
                          code == base_code and err == base_err, "base (%s, %r) vs (%s, %r)" % (base_code, base_err[:120], code, err[:120]))
        # log_event is the effect behind the fail-open and cli-fallback records
        cli = [af.t_human(1), af.t_bash_use("codegraph explore Thing")]
        base_code, base_err = once({}, cli)
        for fn in (boom, exits, weird):
            code, err = once({"log_event": fn}, cli)
            check(f"CO-17 the cli-fallback record: log_event forced to raise {fn.__name__} leaves exit code and stderr unchanged",
                  code == base_code and err == base_err, "base (%s, %r) vs (%s, %r)" % (base_code, base_err[:120], code, err[:120]))
        # the fail-open record is an effect too: the stderr line is printed whatever the record raises
        def once_missing(patches: dict) -> tuple:
            mod = load_module(w.guard, "codegraph_first_guard_late_" + uuid.uuid4().hex[:8])
            payload = guard_payload(project, sid(), transcript_path=str(sb.root / "tr" / "never-written.jsonl"), prompt_id="p")
            with contextlib.ExitStack() as stack:
                for name, value in patches.items():
                    stack.enter_context(mock.patch.object(mod, name, value, create=True))
                return run_inproc(mod, payload, env)

        base_code, base_err = once_missing({})
        check("CO-17 control: a missing transcript fails open with one stderr line", base_code == 0 and base_err.count("allowed (") == 1,
              (base_code, base_err))
        for fn in (boom, exits, weird):
            code, err = once_missing({"log_event": fn})
            check(f"CO-17 the fail-open record: log_event forced to raise {fn.__name__} leaves exit code and stderr unchanged",
                  code == base_code and err == base_err, "base (%s, %r) vs (%s, %r)" % (base_code, base_err[:120], code, err[:120]))
        # an exception inside the read is the cause 'error': fail open, one stderr line
        mod = load_module(w.guard, "codegraph_first_guard_readerr")
        payload = guard_payload(project, sid(), transcript_path=str(fresh_transcript(sb, [af.t_human(1)])))
        with mock.patch.object(mod, "read_transcript", boom):
            code, err = run_inproc(mod, payload, env)
        check("CO-18 an exception inside the transcript read allows with fail-open:transcript-error (one stderr line)",
              code == 0 and "fail-open:transcript-error" in err and err.count("allowed (") == 1, (code, err))
        # a read that runs out of its time budget is the cause time-exceeded
        mod = load_module(w.guard, "codegraph_first_guard_budget")
        payload = guard_payload(project, sid(), transcript_path=str(fresh_transcript(sb, [af.t_human(1)])))
        with mock.patch.object(mod, "TRANSCRIPT_TIME_BUDGET_S", -1.0, create=True):
            code, err = run_inproc(mod, payload, env)
        check("CO-18 a read past its time budget allows with fail-open:transcript-time-exceeded",
              code == 0 and "fail-open:transcript-time-exceeded" in err, (code, err))


def run_prompt_row(w: World) -> None:
    with af.Sandbox("cgpr-") as sb:
        project = project_of(sb, "pr", server=False)
        make_logs(project)

        def notice(session: str, argv=("notice",), env_extra=None, dont_bytecode=True, hook: Path | None = None):
            payload = {"session_id": session, "cwd": str(project), "hook_event_name": "UserPromptSubmit", "prompt": "hello"}
            env = af.isolated_env(sb.home, sb.tmp, project, env_extra)
            if not dont_bytecode:
                env.pop("PYTHONDONTWRITEBYTECODE", None)
            return subprocess.run([sys.executable] + (["-B"] if dont_bytecode else []) + [str(hook or w.guard), *argv],
                                  input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", cwd=str(project), env=env, timeout=60)

        parent = af.session_parent(sb.home)
        s = sid()
        stale = old_session(parent, "auto-improve-codegraph-oldsession1")
        proc = notice(s)
        check("PRW-1 the guard's prompt row exits 0 and prints nothing when nothing needs saying", proc.returncode == 0 and proc.stdout.strip() == "", describe(proc))
        check("PRW-1 it prunes an old session folder on the first prompt of a session", not stale.exists(), "still there: %s" % stale)
        check("PRW-1 and sets the pruned flag in this session's folder", (pfolder(sb, s) / "pruned").exists())
        stale2 = old_session(parent, "auto-improve-codegraph-oldsession2")
        notice(s)
        check("PRW-2 it prunes ONCE per session: a second old folder survives the second prompt", stale2.exists(), "pruned again")
        # none of the old reset hook's deletions
        s2 = sid()
        folder = pfolder(sb, s2, True)
        folder.mkdir(exist_ok=True)
        ticket = folder / ("ticket-" + "a" * 64)
        ticket.write_text("{}\n", encoding="utf-8")
        legacy = project / ".claude" / ".codegraph-used-this-turn"
        legacy.write_text("legacy\n", encoding="utf-8")
        marker = af.write_marker(parent, s2)
        proc = notice(s2)
        check("PRW-3 it deletes no ticket, no turn.json and no legacy sentinel", proc.returncode == 0 and ticket.exists() and marker.exists() and legacy.exists(),
              describe(proc))
        # no bytecode
        hooks_copy = sb.root / "pycache-check" / ".claude" / "hooks"
        hooks_copy.mkdir(parents=True)
        for name in (HOOK_FILE, "_error_log.py", "_project_paths.py"):
            shutil.copyfile(w.guard.parent / name, hooks_copy / name)
        proc = notice(sid(), dont_bytecode=False, hook=hooks_copy / HOOK_FILE)
        check("PRW-4 the prompt row writes no __pycache__ (neither beside the hook nor beside its helpers)",
              proc.returncode == 0 and not list(hooks_copy.rglob("__pycache__")), describe(proc) + str(list(hooks_copy.rglob("__pycache__"))))
        # an unusable folder: one line, no 'gate stays shut', exit 0
        s3 = sid()
        target = sb.root / "pr-target"
        target.mkdir()
        link = pfolder(sb, s3)
        if af.make_dir_link(link, target):
            stale3 = old_session(parent, "auto-improve-codegraph-oldsession3")
            proc = notice(s3)
            check("PRW-5 an unusable Session folder: exit 0, one line saying why, no 'gate stays shut' claim, nothing pruned",
                  proc.returncode == 0 and "cannot be used" in proc.stderr and "gate stays shut" not in proc.stderr and stale3.exists(), describe(proc))
            try:
                os.rmdir(str(link))
            except OSError:
                pass
        # whatever it raises, SystemExit included, ends in exit 0
        mod = load_module(w.guard, "codegraph_first_guard_notice_raise")
        env = af.isolated_env(sb.home, sb.tmp, project)
        for target_name in ("notice_section", "prune_session_folders", "_first_prompt_of_session"):
            for exc in (RuntimeError("x"), SystemExit(5)):
                def raiser(*a, _e=exc, **k):
                    raise _e
                code = None
                with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(sys, "argv", [str(w.guard), "notice"]), \
                        mock.patch.object(sys, "stdin", io.StringIO(json.dumps({"session_id": sid(), "cwd": str(project)}))), \
                        mock.patch.object(mod, target_name, raiser, create=True), contextlib.redirect_stderr(io.StringIO()), \
                        contextlib.redirect_stdout(io.StringIO()):
                    try:
                        mod.main()
                    except SystemExit as stop:
                        code = stop.code if stop.code is not None else 0
                check(f"PRW-6 the prompt row exits 0 when {target_name} raises {type(exc).__name__}", code == 0, code)
        # the old reset hook is not a hook any more
        check("PRW-7 the manifest registers the guard's prompt row (UserPromptSubmit, args [notice]) and no reset or tracker row",
              {(r["event"], r["hook"], tuple(r.get("args", []))) for r in af.registrations(ADD_ON)}
              == {("PreToolUse", HOOK_FILE, ()), ("UserPromptSubmit", HOOK_FILE, ("notice",))}, af.registrations(ADD_ON))


def guarded(name: str, fn, *args) -> None:
    """One section: a crash inside it is ONE failing check naming the section, and the runner goes on."""
    try:
        fn(*args)
    except Exception:  # noqa: BLE001
        check(f"section {name} ran to the end without an error", False, traceback.format_exc())


def run() -> None:
    real_temp_before = af.real_temp_codegraph_entries()
    real_parent_before = af.real_parent_codegraph_entries()
    real_snapshot_before = af.real_parent_snapshot()
    try:
        world = World()
    except af.AddonFixtureError as exc:
        check("the codegraph add-on is available to this suite (hook, manifest and helpers exist)", False, str(exc))
        return
    try:
        guarded("K-4", run_k4, world)
        guarded("CO-states", run_cutover_states, world)
        guarded("CO-unknown", run_cutover_unknown, world)
        guarded("CO-tickets", run_cutover_state_and_tickets, world)
        guarded("CO-record", run_cutover_fallback_and_record, world)
        guarded("CO-late", run_cutover_late_effects, world)
        guarded("PR", run_prompt_row, world)
        guarded("#612", run_612)
        guarded("R", run_reasons, world)
        guarded("E", run_escape, world)
        guarded("T", run_marker, world)
        guarded("O", run_ownership, world)
        guarded("O-4", run_server_only_under_main, world)
        guarded("P-1", run_parity_server, world)
        guarded("P-2", run_parity_ownership, world)
        guarded("U", run_own_root_units, world)
        guarded("V", run_review_round_two, world)
        guarded("W", run_review_round_three, world)
        guarded("X", run_pruner, world)
        guarded("X-8", run_prune_once, world)
        guarded("S", run_state, world)
        guarded("L", run_link_writes, world)
        guarded("Q-plant", run_planted_state, world)
        guarded("Q-prune", run_parent_pruner, world)
        guarded("Q-leftover-marker", run_foreign_marker, world)
        guarded("Q-rule", run_parent_rule_table, world)
        guarded("Q-unusable", run_unusable_parent, world)
        guarded("Q-nonsource", run_unusable_nonsource, world)
        guarded("Q-checkfailed", run_check_failed, world)
        guarded("Q-announce", run_announce_unusable, world)
        guarded("Q-ticket", run_ticket_unwritten, world)
        guarded("Q-banner", run_banner_by_reason, world)
        guarded("Q-hop", run_hop_proof, world)
        guarded("R2-parity", run_verdict_function_parity, world)
        guarded("R2-mapped", run_recorded_mapped_drive, world)
        guarded("R2-surrogate", run_block_survives_surrogates, world)
        guarded("R3-pre-realpath", run_remote_before_realpath, world)
        guarded("R3-nonstring", run_block_non_string_fields, world)
        guarded("R2-matrix", run_verdict_matrix, world)
        guarded("R2-boundary", run_base_boundaries, world)
        guarded("R2-fallback-order", run_foreign_marker_order, world)
        guarded("R2-ambiguous", run_ambiguous_after_unwritten, world)
        guarded("R2-bridge", run_bridge_without_own_root, world)
        guarded("R2-snapshot", run_real_parent_snapshot_selfcheck, world)
        guarded("CLI", run_cli_route, world)
        guarded("RT", run_marker_routes, world)
        guarded("R5", run_cli_fallback_record, world)
        guarded("AC2", run_cli_ac2, world)
        guarded("AC3", run_banner, world)
        guarded("PR", run_probe_rows, world)
        guarded("NT", run_notice_rows, world)
        guarded("NM", run_notice_main_rows, world)
        guarded("SSP", run_server_starts_process, world)
        guarded("AC7-8", run_ac7_ac8, world)
        guarded("BN", run_bench_rows, world)
        guarded("RV", run_review_followups, world)
        guarded("PT", run_process_table_real, world)
    finally:
        world.close()
        leftovers = [p for p in af.LEFTOVERS]
        check("cleanup: every sandbox this run created was removed", not leftovers, "left behind: %s" % leftovers)
        leaked = sorted(af.real_temp_codegraph_entries() - real_temp_before)
        check("isolation: the REAL temp folder (%s) gained no auto-improve-codegraph-* entry during this run" % af.REAL_TEMP,
              not leaked, "new entries: %s" % leaked)
        leaked_parent = sorted(af.real_parent_codegraph_entries() - real_parent_before)
        check("isolation: the REAL per-user session parent (%s) gained no auto-improve-codegraph-* entry during this run"
              % af.REAL_PARENT, not leaked_parent, "new entries: %s" % leaked_parent)
        after_snapshot = af.real_parent_snapshot()
        check("isolation: the REAL per-user session parent itself was not newly created and gained no entry of any name "
              "(a .tmp-* or a non-prefixed entry counts)", after_snapshot == real_snapshot_before,
              "before %r / after %r" % (real_snapshot_before, after_snapshot))


if __name__ == "__main__":
    try:
        run()
    except Exception:  # noqa: BLE001 - report any setup error as a failure, never as a crash
        traceback.print_exc()
        FAILED.append("test run raised")
    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed, {len(SKIPPED)} skipped, "
          f"{len(PASSED) + len(FAILED) + len(SKIPPED)} total")
    sys.exit(1 if FAILED else 0)
