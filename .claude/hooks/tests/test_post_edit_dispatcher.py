#!/usr/bin/env python3
"""
test_post_edit_dispatcher.py -- INV-O4 of the hook-server-modes contract's amendment 2026-10-09
("Plugin is the source of its hooks; fewer gates"), sub-task 23.

WHAT IS PINNED DOWN
-------------------
The plugin ships ONE asynchronous PostToolUse hook, .claude/hooks/post-edit-dispatcher.py, in place of
four. It runs the four trackers inside its own process, in this order, with the same input bytes:

    integration-check.py, critic-verdict-tracker.py, contract-status-watcher.py,
    journal-post-approval-tracker.py

(The order is the one this repository's settings.json registers today and the contract's table lists.)

  * One check's failure never stops the next one.
  * Its single output joins each check's context and plain output, in that order, each prefixed with
    the check's file name. It exits 0. A check's error output passes through.
  * Each check's own off switch still works (CLAUDE_INTEGRATION_CHECK, CLAUDE_ACCURACY_TRACKER).
  * The state the checks leave behind equals what the four standalone runs leave behind.

HOW IT IS TESTED
----------------
An inline corpus of seven edits (a contract carrying a Critique verdict, a status change to
rejected, a verdict change, a JOURNAL.md seed, a JOURNAL.md post-approval entry, a backend DTO edit
that integration-check reports on, a plain .md edit) is replayed twice from the same starting state:
once through the four standalone hooks in order, once through the dispatcher. HOME / USERPROFILE and
TEMP / TMP point at temporary folders, and CLAUDE_PROJECT_DIR at a temporary fixture project, so the
real machine's state is never read or written. Then the dispatcher's outputs and the two final state
snapshots are compared.

The comparison itself is exercised by CONTROLS that must reject a wrong dispatcher: one that runs
only the first check, one with the checks out of order, one that drops an output. A test that
cannot fail proves nothing (the same lesson as the hook suites).

Run:
    py -3 .claude/hooks/tests/test_post_edit_dispatcher.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HOOKS = ROOT / ".claude" / "hooks"
DISPATCHER_NAME = "post-edit-dispatcher.py"
CHECK_ORDER = ["integration-check.py", "critic-verdict-tracker.py", "contract-status-watcher.py",
               "journal-post-approval-tracker.py"]

_failures: list[str] = []
_passes = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passes
    if cond:
        _passes += 1
        print("  PASS  %s" % name)
    else:
        _failures.append(name)
        print("  FAIL  %s%s" % (name, ("\n        " + detail.replace("\n", "\n        ")) if detail else ""))


_TMP = tempfile.TemporaryDirectory(prefix="dispatcher-")
BASE = Path(_TMP.name)
_n = [0]


def fresh(label: str) -> Path:
    _n[0] += 1
    path = BASE / ("%03d-%s" % (_n[0], label))
    path.mkdir(parents=True)
    return path


# ---------------------------------------------------------------------------
# The fixture: one project, one home, one temp folder, rebuilt from nothing before every replay so
# both replays start from the SAME state at the SAME paths (a state file keys on absolute paths).
# ---------------------------------------------------------------------------
ENV_ROOT = BASE / "env"
CONTRACT_TEXT = """# Concept Contract -- probe

**Status:** approved

**Files to touch:**

- `src/probe/Thing.cs`

## Critique

**Verdict:** clean
"""
JOURNAL_SEED = """# Journal

### 2026-01-01 -- an old entry
- **Trigger:** manual
- **Source contract:** N/A
"""
JOURNAL_NEW = """
### 2026-02-02 -- a post-approval entry
- **Trigger:** post-approval
- **Source contract:** `%s`
"""


class Env:
    def __init__(self):
        if ENV_ROOT.exists():
            shutil.rmtree(ENV_ROOT, ignore_errors=True)
        self.project = ENV_ROOT / "project"
        self.home = ENV_ROOT / "home"
        self.temp = ENV_ROOT / "temp"
        self.cwd = ENV_ROOT / "cwd"
        for d in (self.project / ".claude" / "concepts", self.project / ".claude" / "hooks",
                  self.project / ".claude" / "registries", self.project / ".claude" / "logs",
                  self.home, self.temp, self.cwd):
            d.mkdir(parents=True, exist_ok=True)
        # the project's own integration markers (project-first, INV-O3); no hook reads the template here
        (self.project / ".claude" / "hooks" / "integration-check.rules.json").write_text(
            json.dumps({"backend_markers": ["srv/Zeta."], "frontend_markers": ["web/zeta/"]}), encoding="utf-8")
        self.contract = self.project / ".claude" / "concepts" / "2026-01-01-probe.md"
        self.journal = self.project / ".claude" / "registries" / "JOURNAL.md"
        self.dto = self.project / "srv" / "Zeta.Api" / "Controllers" / "FooController.cs"
        self.readme = self.project / "README.md"

    def env(self, plugin_root: Path, extra: dict | None = None) -> dict:
        e = dict(os.environ)
        for key in ("CLAUDE_INTEGRATION_CHECK", "CLAUDE_ACCURACY_TRACKER", "CLAUDE_PROJECT_DIR"):
            e.pop(key, None)
        e.update({"CLAUDE_PROJECT_DIR": str(self.project), "CLAUDE_PLUGIN_ROOT": str(plugin_root),
                  "HOME": str(self.home), "USERPROFILE": str(self.home), "TEMP": str(self.temp),
                  "TMP": str(self.temp), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"})
        e.update(extra or {})
        return e


def corpus(env: Env):
    """[(label, mutate(), file_path)]. Each mutate() applies the edit to the fixture before the hooks fire."""
    def write(path: Path, text: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def contract_clean():
        write(env.contract, CONTRACT_TEXT)

    def contract_rejected():
        write(env.contract, CONTRACT_TEXT.replace("**Status:** approved", "**Status:** rejected"))

    def contract_blockers():
        write(env.contract, CONTRACT_TEXT.replace("**Status:** approved", "**Status:** rejected")
              .replace("**Verdict:** clean", "**Verdict:** blockers-found"))

    def journal_seed():
        write(env.journal, JOURNAL_SEED)

    def journal_post_approval():
        write(env.journal, JOURNAL_SEED + (JOURNAL_NEW % str(env.contract).replace("\\", "/")))

    def dto_edit():
        write(env.dto, "public class FooController {}\n")

    def plain_md():
        write(env.readme, "# readme\n")

    return [
        ("a contract carrying a clean Critique verdict", contract_clean, env.contract),
        ("a status change from approved to rejected", contract_rejected, env.contract),
        ("a Critique verdict change to blockers-found", contract_blockers, env.contract),
        ("a JOURNAL.md seed", journal_seed, env.journal),
        ("a JOURNAL.md post-approval entry", journal_post_approval, env.journal),
        ("a backend DTO edit integration-check reports on", dto_edit, env.dto),
        ("a plain .md edit", plain_md, env.readme),
    ]


def payload_bytes(path: Path) -> bytes:
    return json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Edit",
                       "tool_input": {"file_path": str(path)}}).encode("utf-8")


# ---------------------------------------------------------------------------
# Running and reading
# ---------------------------------------------------------------------------
def run_py(script: Path, data: bytes, env: dict, cwd: Path):
    return subprocess.run([sys.executable, str(script)], input=data, capture_output=True, env=env,
                          cwd=str(cwd), timeout=120)


def dec(b: bytes) -> str:
    return (b or b"").decode("utf-8", "replace")


def flatten(stdout: str) -> str:
    """Every string a hook printed: a JSON object's string leaves (the context), or the plain text."""
    s = stdout.strip()
    if not s:
        return ""
    try:
        obj = json.loads(s)
    except ValueError:
        return s
    out: list[str] = []

    def walk(o):
        if isinstance(o, str):
            out.append(o)
        elif isinstance(o, dict):
            for k, v in o.items():
                if k != "hookEventName":
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(obj)
    return "\n".join(out)


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


_TS = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")


def snapshot(env: Env) -> dict:
    """Every state file the four checks can leave behind, timestamps blanked."""
    found: dict[str, str] = {}
    spots = [(env.home / ".claude" / "state", "home-state"),
             (env.project / ".claude" / "state", "project-state"),
             (env.temp, "temp")]
    for folder, tag in spots:
        if folder.is_dir():
            for p in sorted(folder.rglob("*.json")):
                found["%s/%s" % (tag, p.relative_to(folder).as_posix())] = _TS.sub("<ts>", p.read_text(
                    encoding="utf-8", errors="replace"))
    ledger = env.project / ".claude" / "contract-accuracy.json"
    if ledger.is_file():
        found["project/contract-accuracy.json"] = _TS.sub("<ts>", ledger.read_text(encoding="utf-8", errors="replace"))
    return found


def replay_standalone(plugin_root: Path, extra: dict | None = None):
    """The four standalone hooks, in order, for every edit of the corpus."""
    env = Env()
    hooks = plugin_root / ".claude" / "hooks"
    records = []
    for label, mutate, path in corpus(env):
        mutate()
        data = payload_bytes(path)
        per_check = []
        for name in CHECK_ORDER:
            p = run_py(hooks / name, data, env.env(plugin_root, extra), env.cwd)
            per_check.append((name, p.returncode, dec(p.stdout), dec(p.stderr)))
        records.append((label, per_check))
    return records, snapshot(env)


def replay_dispatcher(plugin_root: Path, extra: dict | None = None):
    """The dispatcher once per edit of the corpus."""
    env = Env()
    script = plugin_root / ".claude" / "hooks" / DISPATCHER_NAME
    records = []
    for label, mutate, path in corpus(env):
        mutate()
        p = run_py(script, payload_bytes(path), env.env(plugin_root, extra), env.cwd)
        records.append((label, p.returncode, dec(p.stdout), dec(p.stderr)))
    return records, snapshot(env)


def verify(standalone, dispatcher, tolerate_failing=()) -> list[str]:
    """Problems found comparing a dispatcher replay with the standalone replay. [] means they agree."""
    problems: list[str] = []
    s_records, s_snap = standalone
    d_records, d_snap = dispatcher
    if len(s_records) != len(d_records):
        return ["the replays have different lengths"]
    for (label, per_check), (_l, rc, out, err) in zip(s_records, d_records):
        if rc != 0:
            problems.append("%s: the dispatcher exited %s, not 0" % (label, rc))
        text = norm(flatten(out))
        cursor = 0
        for name, _rc, c_out, c_err in per_check:
            if name in tolerate_failing:
                continue
            expected = norm(flatten(c_out))
            if not expected:
                continue
            at = text.find(name, cursor)
            if at < 0:
                problems.append("%s: no output prefixed with %s (searched from %d)" % (label, name, cursor))
                continue
            body = text.find(expected, at)
            if body < 0:
                problems.append("%s: %s's output %r is not found after its prefix" % (label, name, expected[:80]))
                continue
            cursor = body + len(expected)
    if s_snap != d_snap:
        keys = sorted(set(s_snap) | set(d_snap))
        differing = [k for k in keys if s_snap.get(k) != d_snap.get(k)]
        problems.append("state files differ from the standalone runs: %s" % differing)
    return problems


def the_dispatcher_exists() -> bool:
    return (HOOKS / DISPATCHER_NAME).is_file()


# ---------------------------------------------------------------------------
# 0. Existence and shape
# ---------------------------------------------------------------------------
print("\nINV-O4  the dispatcher exists and names the four checks in order")
check("%s exists in the plugin's hooks folder" % DISPATCHER_NAME, the_dispatcher_exists(),
      "missing: %s" % (HOOKS / DISPATCHER_NAME))
src = (HOOKS / DISPATCHER_NAME).read_text(encoding="utf-8", errors="replace") if the_dispatcher_exists() else ""
positions = [src.find(name) for name in CHECK_ORDER]
check("its source names the four checks, each once or more, in the order %s" % ", ".join(CHECK_ORDER),
      bool(src) and all(p >= 0 for p in positions) and positions == sorted(positions),
      "first positions: %r" % positions)
check("the four standalone checks stay in the plugin (they are the dispatcher's constant list)",
      all((HOOKS / name).is_file() for name in CHECK_ORDER))

# ---------------------------------------------------------------------------
# 1. The standalone replay is the reference; prove it is not vacuous.
# ---------------------------------------------------------------------------
print("\nINV-O4  the standalone replay (the reference) leaves state and one warning")
STANDALONE = replay_standalone(ROOT)
s_records, s_snap = STANDALONE
check("control: the standalone replay leaves state files behind (the corpus exercises the accuracy trackers)",
      any(k.startswith("home-state/") for k in s_snap) and "project/contract-accuracy.json" in s_snap,
      "state files: %s" % sorted(s_snap))
check("control: integration-check reports the backend DTO edit (the corpus exercises the one output-producing check)",
      any(name == "integration-check.py" and "[integration-check] WARNING" in flatten(out)
          for _l, per in s_records for name, _rc, out, _e in per),
      "no standalone output carried the warning; integration-check read the project's markers? "
      "(INV-O3: its rules file is read project-first)")
check("control: every standalone check exits 0 on every edit",
      all(rc == 0 for _l, per in s_records for _n2, rc, _o, _e in per))

# ---------------------------------------------------------------------------
# 2. The real dispatcher against the standalone replay
# ---------------------------------------------------------------------------
print("\nINV-O4  the dispatcher's output and state equal the four standalone runs")
if the_dispatcher_exists():
    DISPATCHED = replay_dispatcher(ROOT)
    problems = verify(STANDALONE, DISPATCHED)
    check("output joins each check's output in order, prefixed with its file name; exit 0; state files equal",
          not problems, "\n".join(problems))
else:
    check("output joins each check's output in order, prefixed with its file name; exit 0; state files equal",
          False, "there is no dispatcher to run")

# ---------------------------------------------------------------------------
# 3. Controls on the comparison: a wrong dispatcher must be rejected
# ---------------------------------------------------------------------------
print("\nINV-O4  controls: the comparison rejects a wrong dispatcher")

# a scratch plugin whose dispatcher runs ONLY the first check (end to end, real processes)
scratch = fresh("scratch-only-first")
shutil.copytree(HOOKS, scratch / ".claude" / "hooks", ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc"))
shutil.copytree(ROOT / ".claude" / "scripts", scratch / ".claude" / "scripts",
                ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc"))
(scratch / ".claude" / "hooks" / DISPATCHER_NAME).write_text(
    "import subprocess, sys\n"
    "from pathlib import Path\n"
    "data = sys.stdin.buffer.read()\n"
    "p = subprocess.run([sys.executable, str(Path(__file__).parent / 'integration-check.py')], input=data,\n"
    "                   capture_output=True)\n"
    "sys.stdout.buffer.write(p.stdout)\n"
    "sys.stderr.buffer.write(p.stderr)\n"
    "sys.exit(0)\n", encoding="utf-8")
only_first = replay_dispatcher(scratch)
check("control: a scratch dispatcher running only the first check is rejected (the state of the others is missing)",
      bool(verify(STANDALONE, only_first)), "the comparison accepted a dispatcher that ran one check")

# synthetic records: wrong order, a dropped output, a changed state file, a non-zero exit
warn = '{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "[a] WARNING: one"}}'
note = "plain note from the second check"
syn_standalone = ([("edit", [("integration-check.py", 0, warn, ""), ("critic-verdict-tracker.py", 0, note, "")])],
                  {"home-state/x.json": "{}"})
good = ([("edit", 0, "integration-check.py: [a] WARNING: one\ncritic-verdict-tracker.py: " + note, "")],
        {"home-state/x.json": "{}"})
check("control: the comparison accepts a dispatcher that prefixes and orders the outputs correctly",
      verify(syn_standalone, good) == [], "; ".join(verify(syn_standalone, good)))
wrong_order = ([("edit", 0, "critic-verdict-tracker.py: " + note + "\nintegration-check.py: [a] WARNING: one", "")],
               {"home-state/x.json": "{}"})
check("control: the comparison rejects the outputs in the wrong order", bool(verify(syn_standalone, wrong_order)))
dropped = ([("edit", 0, "integration-check.py: [a] WARNING: one", "")], {"home-state/x.json": "{}"})
check("control: the comparison rejects a dropped output", bool(verify(syn_standalone, dropped)))
no_prefix = ([("edit", 0, "[a] WARNING: one\n" + note, "")], {"home-state/x.json": "{}"})
check("control: the comparison rejects outputs that carry no file-name prefix", bool(verify(syn_standalone, no_prefix)))
state_differs = ([("edit", 0, "integration-check.py: [a] WARNING: one\ncritic-verdict-tracker.py: " + note, "")],
                 {"home-state/x.json": "{\"changed\": 1}"})
check("control: the comparison rejects a different state file", bool(verify(syn_standalone, state_differs)))
bad_exit = ([("edit", 3, "integration-check.py: [a] WARNING: one\ncritic-verdict-tracker.py: " + note, "")],
            {"home-state/x.json": "{}"})
check("control: the comparison rejects a non-zero exit", bool(verify(syn_standalone, bad_exit)))

# ---------------------------------------------------------------------------
# 4. One check's failure never stops the next
# ---------------------------------------------------------------------------
print("\nINV-O4  a first check that raises still lets the rest through")
if the_dispatcher_exists():
    raising = fresh("scratch-raising")
    shutil.copytree(HOOKS, raising / ".claude" / "hooks",
                    ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc"))
    shutil.copytree(ROOT / ".claude" / "scripts", raising / ".claude" / "scripts",
                    ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc"))
    (raising / ".claude" / "hooks" / "integration-check.py").write_text(
        "import sys\nsys.stderr.write('RAISE_MARKER\\n')\nraise RuntimeError('first check failed on purpose')\n",
        encoding="utf-8")
    ref = replay_standalone(raising)
    got = replay_dispatcher(raising)
    check("control: in the scratch plugin the first check really fails when run alone",
          all(per[0][1] != 0 for _l, per in ref[0]), "first check exit codes: %r" % [per[0][1] for _l, per in ref[0]])
    problems = verify(ref, got, tolerate_failing=("integration-check.py",))
    check("the other three checks still run: their outputs and state equal the standalone runs, exit 0",
          not problems, "\n".join(problems))
    check("the failing check's error output passes through the dispatcher's own error output",
          any("RAISE_MARKER" in rec[3] for rec in got[0]), "stderr of every edit: %r" % [rec[3][:80] for rec in got[0]])
    check("the accuracy trackers did run after the failure (the home state exists)",
          any(k.startswith("home-state/") for k in got[1]), "state files: %s" % sorted(got[1]))
else:
    check("the other three checks still run after a raising first check", False, "there is no dispatcher to run")

# ---------------------------------------------------------------------------
# 5. Each check's own off switch
# ---------------------------------------------------------------------------
print("\nINV-O4  each check's own off switch still works, and removes only that piece")
if the_dispatcher_exists():
    off_env = {"CLAUDE_INTEGRATION_CHECK": "off"}
    ref_off = replay_standalone(ROOT, off_env)
    got_off = replay_dispatcher(ROOT, off_env)
    problems = verify(ref_off, got_off)
    check("CLAUDE_INTEGRATION_CHECK=off: output and state still equal the standalone runs under the same switch",
          not problems, "\n".join(problems))
    check("CLAUDE_INTEGRATION_CHECK=off: no integration warning is printed",
          not any("[integration-check]" in rec[2] for rec in got_off[0]),
          "the warning was printed with the switch off")
    check("CLAUDE_INTEGRATION_CHECK=off removes only that piece: the accuracy state is still written",
          any(k.startswith("home-state/") for k in got_off[1]) and "project/contract-accuracy.json" in got_off[1],
          "state files: %s" % sorted(got_off[1]))
    check("control: with the switch off, the integration state file is absent but the same replay with it on has it",
          not any(k.startswith("temp/") for k in got_off[1]) and any(k.startswith("temp/") for k in s_snap),
          "off: %s / on: %s" % (sorted(k for k in got_off[1] if k.startswith("temp/")),
                                sorted(k for k in s_snap if k.startswith("temp/"))))

    acc_env = {"CLAUDE_ACCURACY_TRACKER": "off"}
    ref_acc = replay_standalone(ROOT, acc_env)
    got_acc = replay_dispatcher(ROOT, acc_env)
    problems = verify(ref_acc, got_acc)
    check("CLAUDE_ACCURACY_TRACKER=off: output and state still equal the standalone runs under the same switch",
          not problems, "\n".join(problems))
    check("CLAUDE_ACCURACY_TRACKER=off removes only the three trackers: no accuracy state, the integration warning remains",
          not any(k.startswith("home-state/") for k in got_acc[1]) and "project/contract-accuracy.json" not in got_acc[1]
          and any("[integration-check] WARNING" in rec[2] for rec in got_acc[0]),
          "state files: %s" % sorted(got_acc[1]))
else:
    check("each check's own off switch works through the dispatcher", False, "there is no dispatcher to run")

print("\n%s\n %d passed, %d failed\n%s" % ("-" * 60, _passes, len(_failures), "-" * 60))
_TMP.cleanup()
sys.exit(1 if _failures else 0)
