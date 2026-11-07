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
  E-*            the retry escape: single use, per call, per session, cleared by the next prompt
  T-*            the tracker writes the session-keyed marker for explore / search / an unknown future tool name,
                 the marker survives a directory change, the reset hook clears it
  O-*            index ownership over real and fixture git layouts, in three helper modes (bound, missing, older)
  P-*            parity between the guard and the installer (server rule, index ownership)
  U-*            worktree_own_root unit rows
  X-*            the session-folder pruner, through the before_remove seam (X-2b and X-4 bite without file-symlink rights);
                 it lists the Per-user session parent only and never the system temp folder (issue #271, criterion 3)
  Q-*  (#271)    a planted folder in the shared temp folder opens no gate; the Per-user session parent rule (pure table,
                 every OS) and its problems on disk; fail closed (session-state-unusable, check-failed, announce,
                 retry-ticket-unwritten, link swap); the Foreign marker; the banner by reason; hook parity; the Hop proof
  U-H            review round: a hostile gitdir line (UNC, device path, no /.git/worktrees|modules/, 4096-byte cap) is
                 undecidable in the helper, the guard's inline copy, the bridge's inline copy and _git_file_kind
  S-*            review round: index verdict cached per cwd, the logged-<reason> flag after the record, 'X.' vs 'X'
  L-*            review round: no state write (availability.json, ticket-*, turn.json) goes through a hard link or symlink
"""

from __future__ import annotations

import importlib.util
import inspect
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


def run_hook(hook: Path, sb: af.Sandbox, project: Path, tool: str, tool_input: dict, session: str,
             cwd: Path | None = None, payload_extra: dict | None = None, extra_env: dict | None = None,
             raw: str | None = None, event: str = "PreToolUse") -> subprocess.CompletedProcess:
    """Run a hook as Claude Code does: JSON on stdin, the isolated environment, cwd = the payload cwd."""
    where = Path(cwd or project)
    where.mkdir(parents=True, exist_ok=True)
    payload = {"session_id": session, "cwd": str(where), "hook_event_name": event, "tool_name": tool,
               "tool_input": tool_input}
    if payload_extra:
        payload.update(payload_extra)
    return subprocess.run([sys.executable, "-B", str(hook)], input=raw if raw is not None else json.dumps(payload),
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
        self.tracker = installed[TRACKER_FILE]
        self.reset = installed[RESET_FILE]
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
            decision, why = guard.decide("Read", {"file_path": inside_src})
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
        # the next prompt clears the tickets
        s3 = sid()
        run_hook(w.guard, sb, project, "Read", read_cs(project), s3)
        reset = run_hook(w.reset, sb, project, "", {}, s3, event="UserPromptSubmit",
                         payload_extra={"prompt": "next question"})
        check("E-6: the reset hook exits 0", reset.returncode == 0, describe(reset))
        after = run_hook(w.guard, sb, project, "Read", read_cs(project), s3)
        check("E-6: after the next prompt the ticket is gone: the identical call is BLOCKED again", blocked(after),
              describe(after))
        tickets = list(pfolder(sb, s3).glob("ticket-*")) if pfolder(sb, s3).is_dir() else []
        check("E-6b: the reset hook deleted the session's tickets (only the fresh block's ticket may remain)",
              len(tickets) <= 1, "tickets: %s" % [t.name for t in tickets])
        # the ticket name carries a 64 hex call fingerprint
        s4 = sid()
        run_hook(w.guard, sb, project, "Read", read_cs(project), s4)
        names = [p.name for p in pfolder(sb, s4).glob("ticket-*")] \
            if pfolder(sb, s4).is_dir() else []
        check("E-7: a block writes ticket-<64 hex fingerprint> in the Session folder",
              len(names) == 1 and re.fullmatch(r"ticket-[0-9a-f]{64}", names[0]) is not None, "tickets: %s" % names)


# --------------------------------------------------------------------------------------------------------------
# T-*: tracker, marker, reset
# --------------------------------------------------------------------------------------------------------------
def run_marker(w: World) -> None:
    with af.Sandbox("cgt-") as sb:
        project = project_of(sb, "trk")
        cases = [
            ("codegraph_explore (with mcp_server in the payload)", "mcp__codegraph__codegraph_explore",
             {"query": "how does X work"}, {"mcp_server": "codegraph"}),
            ("codegraph_search", "mcp__codegraph__codegraph_search", {"query": "Thing"}, {}),
            ("an unknown future tool name (codegraph_zz_future_tool)", "mcp__codegraph__codegraph_zz_future_tool",
             {"anything": 1}, {}),
        ]
        for number, (label, tool, tool_input, extra) in enumerate(cases):
            project = project_of(sb, "trk-%d" % number)  # a fresh project per case: no leaked legacy sentinel
            session = sid()
            before = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
            check(f"T-1 control [{label}]: blocked before the tracker ran", blocked(before), describe(before))
            tracked = run_hook(w.tracker, sb, project, tool, tool_input, session, payload_extra=extra,
                               event="PostToolUse")
            check(f"T-1 [{label}]: the tracker exits 0", tracked.returncode == 0, describe(tracked))
            marker = pfolder(sb, session) / "turn.json"
            try:
                body = json.loads(marker.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                body = None
                reason = "no readable marker at %s (%s)" % (marker, exc)
            else:
                reason = ""
            check(f"T-1 [{label}]: the tracker writes turn.json {{ts, tool, summary, pid, writer, session}} in the session's "
                  "folder under the Per-user session parent",
                  isinstance(body, dict) and {"ts", "tool", "summary", "pid", "writer", "session"} <= set(body)
                  and body.get("tool") == tool, reason or repr(body))
            check(f"T-1 [{label}]: and stamps it writer=codegraph-turn-tracker, session=<the Session key>",
                  isinstance(body, dict) and body.get("writer") == "codegraph-turn-tracker"
                  and body.get("session") == session, repr(body))
            check(f"T-1 [{label}]: and writes NO legacy <cwd>/.claude/.codegraph-used-this-turn",
                  not (project / ".claude" / ".codegraph-used-this-turn").exists(), "legacy sentinel exists")
            after = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
            # The same Read was just blocked, so the retry ticket would also let it through: only the ABSENCE of an
            # `allowed (` line proves that the marker (step 2) did it. A retry-escape-used allow always prints one.
            check(f"T-1 [{label}]: the same Read is now allowed by the MARKER (no `allowed (` line: not the retry escape)",
                  silent_allow(after), describe(after))
            fresh = run_hook(w.guard, sb, project, "Read", read_cs(project), sid())
            check(f"T-1 [{label}]: and a FRESH session with the same Read is still BLOCKED [control]", blocked(fresh),
                  describe(fresh))

        # a tool that is not a CodeGraph tool writes nothing
        for tool in ("Bash", "mcp__other__codegraph_search"):
            session = sid()
            run_hook(w.tracker, sb, project, tool, {"command": "ls"}, session, event="PostToolUse")
            check(f"T-2: {tool} writes no marker",
                  not (pfolder(sb, session) / "turn.json").exists(), "marker exists")

        # the marker survives a directory change (cd / EnterWorktree)
        session = sid()
        here, there = project / "src", project / "elsewhere" / "deeper"
        run_hook(w.tracker, sb, project, "mcp__codegraph__codegraph_explore", {"query": "q"}, session, cwd=here,
                 event="PostToolUse")
        moved = run_hook(w.guard, sb, project, "Read", read_cs(project), session, cwd=there)
        check("T-3: a marker written with cwd=A allows a call made with cwd=B in the SAME session", allowed(moved),
              describe(moved))
        other = run_hook(w.guard, sb, project, "Read", read_cs(project), sid(), cwd=there)
        check("T-3: the marker is keyed to the session: ANOTHER session is BLOCKED [control]", blocked(other),
              describe(other))

        # the reset hook clears marker, tickets and the legacy sentinel
        session = sid()
        legacy = project / ".claude" / ".codegraph-used-this-turn"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text("legacy\n", encoding="utf-8")
        run_hook(w.tracker, sb, project, "mcp__codegraph__codegraph_search", {"query": "q"}, session,
                 event="PostToolUse")
        run_hook(w.reset, sb, project, "", {}, session, event="UserPromptSubmit", payload_extra={"prompt": "again"})
        check("T-4: the reset hook deletes this session's turn.json",
              not (pfolder(sb, session) / "turn.json").exists(), "turn.json still there")
        check("T-4: and a legacy <cwd>/.claude/.codegraph-used-this-turn if present", not legacy.exists(),
              "legacy sentinel still there")
        closed = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        check("T-4: the guard blocks the same Read again", blocked(closed), describe(closed))

        # the legacy sentinel no longer opens the gate (it is only cleaned up)
        session = sid()
        legacy.write_text("legacy\n", encoding="utf-8")
        proc = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        check("T-5: a legacy <cwd>/.claude/.codegraph-used-this-turn does NOT open the gate: BLOCKED", blocked(proc),
              describe(proc))
        legacy.unlink()
        # a subagent shares the parent's folder: the parent's marker lets the subagent through
        session = sid()
        run_hook(w.tracker, sb, project, "mcp__codegraph__codegraph_explore", {"query": "q"}, session,
                 event="PostToolUse")
        sub = run_hook(w.guard, sb, project, "Read", read_cs(project), session,
                       payload_extra={"agent_id": "a1", "agent_type": "general-purpose"})
        check("T-6: a subagent payload carries the PARENT session_id: the parent's marker allows it (step 2, before the "
              "agent_id escape of step 3: no `fail-open:subagent`)",
              allowed(sub) and "fail-open:subagent" not in sub.stderr, describe(sub))
        # T-7: the other direction, where the sharing matters: a SUBAGENT's tracker call (parent session_id plus
        # agent_id) opens the gate for the PARENT, which has no agent_id escape of its own.
        session = sid()
        before = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        check("T-7 control: the parent's Read is blocked before any CodeGraph call", blocked(before), describe(before))
        session = sid()
        tracked = run_hook(w.tracker, sb, project, "mcp__codegraph__codegraph_explore", {"query": "q"}, session,
                           payload_extra={"agent_id": "a1", "agent_type": "general-purpose"}, event="PostToolUse")
        parent = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        check("T-7: a tracker call made by a subagent writes the marker in the parent's folder: the parent's plain "
              "Read is allowed with no `allowed (` line", tracked.returncode == 0 and silent_allow(parent),
              describe(tracked) + " / " + describe(parent))
        stranger = run_hook(w.guard, sb, project, "Read", read_cs(project), sid())
        check("T-7: and another session is still BLOCKED [control]", blocked(stranger), describe(stranger))

        # the reset and tracker hook files never use is_junction / isjunction (Python 3.12+ only)
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
    spec = importlib.util.spec_from_file_location("codegraph_turn_reset_under_test", w.reset)
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
                    check("X-0: the reset hook defines prune_session_folders(temp_root, before_remove=...)", False,
                          "codegraph-turn-reset.py has no prune_session_folders")
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
    """The reset hook prunes the Per-user session parent (never the temp folder) once per session (Prune flag), as a hook
    process, on the first prompt only."""
    with af.Sandbox("cgy-") as sb:
        project = project_of(sb, "prune")
        session = sid()
        first_old = old_session(af.session_parent(sb.home), "first-old")
        done = run_hook(w.reset, sb, project, "", {}, session, event="UserPromptSubmit", payload_extra={"prompt": "one"})
        check("X-8: the first prompt of a session exits 0", done.returncode == 0, describe(done))
        check("X-8: the first prompt prunes an old, known-file session folder of another session",
              not first_old.exists(), "old folder still exists")
        check("X-8: and leaves a `pruned` flag in this session's folder",
              (pfolder(sb, session) / "pruned").exists(), "no pruned flag")
        second_old = old_session(af.session_parent(sb.home), "second-old")
        run_hook(w.reset, sb, project, "", {}, session, event="UserPromptSubmit", payload_extra={"prompt": "two"})
        check("X-8: the second prompt of the SAME session does not prune again", second_old.is_dir(),
              "pruned a second time")
        third = sid()
        run_hook(w.reset, sb, project, "", {}, third, event="UserPromptSubmit", payload_extra={"prompt": "three"})
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
        run_hook(w.tracker, sb, project, "mcp__codegraph__codegraph_explore", {"query": "q"}, base_id + ".",
                 event="PostToolUse")
        other = run_hook(w.guard, sb, project, "Read", read_cs(project), base_id)
        check("S-3: the marker of session 'X.' does not open the gate of session 'X' (no folder shared once Windows "
              "strips the dot)", blocked(other), describe(other))
        run_hook(w.tracker, sb, project, "mcp__codegraph__codegraph_explore", {"query": "q"}, base_id + "k",
                 event="PostToolUse")
        own = run_hook(w.guard, sb, project, "Read", read_cs(project), base_id + "k")
        check("S-3 [control]: a plain session id keeps working: its own marker opens its own gate", silent_allow(own),
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
        session = sid()
        run_hook(w.tracker, sb, project, "mcp__codegraph__codegraph_explore", {"query": "q"}, session,
                 event="PostToolUse")
        check("L control: the tracker writes turn.json", (pfolder(sb, session) / "turn.json").is_file(),
              "no turn.json")
        for kind_label, kind in kinds:
            for state_name in ("availability.json", "ticket", "turn.json"):
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
                if state_name == "turn.json":
                    proc = run_hook(w.tracker, sb, project, "mcp__codegraph__codegraph_explore", {"query": "q"}, session,
                                    event="PostToolUse")
                else:
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
    """Item 11 (normalise, then check) and item 14 (the four copies of _hop_allowed agree; since issue #271 the SIX copies
    of _remote_host and of _own_spellings agree: ``six`` = the four plus the codegraph tracker and reset hook)."""
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

    # item 14: one list of inputs through the copies (_remote_host: six, since issue #271)
    for target in PARITY_TARGETS:
        answers = {}
        for label, mod in six:
            try:
                answers[label] = mod._remote_host(target)
            except Exception as exc:  # noqa: BLE001
                answers[label] = "raised %r" % (exc,)
        check(f"W-14 parity: the six copies of _remote_host (helper, guard, bridge, installer, tracker, reset) agree on {target!r}",
              len(answers) == 6 and len({repr(v) for v in answers.values()}) == 1, repr(answers))
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
        if len(set(answers.values())) != 1 or len(answers) != 6:
            differing.append((path, answers))
    check(f"W-14 parity: the six copies of _own_spellings (helper, guard, bridge, installer, tracker, reset) agree on "
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
    tracker_mod = load_module(w.tracker, "codegraph_tracker_round_three")
    reset_mod = load_module(w.reset, "codegraph_reset_round_three")
    run_hop_rows(mods, mods + [("tracker", tracker_mod), ("reset", reset_mod)])
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
                                                        {"session_id": sid(), "cwd": str(project / "src")})
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
# W-14: the reset hook's ticket pattern has an escaped dot
# --------------------------------------------------------------------------------------------------------------
def run_ticket_pattern(w: World) -> None:
    with af.Sandbox("cgt-") as sb:
        with mock.patch.dict(os.environ, af.isolated_env(sb.home, sb.tmp), clear=True):
            saved = tempfile.tempdir
            tempfile.tempdir = str(sb.tmp)
            try:
                mod = load_reset_module(sb, w)
                folder = sb.tmp / (af.CODEGRAPH_SESSION_PREFIX + "w14")
                folder.mkdir()
                names = ("turn.json", "ticket-" + "b" * 64, ".tmp-0123456789abcdef", "xtmp-0123456789abcdef",
                         "Ttmp-0123456789abcdef", "-tmp-0123456789abcdef", "availability.json")
                for name in names:
                    (folder / name).write_text("{}\n", encoding="utf-8")
                mod._delete_marker_and_tickets(str(folder))
                left = sorted(p.name for p in folder.iterdir())
                check("W-14 control: the next prompt clears the marker, a real ticket and a real `.tmp-<16 hex>` sibling",
                      "turn.json" not in left and ("ticket-" + "b" * 64) not in left and ".tmp-0123456789abcdef" not in left,
                      "left: %s" % left)
                check("W-14: a file named `xtmp-<16 hex>` is NOT treated as a ticket or temp file (the dot is escaped)",
                      "xtmp-0123456789abcdef" in left, "deleted; left: %s" % left)
                check("W-14: nor `Ttmp-<16 hex>` or `-tmp-<16 hex>`",
                      "Ttmp-0123456789abcdef" in left and "-tmp-0123456789abcdef" in left, "left: %s" % left)
                check("W-14 control: availability.json is not a ticket and stays", "availability.json" in left, "left: %s" % left)
            finally:
                tempfile.tempdir = saved


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
               no_access: tuple = (), fake_uid: int | None = None) -> tuple:
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
    body = {"session_id": session, "cwd": str(project), "hook_event_name": "PreToolUse", "tool_name": "Read",
            "tool_input": read_cs(project)}
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
        ok = run_hook(w.guard, sb, project, "Read", read_cs(project), mine)
        check("Q-2 [control]: the same marker under the Per-user session parent opens the gate (silent allow)",
              silent_allow(ok), describe(ok))
        before = sorted(p.name for p in sb.tmp.iterdir())
        session = sid()
        run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        run_hook(w.tracker, sb, project, "mcp__codegraph__codegraph_explore", {"query": "q"}, session,
                 event="PostToolUse")
        run_hook(w.reset, sb, project, "", {}, session, event="UserPromptSubmit", payload_extra={"prompt": "next"})
        after = sorted(p.name for p in sb.tmp.iterdir())
        check("Q-2: no hook creates or removes anything in the system temp folder (guard, tracker, reset)",
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
        done = run_hook(w.reset, sb, project, "", {}, session, event="UserPromptSubmit", payload_extra={"prompt": "one"})
        check("Q-3: the reset hook exits 0 on a first prompt", done.returncode == 0, describe(done))
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
            check("Q-3: the reset hook defines prune_session_folders", False, "not defined")
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
            run_hook(w.reset, sb, project, "", {}, sid(), event="UserPromptSubmit", payload_extra={"prompt": "two"})
            check("Q-3: a folder owned by another user is kept", foreign.is_dir(), "foreign-owned folder was removed")


# ---- criterion 4: the Foreign marker opens the gate and is logged once ----------------------------------------------
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

        cases = [("an unstamped (0.15.2 shape) marker", "missing-stamp", lambda s: af.write_marker(parent, s, stamped=False)),
                 ("a marker stamped for another session", "other-session", other_session),
                 ("an unreadable marker", "unreadable", unreadable)]
        for number, (label, cause, setup) in enumerate(cases):
            project = project_of(sb, "fm-%d" % number)
            make_logs(project)
            session = sid()
            setup(session)
            first = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
            second = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
            check(f"Q-4 [{label}]: a Foreign marker still opens the gate on both calls", allowed(first) and allowed(second)
                  and not blocked(first) and not blocked(second), describe(first) + " / " + describe(second))
            records = events(project, "foreign-marker")
            check(f"Q-4 [{label}]: exactly ONE foreign-marker record after two calls", len(records) == 1,
                  "records: %r" % records)
            check(f"Q-4 [{label}]: and the record names the cause {cause}", bool(records) and cause in json.dumps(records[0]),
                  "records: %r" % records)
        project = project_of(sb, "fm-own")
        make_logs(project)
        session = sid()
        af.write_marker(parent, session)
        own = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        check("Q-4 [control]: a stamped OWN marker opens the gate silently", silent_allow(own), describe(own))
        check("Q-4 [control]: and logs no foreign-marker record", events(project, "foreign-marker") == [],
              repr(events(project, "foreign-marker")))


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
    paths = [w.guard, w.tracker, w.reset]
    differ = parity_differences(paths)
    check("Q-parity: resolve_session_parent, _create_parent, session_folder_problem, _base_shown, session_parent_base, "
          "_remote_host and _own_spellings are textually identical in the guard, the tracker and the reset hook",
          differ == [], "differ or missing: %s" % differ)
    check("Q-parity [round 3]: _is_link_stat (code, docstring excluded) and the constants _LOCAL_DEVICE_HOST_RE, PARENT_NAME, "
          "_REPARSE_POINT and PARENT_PROBLEMS (round 4) are identical in the three hooks",
          not [n for n in differ if n in SHARED_NODOC_FUNCTIONS + SHARED_CONSTANTS],
          "differ or missing: %s" % differ)
    # the row must BITE: a throwaway copy of the tracker with one check edited out is reported, then deleted with its sandbox
    with af.Sandbox("cgqpar-") as sb:
        mutations = {"resolve_session_parent": ('"open-mode"', '"open-modes"'),
                     "session_folder_problem": ('"session-foreign-owner"', '"session-foreign"'),
                     "_create_parent": ('"cannot-create"', '"cannot-created"'),
                     "_is_link_stat": ("& _REPARSE_POINT", "& 0"),
                     "_LOCAL_DEVICE_HOST_RE": ('r"\?[a-z]:"', 'r"\?[a-y]:"'),
                     "PARENT_NAME": ('"auto-improve-codegraph"', '"auto-improve-codegraphs"'),
                     "_REPARSE_POINT": ("0x400", "0x401"),
                     "PARENT_PROBLEMS": ('"open-mode"', '"open-modes"')}
        for fn_name, (old, new) in mutations.items():
            text = w.tracker.read_text(encoding="utf-8")
            body = function_source(w.tracker, fn_name) or constant_source(w.tracker, fn_name) or ""
            if not body or old not in body:
                check(f"Q-parity [mutation proof {fn_name}]: the mutation anchor exists in the tracker's copy", False,
                      "anchor %r not found in %s" % (old, fn_name))
                continue
            copy = sb.root / ("mut-" + fn_name + ".py")
            copy.write_text(text.replace(body, body.replace(old, new, 1), 1), encoding="utf-8")
            found = parity_differences([w.guard, copy, w.reset])
            check(f"Q-parity [mutation proof]: editing {fn_name} in one copy makes the parity row report it",
                  fn_name in found, "reported: %s" % found)


def run_parent_rule_table(w: World) -> None:
    hooks = [("guard", w.guard), ("tracker", w.tracker), ("reset", w.reset)]
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
            # the tracker writes no marker and says so; the reset hook prunes nothing and still removes the legacy sentinel
            tracked = run_hook(w.tracker, sb, project, "mcp__codegraph__codegraph_explore", {"query": "q"}, sid(),
                               extra_env=extra, event="PostToolUse")
            check(f"Q-9 [{label}]: the tracker exits 0, writes no marker and prints that the gate stays shut",
                  tracked.returncode == 0 and "the gate stays shut" in tracked.stderr and problem in tracked.stderr
                  and list(sb.root.rglob("turn.json")) == [], describe(tracked))
            legacy = project / ".claude" / ".codegraph-used-this-turn"
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text("legacy\n", encoding="utf-8")
            bait = old_session(link_target, "bait") if link_target is not None else None
            reset = run_hook(w.reset, sb, project, "", {}, sid(), extra_env=extra, event="UserPromptSubmit",
                             payload_extra={"prompt": "next"})
            check(f"Q-9 [{label}]: the reset hook exits 0, prints the same line, and removes the legacy sentinel",
                  reset.returncode == 0 and "the gate stays shut" in reset.stderr and not legacy.exists(), describe(reset))
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
        tracker_mod = load_module(w.tracker, "codegraph_tracker_checkfailed")
        code, err = run_inproc(tracker_mod, {"session_id": sid(), "cwd": str(project), "tool_name":
                               "mcp__codegraph__codegraph_explore", "tool_input": {"query": "q"}}, env, lstat_for=parent)
        check("Q-9f: the tracker writes no marker (exit 0) and prints that the gate stays shut",
              code == 0 and "the gate stays shut" in err and list(parent.rglob("turn.json")) == [old_in_parent / "turn.json"], "exit=%s %r" % (code, err))
        legacy = project / ".claude" / ".codegraph-used-this-turn"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text("legacy\n", encoding="utf-8")
        reset_mod = load_module(w.reset, "codegraph_reset_checkfailed")
        code, err = run_inproc(reset_mod, {"session_id": sid(), "cwd": str(project), "prompt": "next"}, env, lstat_for=parent)
        check("Q-9f: the reset hook deletes and prunes nothing under the parent (exit 0), and removes the legacy sentinel",
              code == 0 and old_in_parent.is_dir() and not legacy.exists(), "exit=%s old exists=%s legacy=%s %r"
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
    for name, path in (("guard", w.guard), ("tracker", w.tracker), ("reset", w.reset)):
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
            tracker_mod = load_module(w.tracker, "codegraph_tracker_matrix")
            code, err = run_inproc(tracker_mod, {"session_id": session, "cwd": str(project), "tool_name":
                                   "mcp__codegraph__codegraph_explore", "tool_input": {"query": "q"}}, env, stat_over=over,
                                   no_access=denied, fake_uid=uid)
            check(f"T-H1 [{label}]: the tracker writes no marker (exit 0) and prints that the gate stays shut",
                  code == 0 and "the gate stays shut" in err and not (folder / "turn.json").exists(), "exit=%s %r" % (code, err))
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


# ---- review fix round T-L1: the Foreign marker's stderr line, and the flag only after the record ---------------------------
def run_foreign_marker_order(w: World) -> None:
    with af.Sandbox("cgqfo-") as sb:
        parent = af.session_parent(sb.home)
        guard_mod = load_module(w.guard, "codegraph_first_guard_foreign_order")
        line = "the gate opened from a turn marker this session's tracker did not write"
        for label, returns, flag_expected in (("the record is written", True, True), ("the record could not be written", False, False)):
            project = project_of(sb, "fo-%s" % returns)
            make_logs(project)
            session = sid()
            af.write_marker(parent, session, stamped=False)
            flag = af.session_folder(parent, session) / "logged-foreign-marker"
            seen: list = []

            def spy(**kwargs):
                seen.append((kwargs.get("event"), flag.exists()))
                return returns
            env = af.isolated_env(sb.home, sb.tmp, project)
            with mock.patch.object(guard_mod, "log_event", spy):
                code, err = run_inproc(guard_mod, guard_payload(project, session), env)
            check(f"T-L1 [{label}]: the gate opens (exit 0) and ONE stderr line says the marker was not written by this "
                  "session's tracker, naming the cause", code == 0 and err.count(line) == 1 and "(missing-stamp)" in err,
                  "exit=%s %r" % (code, err))
            check(f"T-L1 [{label}]: the foreign-marker record is written while the flag does NOT exist yet",
                  seen == [("foreign-marker", False)], repr(seen))
            check(f"T-L1 [{label}]: and the flag exists afterwards only when the record did not fail", flag.exists() is flag_expected,
                  "flag exists=%s" % flag.exists())
            if flag_expected:
                with mock.patch.object(guard_mod, "log_event", spy):
                    code, err = run_inproc(guard_mod, guard_payload(project, session), env)
                check("T-L1: the second call prints no foreign-marker line and writes no second record",
                      code == 0 and line not in err and len(seen) == 1, "exit=%s %r seen=%r" % (code, err, seen))
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


# --------------------------------------------------------------------------------------------------------------
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
        guarded("Q-foreign", run_foreign_marker, world)
        guarded("Q-rule", run_parent_rule_table, world)
        guarded("Q-unusable", run_unusable_parent, world)
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
        guarded("R2-foreign", run_foreign_marker_order, world)
        guarded("R2-ambiguous", run_ambiguous_after_unwritten, world)
        guarded("R2-bridge", run_bridge_without_own_root, world)
        guarded("R2-snapshot", run_real_parent_snapshot_selfcheck, world)
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
