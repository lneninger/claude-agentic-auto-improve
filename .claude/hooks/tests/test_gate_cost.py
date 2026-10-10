#!/usr/bin/env python3
"""
test_gate_cost.py -- RED tests for Lever A: what one launch of concept-gate.py costs.

Lever A (hook-server-modes contract, amendment 2026-10-09) makes the concept gate cheaper
without changing a decision. The decisions are pinned by the parity corpus
(fixtures/gate_parity_corpus.json, run by the project-side parity suite); THIS file pins the
cost, measured the way Claude Code runs a hook:

  * a fresh ``py -3`` process per call, interpreter start and imports included,
  * on the full-work witness payload (a Write to a file no contract covers, which makes the
    gate walk and read every contract before it blocks),
  * against a real concepts folder of production size, with the contract lookup index
    present and current,
  * 20 timed runs, the candidates interleaved round by round (the order rotates), so a slow
    minute on the machine hits every candidate alike.

TARGETS (profiler report of 2026-10-05, the figures the lever is sized from: concept-gate.py
440.4 ms against architecture-guard.py 211.6 ms):

  T1  the gate's median is no higher than architecture-guard.py's median in the same run;
  T2  the gate's 90th percentile is no higher than plugin master's copy of the gate in the
      same run (master = the pinned commit below: the gate as it stood before the lever).

CONTROLS (they prove the harness can pass AND can fail):

  * green control  a scratch hook that reads its input and exits 0 at once meets T1 and T2;
  * red control    a scratch copy of master's gate whose decision is wrapped in a module-level
                   memo, filled on the first call, stays red: no fresh process ever sees a
                   second call, so a memo saves nothing;
  * red control    master's gate itself is red (T1 fails).

WHAT THE GATE IS MEASURED FROM. Both the gate under test and master's copy run from a scratch
copy of their own hooks and scripts folders, laid out alike, so neither pays for this
plugin's own contract folder and the two differ only in their code. The scratch copy of the
working gate is taken from the files in this checkout at the moment the test starts.

THE CONCEPTS FOLDER. The lever is sized against a project with a large contract folder, so
the test copies one (modification times kept, so the index sees the real stamps). Order:
CLAUDE_GATE_COST_CONCEPTS, then <CLAUDE_PROJECT_DIR>/.claude/concepts. A folder with fewer than
MIN_CONTRACTS markdown files fails the test loudly: a cost target met on a tiny folder proves
nothing, and a silent skip would look like a pass.

Run:  CLAUDE_PROJECT_DIR=<project> py -3 .claude/hooks/tests/test_gate_cost.py
Scratch space: CLAUDE_TEST_SCRATCH (default: the system temp folder).
"""

from __future__ import annotations

import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = HOOKS_DIR.parent
SCRIPTS_DIR = CLAUDE_DIR / "scripts"
REPO_ROOT = CLAUDE_DIR.parent

#: Plugin master as it stood before Lever A. The p90 comparator and the red controls are built from the
#: files at this commit, so they cannot drift when the lever merges.
MASTER_COMMIT = "47c6cb63398f4ad8d7791b9280002b4ca3ae8e60"
MASTER_HOOK_FILES = ("concept-gate.py", "_error_log.py", "_project_paths.py")
MASTER_SCRIPT_FILES = ("_contract_files.py", "_contract_index.py")

RUNS = 20
WARMUPS = 2
WITNESS_ATTEMPTS = 3
MIN_CONTRACTS = 100
BLOCK_PHRASE = "no approved contract's 'Files to touch' list references this file"
PROFILER_MEDIANS_MS = {"concept-gate.py": 440.4, "architecture-guard.py": 211.6}

_results: list[tuple[str, bool, str]] = []
_SCRATCH: list[Path] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    _results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in detail.splitlines():
            print(f"        {line}")


def scratch_parent() -> str:
    return os.environ.get("CLAUDE_TEST_SCRATCH") or tempfile.gettempdir()


def python_command() -> list[str]:
    """``py -3`` the way the plugin registers its hooks; the running interpreter where there is no launcher."""
    return ["py", "-3"] if shutil.which("py") else [sys.executable]


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------
class Candidate:
    def __init__(self, name: str, script: Path, project: Path | None, kind: str):
        self.name = name
        self.script = script
        self.project = project          # the CLAUDE_PROJECT_DIR of its launches
        self.kind = kind                # "gate" (full-work witness) | "guard" | "noop"
        self.times_ms: list[float] = []
        self.discarded = 0
        self.witness_failure = ""

    @property
    def payload(self) -> bytes:
        target = f"{self.project.as_posix()}/src/ProfilerWitness.Uncovered/Nothing.cs" if self.project else "x"
        body = '{"tool_name": "Write", "tool_input": {"file_path": "%s", "content": "witness\\n"}}' % target
        return body.encode("utf-8")


def _git_show(rel: str) -> bytes:
    cp = subprocess.run(["git", "-C", str(REPO_ROOT), "show", f"{MASTER_COMMIT}:{rel}"], capture_output=True)
    if cp.returncode != 0:
        raise RuntimeError(f"git show {MASTER_COMMIT}:{rel} failed: {cp.stderr.decode('utf-8', 'replace')[:300]}")
    return cp.stdout


def build_master_tree(root: Path) -> None:
    """Master's gate and the five files it loads, written from the pinned commit."""
    for name in MASTER_HOOK_FILES:
        dest = root / ".claude" / "hooks" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_git_show(f".claude/hooks/{name}"))
    for name in MASTER_SCRIPT_FILES:
        dest = root / ".claude" / "scripts" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_git_show(f".claude/scripts/{name}"))


def build_working_tree(root: Path) -> None:
    """Every top-level module of this checkout's hooks and scripts folders (data files beside them too)."""
    for src_dir, sub in ((HOOKS_DIR, "hooks"), (SCRIPTS_DIR, "scripts")):
        dest_dir = root / ".claude" / sub
        dest_dir.mkdir(parents=True, exist_ok=True)
        for src in src_dir.iterdir():
            if src.is_file() and src.suffix in (".py", ".json"):
                shutil.copy2(src, dest_dir / src.name)


MEMO_SHIM = '''
_MEMO = {}
_resolve_target_unmemoized = resolve_target


def resolve_target(target, pinned):
    """Scratch control: the decision, remembered after the first call in this process."""
    key = (str(target), str(pinned))
    if key not in _MEMO:
        _MEMO[key] = _resolve_target_unmemoized(target, pinned)
    return _MEMO[key]

'''


def wrap_decision_in_memo(gate: Path) -> bool:
    """Insert the memo between ``resolve_target`` and ``block``; True when the insertion point was found once."""
    text = gate.read_text(encoding="utf-8")
    marker = "\ndef block(\n"
    if text.count(marker) != 1:
        return False
    gate.write_text(text.replace(marker, "\n" + MEMO_SHIM + marker.lstrip("\n"), 1), encoding="utf-8", newline="")
    return True


def concepts_source() -> tuple[Path | None, str]:
    explicit = os.environ.get("CLAUDE_GATE_COST_CONCEPTS", "").strip()
    if explicit:
        return Path(explicit), "CLAUDE_GATE_COST_CONCEPTS"
    project = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    if project:
        return Path(project) / ".claude" / "concepts", "CLAUDE_PROJECT_DIR"
    return None, "neither CLAUDE_GATE_COST_CONCEPTS nor CLAUDE_PROJECT_DIR is set"


def make_project(root: Path, concepts_from: Path) -> Path:
    project = root / "project"
    shutil.copytree(concepts_from, project / ".claude" / "concepts", copy_function=shutil.copy2)
    (project / "CLAUDE.md").write_text("# measured project\n", encoding="utf-8")
    return project


def make_bare_project(root: Path) -> Path:
    project = root / "project"
    project.mkdir(parents=True)
    (project / "CLAUDE.md").write_text("# measured project\n", encoding="utf-8")
    return project


# ---------------------------------------------------------------------------
# Launching and statistics
# ---------------------------------------------------------------------------
def launch(c: Candidate, home: Path, *, trace: bool = False) -> tuple[float, subprocess.CompletedProcess]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_") and k != "PYTHONPATH"}
    env["HOME"] = env["USERPROFILE"] = str(home)
    if c.project is not None:
        env["CLAUDE_PROJECT_DIR"] = str(c.project)
    if trace:
        env["CLAUDE_CONTRACT_INDEX"] = "trace"
    t0 = time.perf_counter()
    cp = subprocess.run(python_command() + [str(c.script)], input=c.payload, capture_output=True,
                        cwd=str(home), env=env, timeout=180)
    return (time.perf_counter() - t0) * 1000.0, cp


def witness_ok(c: Candidate, cp: subprocess.CompletedProcess) -> bool:
    err = (cp.stderr or b"").decode("utf-8", "replace")
    if c.kind == "gate":
        return cp.returncode == 2 and BLOCK_PHRASE in err
    if c.kind == "guard":
        return cp.returncode in (0, 2)
    return cp.returncode == 0


def p90(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.9 * len(ordered)) - 1)]


def median(values: list[float]) -> float:
    return statistics.median(values)


def measure(candidates: list[Candidate], home: Path) -> None:
    for c in candidates:                                   # untimed: byte-code and index
        for _ in range(WARMUPS):
            launch(c, home)
    for round_no in range(RUNS):
        shift = round_no % len(candidates)
        for c in candidates[shift:] + candidates[:shift]:  # the order rotates every round
            for _ in range(WITNESS_ATTEMPTS):
                ms, cp = launch(c, home)
                if witness_ok(c, cp):
                    c.times_ms.append(ms)
                    break
                c.discarded += 1
                c.witness_failure = (
                    f"exit {cp.returncode}; stderr: {(cp.stderr or b'').decode('utf-8', 'replace')[-300:]!r}")


def meets_targets(c: Candidate, arch: Candidate, master: Candidate) -> tuple[bool, bool]:
    return (median(c.times_ms) <= median(arch.times_ms), p90(c.times_ms) <= p90(master.times_ms))


def row(c: Candidate) -> str:
    return (f"{c.name:<26} median {median(c.times_ms):7.1f} ms   p90 {p90(c.times_ms):7.1f} ms   "
            f"runs {len(c.times_ms)}   discarded {c.discarded}")


# ===========================================================================
def section_cost() -> None:
    print("-- Lever A: one launch of concept-gate.py, fresh process, full-work witness --")
    source, source_label = concepts_source()
    count = len(list(source.rglob("*.md"))) if source is not None and source.is_dir() else 0
    check(f"the measured concepts folder is production size (at least {MIN_CONTRACTS} contracts; from {source_label})",
          count >= MIN_CONTRACTS,
          f"{source} holds {count} markdown files. Set CLAUDE_PROJECT_DIR to the project the lever is sized "
          "against, or CLAUDE_GATE_COST_CONCEPTS to a copy of its concepts folder.")
    if count < MIN_CONTRACTS:
        return

    root = Path(tempfile.mkdtemp(prefix="gate_cost_", dir=scratch_parent()))
    _SCRATCH.append(root)
    home = root / "home"
    home.mkdir()
    try:
        build_master_tree(root / "master")
    except RuntimeError as exc:
        check("master's gate can be written out from the pinned commit", False, str(exc))
        return

    build_working_tree(root / "gate")
    build_master_tree(root / "memo")
    memo_applied = wrap_decision_in_memo(root / "memo" / ".claude" / "hooks" / "concept-gate.py")
    check("harness: the memo control wraps master's resolve_target exactly once", memo_applied,
          "the insertion point 'def block(' was not found exactly once in master's gate")

    noop = root / "noop" / "noop-hook.py"
    noop.parent.mkdir(parents=True)
    noop.write_text("import sys\nsys.stdin.read()\nsys.exit(0)\n", encoding="utf-8")

    gate = Candidate("concept-gate.py", root / "gate" / ".claude" / "hooks" / "concept-gate.py",
                     make_project(root / "gate", source), "gate")
    master = Candidate("master gate (pinned)", root / "master" / ".claude" / "hooks" / "concept-gate.py",
                       make_project(root / "master", source), "gate")
    memo = Candidate("memo control (master)", root / "memo" / ".claude" / "hooks" / "concept-gate.py",
                     make_project(root / "memo", source), "gate")
    arch = Candidate("architecture-guard.py", root / "gate" / ".claude" / "hooks" / "architecture-guard.py",
                     make_bare_project(root / "arch"), "guard")
    green = Candidate("noop control", noop, None, "noop")
    if not memo_applied:
        return
    candidates = [gate, master, memo, arch, green]

    print(f"   {RUNS} timed runs per candidate after {WARMUPS} untimed; interleaved, order rotating each round")
    measure(candidates, home)
    for c in candidates:
        print("   " + row(c))
    print(f"   profiler (2026-10-05): concept-gate.py {PROFILER_MEDIANS_MS['concept-gate.py']} ms, "
          f"architecture-guard.py {PROFILER_MEDIANS_MS['architecture-guard.py']} ms")

    # -- the harness itself ------------------------------------------------
    short = [c for c in candidates if len(c.times_ms) < RUNS]
    check("harness: every candidate passed its witness on all timed runs", not short,
          "\n".join(f"{c.name}: {len(c.times_ms)}/{RUNS} timed runs; last failure {c.witness_failure}" for c in short))
    if short:
        return

    index_problems = []
    for c in (gate, master, memo):
        _ms, cp = launch(c, home, trace=True)
        err = (cp.stderr or b"").decode("utf-8", "replace")
        files = list((c.project / ".claude" / "cache" / "contract-index").glob("*.json")) if c.project else []
        m = re.search(r"\[contract-index\]\s+variant=concept-shared\s+hits=(\d+)", err)
        if not files or not m or int(m.group(1)) < 1:
            index_problems.append(f"{c.name}: index files={len(files)}, trace={m.group(0) if m else 'no trace line'}")
    check("harness: the contract lookup index is present and current (served hits) for every gate measured",
          not index_problems, "\n".join(index_problems))

    # -- controls ----------------------------------------------------------
    g_med, g_p90 = meets_targets(green, arch, master)
    check("GREEN CONTROL: a hook that reads its input and exits 0 at once meets T1 and T2 in the same run",
          g_med and g_p90,
          f"median {median(green.times_ms):.1f} vs architecture-guard {median(arch.times_ms):.1f}; "
          f"p90 {p90(green.times_ms):.1f} vs master {p90(master.times_ms):.1f}")

    m_med, m_p90 = meets_targets(memo, arch, master)
    check("RED CONTROL: a copy of master's gate with its decision memoised in-process still misses the targets "
          "(a fresh process never sees a second call)",
          not (m_med and m_p90),
          f"memo copy met both: median {median(memo.times_ms):.1f} <= {median(arch.times_ms):.1f}, "
          f"p90 {p90(memo.times_ms):.1f} <= {p90(master.times_ms):.1f}")

    ms_med, ms_p90 = meets_targets(master, arch, master)
    check("RED CONTROL: master's gate (the gate before the lever) misses T1",
          not ms_med,
          f"master median {median(master.times_ms):.1f} <= architecture-guard {median(arch.times_ms):.1f}")

    # -- the lever ----------------------------------------------------------
    t1, t2 = meets_targets(gate, arch, master)
    check("LEVER A: concept-gate.py meets T1 (median <= architecture-guard.py's) and T2 (p90 <= master's copy's)",
          t1 and t2,
          f"T1 {'met' if t1 else 'MISSED'}: concept-gate.py median {median(gate.times_ms):.1f} ms against "
          f"architecture-guard.py {median(arch.times_ms):.1f} ms\n"
          f"T2 {'met' if t2 else 'MISSED'}: concept-gate.py p90 {p90(gate.times_ms):.1f} ms against "
          f"master's copy {p90(master.times_ms):.1f} ms")


def cleanup() -> None:
    for root in _SCRATCH:
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    try:
        try:
            section_cost()
        except Exception:  # noqa: BLE001 - reported as a harness fault, never silent
            check("HARNESS ERROR in section_cost", False, traceback.format_exc())
    finally:
        cleanup()
    failed = sum(1 for _, ok, _ in _results if not ok)
    print()
    print(f"results: {len(_results) - failed} passed, {failed} failed (of {len(_results)})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
