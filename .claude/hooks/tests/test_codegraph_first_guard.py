#!/usr/bin/env python3
"""
test_codegraph_first_guard.py -- the CodeGraph-first gate: issue #612 (a read of a non-source file outside the
project is not gated) and issue #259 (the gate fails open when CodeGraph is provably unavailable, has a
single-use retry escape, keys its turn marker to the session, and never advises the shell).

House style: plain runnable script, NO pytest. check(name, cond, detail) accumulator,
PASS/FAIL/SKIP summary, non-zero exit on any failure (a skip never fails the run and is never a pass).

    py -3 .claude/hooks/tests/test_codegraph_first_guard.py

ISOLATION (contract 2026-11-05-codegraph-guard-fail-open, FM 1): every row that reads server state or writes a Session
folder runs with HOME, USERPROFILE and CLAUDE_CONFIG_DIR at a fixture home folder and TMP, TEMP at a fixture temp
folder, and a fresh session_id. The developer's real home and temp folder are never read or written.

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
  X-*            the temp folder pruner, through the before_remove seam (X-2b and X-4 bite without file-symlink rights)
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

        # step 0: an unusable Session folder allows with a logged reason
        project = project_of(sb, "step0")
        make_logs(project)
        session = sid()
        target = sb.root / "step0-link-target"
        target.mkdir()
        link = af.session_folder(sb.tmp, session)
        if af.make_dir_link(link, target):
            proc = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
            check("step 0: a Session folder that is a link allows, reason fail-open:state-unwritable",
                  allowed(proc, "fail-open:state-unwritable"), describe(proc))
            check("step 0: and nothing was written through the link", not any(target.iterdir()),
                  "target holds: %s" % [p.name for p in target.iterdir()])
            try:
                os.rmdir(str(link))
            except OSError:
                pass
        else:
            skip("step 0: a Session folder that is a link", "the OS refused to create a folder link")
        session = sid()
        af.session_folder(sb.tmp, session).write_text("not a folder\n", encoding="utf-8")
        proc = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        check("step 0: a Session folder path that is a plain FILE allows, reason fail-open:state-unwritable",
              allowed(proc, "fail-open:state-unwritable"), describe(proc))

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

        # step 7: a ticket that cannot be written allows, reason fail-open:state-unwritable (a folder sits in the
        # ticket's place, so the Session folder stays usable and only the ticket write fails)
        project = project_of(sb, "step7")
        make_logs(project)
        guard_mod = load_module(w.guard, "codegraph_first_guard_step7")
        session = sid()
        folder = af.session_folder(sb.tmp, session)
        folder.mkdir()
        (folder / ("ticket-" + guard_mod.call_fingerprint("Read", read_cs(project)))).mkdir()
        proc = run_hook(w.guard, sb, project, "Read", read_cs(project), session)
        check("step 7: a ticket that cannot be written allows, reason fail-open:state-unwritable (never a block that "
              "cannot be retried)", allowed(proc, "fail-open:state-unwritable") and not blocked(proc), describe(proc))
        project = project_of(sb, "step7-twin")
        proc = run_hook(w.guard, sb, project, "Read", read_cs(project), sid())
        check("step 7 [control]: the same call with a writable Session folder is BLOCKED", blocked(proc), describe(proc))


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
        tickets = list(af.session_folder(sb.tmp, s3).glob("ticket-*")) if af.session_folder(sb.tmp, s3).is_dir() else []
        check("E-6b: the reset hook deleted the session's tickets (only the fresh block's ticket may remain)",
              len(tickets) <= 1, "tickets: %s" % [t.name for t in tickets])
        # the ticket name carries a 64 hex call fingerprint
        s4 = sid()
        run_hook(w.guard, sb, project, "Read", read_cs(project), s4)
        names = [p.name for p in af.session_folder(sb.tmp, s4).glob("ticket-*")] \
            if af.session_folder(sb.tmp, s4).is_dir() else []
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
            marker = af.session_folder(sb.tmp, session) / "turn.json"
            try:
                body = json.loads(marker.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                body = None
                reason = "no readable marker at %s (%s)" % (marker, exc)
            else:
                reason = ""
            check(f"T-1 [{label}]: the tracker writes turn.json {{ts, tool, summary, pid}} in the session's folder",
                  isinstance(body, dict) and {"ts", "tool", "summary", "pid"} <= set(body) and body.get("tool") == tool,
                  reason or repr(body))
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
                  not (af.session_folder(sb.tmp, session) / "turn.json").exists(), "marker exists")

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
              not (af.session_folder(sb.tmp, session) / "turn.json").exists(), "turn.json still there")
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
        older = types.SimpleNamespace(WORKTREE_OWN_ROOT_NATIVE=True, worktree_own_root=pp.worktree_own_root,
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
    """The reset hook prunes once per session (Prune flag), as a hook process, on the first prompt only."""
    with af.Sandbox("cgy-") as sb:
        project = project_of(sb, "prune")
        session = sid()
        first_old = old_session(sb.tmp, "first-old")
        done = run_hook(w.reset, sb, project, "", {}, session, event="UserPromptSubmit", payload_extra={"prompt": "one"})
        check("X-8: the first prompt of a session exits 0", done.returncode == 0, describe(done))
        check("X-8: the first prompt prunes an old, known-file session folder of another session",
              not first_old.exists(), "old folder still exists")
        check("X-8: and leaves a `pruned` flag in this session's folder",
              (af.session_folder(sb.tmp, session) / "pruned").exists(), "no pruned flag")
        second_old = old_session(sb.tmp, "second-old")
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
        folder = af.session_folder(sb.tmp, session)
        check("L control: the guard writes availability.json and a ticket-<64 hex> into the Session folder",
              blocked(done) and (folder / "availability.json").is_file() and len(list(folder.glob("ticket-*"))) == 1,
              describe(done) + " / " + str(sorted(p.name for p in folder.glob("*"))))
        session = sid()
        run_hook(w.tracker, sb, project, "mcp__codegraph__codegraph_explore", {"query": "q"}, session,
                 event="PostToolUse")
        check("L control: the tracker writes turn.json", (af.session_folder(sb.tmp, session) / "turn.json").is_file(),
              "no turn.json")
        for kind_label, kind in kinds:
            for state_name in ("availability.json", "ticket", "turn.json"):
                session = sid()
                folder = af.session_folder(sb.tmp, session)
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


def run_hop_rows(mods) -> None:
    """Item 11 (normalise, then check) and item 14 (the four copies agree)."""
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

    # item 14: one list of inputs through the four copies
    for target in PARITY_TARGETS:
        answers = {}
        for label, mod in mods:
            try:
                answers[label] = mod._remote_host(target)
            except Exception as exc:  # noqa: BLE001
                answers[label] = "raised %r" % (exc,)
        check(f"W-14 parity: the four copies of _remote_host agree on {target!r}",
              len({repr(v) for v in answers.values()}) == 1, repr(answers))
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
        for label, mod in mods:
            try:
                answers[label] = repr(tuple(mod._own_spellings(path)))
            except Exception as exc:  # noqa: BLE001
                answers[label] = "raised %r" % (exc,)
        if len(set(answers.values())) != 1:
            differing.append((path, answers))
    check(f"W-14 parity: the four copies of _own_spellings agree on {len(spelling_inputs)} inputs",
          not differing, "differ on: %r" % (differing[:3],))


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
    run_hop_rows(mods)
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
def guarded(name: str, fn, *args) -> None:
    """One section: a crash inside it is ONE failing check naming the section, and the runner goes on."""
    try:
        fn(*args)
    except Exception:  # noqa: BLE001
        check(f"section {name} ran to the end without an error", False, traceback.format_exc())


def run() -> None:
    real_temp_before = af.real_temp_codegraph_entries()
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
    finally:
        world.close()
        leftovers = [p for p in af.LEFTOVERS]
        check("cleanup: every sandbox this run created was removed", not leftovers, "left behind: %s" % leftovers)
        leaked = sorted(af.real_temp_codegraph_entries() - real_temp_before)
        check("isolation: the REAL temp folder (%s) gained no auto-improve-codegraph-* entry during this run" % af.REAL_TEMP,
              not leaked, "new entries: %s" % leaked)


if __name__ == "__main__":
    try:
        run()
    except Exception:  # noqa: BLE001 - report any setup error as a failure, never as a crash
        traceback.print_exc()
        FAILED.append("test run raised")
    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed, {len(SKIPPED)} skipped, "
          f"{len(PASSED) + len(FAILED) + len(SKIPPED)} total")
    sys.exit(1 if FAILED else 0)
