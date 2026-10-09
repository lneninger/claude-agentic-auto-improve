#!/usr/bin/env python3
"""
test_contract_index.py -- RED tests for the contract lookup index.

SYNCED FILE. It must stay free of every project-name token listed in
``.claude/.project-tokens.json`` (minus the ``allowed`` strings) and must name
no commit; the last section scans this file and ``_contract_index.py`` for
both. Anything that names this repository or a commit belongs in the sibling
``test_contract_index_parity_local.py``.

What is pinned (each section maps to one item of the approved contract's
test task; D, I, R and FM numbers are the contract's own):

  (b) end to end, per gate: decision and exit code equal to the switch set to
      "off", cold and warm, in several launch contexts.
  (c) never stale: add, same-size approved -> archived inside the racy window,
      mtime moved back, a modification time within two seconds of the lookup,
      a future one, Files-to-touch change, rename, delete; main and worktree
      roots.
  (d) fails closed: damaged index files, a deleted, stale or throwing module,
      a contract read that fails once.
  (e) concurrency, staggered: reads that meet replaces, counted from the trace
      line's read= and replace= intervals.
  (f) the two environment escape hatches and the inline-fallback fixture (D5).
  (g) storage: only <X>/.claude/cache/contract-index/, git-ignored.
  (h) the lookup-mode switch, every value; st_ino.
  (i) save on every exit, and the two failure rows that prove the failure
      before they check stderr.

THE INTERFACE THESE TESTS EXPECT (the implementer's contract with this file)
  * ``.claude/scripts/_contract_index.py`` exists, is standard-library only,
    and carries no project token.
  * Index file: ``<X>/.claude/cache/contract-index/<variant>-<fingerprint
    first 12>.json`` where ``<X>/.claude/concepts`` is the root; JSON object
    with ``schema`` (1), ``variant`` ("concept-shared" | "bash"),
    ``fingerprint``, ``root``, ``records`` (relative path, forward slashes ->
    {size, mtime_ns, file_id, parsed_at_ns, status, entries?}).
  * Trace line (``CLAUDE_CONTRACT_INDEX=trace``), on stderr, one per gate
    process and variant, printed by the atexit wrapper, never from inside a
    function whose name contains "save":
      [contract-index] variant=<v> hits=<n> misses=<m> uncacheable=<u>
        write=<ok|skipped|failed:<cause>> read=<start_ns>:<end_ns>
        replace=<start_ns>:<end_ns>:<ok|failed>     (or replace=none)
    (one physical line; the cause holds no space).
  * The module's save work lives in top-level functions whose name contains
    "save" (case-insensitive); the failure rows replace every such function.
  * Every other public top-level function is an entry point a gate may bind;
    the stale-module rows remove them one at a time.
  * Any other CLAUDE_CONTRACT_INDEX value: stderr names the value.

Run:  py -3 .claude/hooks/tests/test_contract_index.py
Scratch space: CLAUDE_TEST_SCRATCH (default: the system temp folder).
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = HOOKS_DIR.parent
SCRIPTS_DIR = CLAUDE_DIR / "scripts"
REPO_ROOT = CLAUDE_DIR.parent
SELF = Path(__file__).resolve()
INDEX_MODULE = SCRIPTS_DIR / "_contract_index.py"

# PLUGIN PORT (sub-task 23, INV-O7): bash-gate.py is cut and is not shipped by the plugin, so its half of
# this repository's suite cannot be ported. GATES names the one gate that remains; every case that loops
# over it, and every verdict, is this repository's, unchanged.
GATES = ("concept",)
VARIANT = {"concept": "concept-shared", "bash": "bash"}
GATE_FILE = {"concept": "concept-gate.py", "bash": "bash-gate.py"}

_results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    _results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in detail.splitlines():
            print(f"        {line}")


def fs(p) -> str:
    return str(p).replace("\\", "/")


def scratch_parent() -> str:
    return os.environ.get("CLAUDE_TEST_SCRATCH") or tempfile.gettempdir()


# ---------------------------------------------------------------------------
# The trace line
# ---------------------------------------------------------------------------
_TRACE_RE = re.compile(r"^\[contract-index\][ \t]+(.*)$", re.M)


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse_trace(stderr: str) -> list[dict]:
    out: list[dict] = []
    for m in _TRACE_RE.finditer(stderr or ""):
        fields: dict[str, str] = {}
        for tok in m.group(1).split():
            k, _, v = tok.partition("=")
            fields[k] = v
        if "variant" not in fields:
            continue
        rec: dict = {
            "variant": fields.get("variant"),
            "hits": _int(fields.get("hits")),
            "misses": _int(fields.get("misses")),
            "uncacheable": _int(fields.get("uncacheable")),
            "write": fields.get("write", ""),
            "read": None,
            "replace": None,
        }
        a, _, b = fields.get("read", "").partition(":")
        if _int(a) is not None and _int(b) is not None:
            rec["read"] = (int(a), int(b))
        parts = fields.get("replace", "none").split(":")
        if len(parts) == 3 and _int(parts[0]) is not None and _int(parts[1]) is not None:
            rec["replace"] = (int(parts[0]), int(parts[1]), parts[2])
        out.append(rec)
    return out


def strip_trace(stderr: str) -> str:
    return "\n".join(
        ln for ln in (stderr or "").splitlines() if not ln.startswith("[contract-index]")
    )


class Run:
    def __init__(self, cp: subprocess.CompletedProcess, secs: float):
        self.code = cp.returncode
        self.out = (cp.stdout or b"").decode("utf-8", "replace")
        self.err = (cp.stderr or b"").decode("utf-8", "replace")
        self.secs = secs
        self.trace = parse_trace(self.err)
        self.plain_err = strip_trace(self.err)

    def of(self, variant: str) -> list[dict]:
        return [t for t in self.trace if t["variant"] == variant]

    def hits(self, variant: str) -> int:
        return max([t["hits"] or 0 for t in self.of(variant)] or [0])

    def misses(self, variant: str) -> int:
        return max([t["misses"] or 0 for t in self.of(variant)] or [0])

    def uncacheable(self, variant: str) -> int:
        return max([t["uncacheable"] or 0 for t in self.of(variant)] or [0])

    def decision(self):
        return (self.code, self.plain_err)


# ---------------------------------------------------------------------------
# Sandbox: a throwaway tree holding a copy of the gates and their helpers
# ---------------------------------------------------------------------------
HOOK_FILES = ("concept-gate.py", "_error_log.py", "_project_paths.py")
SCRIPT_FILES = ("_contract_files.py", "_contract_index.py")

_SANDBOXES: list[Path] = []


class Sandbox:
    def __init__(self, tag: str, *, with_index: bool = True, with_files: bool = True):
        self.root = Path(tempfile.mkdtemp(prefix=f"ci_{tag}_", dir=scratch_parent()))
        _SANDBOXES.append(self.root)
        self.hooks = self.root / ".claude" / "hooks"
        self.scripts = self.root / ".claude" / "scripts"
        self.concepts = self.root / ".claude" / "concepts"
        self.home = self.root / "home"
        self.wt = self.root / ".claude" / "worktrees" / "wt1"
        self.wt_concepts = self.wt / ".claude" / "concepts"
        for d in (self.hooks, self.scripts, self.concepts, self.home):
            d.mkdir(parents=True, exist_ok=True)
        for name in HOOK_FILES:
            shutil.copyfile(HOOKS_DIR / name, self.hooks / name)
        for name in SCRIPT_FILES:
            if name == "_contract_index.py" and not with_index:
                continue
            if name == "_contract_files.py" and not with_files:
                continue
            src = SCRIPTS_DIR / name
            if src.exists():
                shutil.copyfile(src, self.scripts / name)

    # -- layout ------------------------------------------------------------
    def concepts_of(self, kind: str) -> Path:
        d = self.concepts if kind == "main" else self.wt_concepts
        d.mkdir(parents=True, exist_ok=True)
        return d

    def x_of(self, kind: str) -> Path:
        return self.root if kind == "main" else self.wt

    def cache_of(self, kind: str) -> Path:
        return self.x_of(kind) / ".claude" / "cache"

    def index_dir(self, kind: str) -> Path:
        return self.cache_of(kind) / "contract-index"

    def target(self, kind: str, rel: str) -> str:
        return fs(self.x_of(kind) / rel)

    def index_files(self, kind: str, variant: str | None = None) -> list[Path]:
        d = self.index_dir(kind)
        if not d.is_dir():
            return []
        pat = f"{variant}-*.json" if variant else "*.json"
        return sorted(d.glob(pat))

    def read_index(self, kind: str, variant: str) -> dict | None:
        files = self.index_files(kind, variant)
        if not files:
            return None
        try:
            return json.loads(files[-1].read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def record(self, kind: str, variant: str, rel: str) -> dict | None:
        data = self.read_index(kind, variant)
        if not isinstance(data, dict):
            return None
        recs = data.get("records")
        return recs.get(rel) if isinstance(recs, dict) else None

    def drop_cache(self, kind: str | None = None) -> None:
        for k in (("main", "worktree") if kind is None else (kind,)):
            shutil.rmtree(self.cache_of(k), ignore_errors=True)

    def reset(self) -> None:
        for d in (self.concepts, self.wt_concepts):
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
        self.concepts.mkdir(parents=True, exist_ok=True)
        self.drop_cache()

    # -- contracts ---------------------------------------------------------
    def contract(self, kind: str, name: str, status: str, files, age: float = 10.0) -> Path:
        p = self.concepts_of(kind) / name
        write_contract(p, status, files, age)
        return p

    # -- running -----------------------------------------------------------
    def env(self, extra: dict | None = None, project_dir=None) -> dict:
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("CLAUDE_") and k != "PYTHONPATH"}
        env["CLAUDE_PROJECT_DIR"] = str(project_dir if project_dir is not None else self.root)
        env["HOME"] = str(self.home)
        env["USERPROFILE"] = str(self.home)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        for k, v in (extra or {}).items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
        return env

    def payload(self, gate: str, target: str) -> bytes:
        if gate == "concept":
            body = {"tool_name": "Edit", "tool_input": {"file_path": target}}
        else:
            body = {"tool_name": "Bash", "tool_input": {"command": f"echo x > {target}"}}
        return json.dumps(body).encode("utf-8")

    def run(self, gate: str, target: str, *, mode: str | None = "trace", env=None,
            cwd=None, project_dir=None, hooks_dir=None, script=None) -> Run:
        e = dict(env or {})
        if mode is not None and "CLAUDE_CONTRACT_INDEX" not in e:
            e["CLAUDE_CONTRACT_INDEX"] = mode
        script_path = script or ((hooks_dir or self.hooks) / GATE_FILE[gate])
        t0 = time.perf_counter()
        cp = subprocess.run(
            [sys.executable, str(script_path)],
            input=self.payload(gate, target),
            capture_output=True,
            cwd=str(cwd or self.root),
            env=self.env(e, project_dir),
            timeout=180,
        )
        return Run(cp, time.perf_counter() - t0)

    def off(self, gate: str, target: str, **kw) -> Run:
        return self.run(gate, target, mode="off", **kw)

    def popen(self, gate: str, target: str, mode: str = "trace") -> subprocess.Popen:
        p = subprocess.Popen(
            [sys.executable, str(self.hooks / GATE_FILE[gate])],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=str(self.root),
            env=self.env({"CLAUDE_CONTRACT_INDEX": mode}),
        )
        assert p.stdin is not None
        p.stdin.write(self.payload(gate, target))
        p.stdin.close()
        return p


def write_contract(path: Path, status: str, files, age: float = 10.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"- `{f}`" for f in files)
    text = (
        "# Concept Contract - fixture\n\n"
        f"**Status:** {status}\n\n"
        "## Implementation Handoff\n\n"
        "**Files to touch:**\n"
        f"{body}\n\n"
        "## Next section\n\nprose\n"
    )
    path.write_bytes(text.encode("utf-8"))
    now = time.time()
    ns = int((now - age) * 1e9)
    os.utime(path, ns=(ns, ns))


def cleanup() -> None:
    for root in _SANDBOXES:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# Source rewriting helpers (for stale, raising and failing-save module copies)
# ---------------------------------------------------------------------------
def top_functions(src: str):
    tree = ast.parse(src)
    return [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def public_function_names(src: str) -> list[str]:
    return [n.name for n in top_functions(src) if not n.name.startswith("_")]


def inject_into(src: str, pick, lines_fn) -> tuple[str, list[str]]:
    """Insert ``lines_fn(name)`` before the first statement of each picked
    top-level function. Returns the new source and the names rewritten."""
    lines = src.splitlines(keepends=True)
    nodes = [n for n in top_functions(src) if pick(n.name)]
    done: list[str] = []
    for node in sorted(nodes, key=lambda n: n.body[0].lineno, reverse=True):
        first = node.body[0]
        if first.lineno == node.lineno:
            continue
        indent = " " * first.col_offset
        ins = [indent + ln + "\n" for ln in lines_fn(node.name)]
        lines[first.lineno - 1:first.lineno - 1] = ins
        done.append(node.name)
    return "".join(lines), done


def remove_function(src: str, name: str) -> str:
    lines = src.splitlines(keepends=True)
    for node in top_functions(src):
        if node.name == name:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            del lines[start - 1:node.end_lineno]
            break
    return "".join(lines)


def decisions_equal(a: Run, b: Run) -> bool:
    return a.decision() == b.decision()


def short(r: Run) -> str:
    return f"exit={r.code} hits={r.trace and [t['hits'] for t in r.trace]} err={r.err[:300]!r}"


# ---------------------------------------------------------------------------
# Common fixture: one covered target, one uncovered target
# ---------------------------------------------------------------------------
def basic_sandbox(tag: str, **kw) -> tuple[Sandbox, str, str]:
    sb = Sandbox(tag, **kw)
    sb.contract("main", "c1.md", "approved", ["src/feat/covered.cs"])
    sb.contract("main", "c2.md", "archived", ["src/feat/uncovered.cs"])
    return sb, sb.target("main", "src/feat/covered.cs"), sb.target("main", "src/feat/uncovered.cs")


# ===========================================================================
# (b) end to end
# ===========================================================================
def section_b() -> None:
    print("-- (b) end to end: decision equals the switch set to off --")
    for gate in GATES:
        v = VARIANT[gate]
        sb = Sandbox("b")
        sb.contract("main", "c1.md", "approved", ["src/feat/covered.cs"])
        sb.contract("main", "c2.md", "archived", ["src/feat/uncovered.cs"])
        sb.contract("worktree", "w1.md", "approved", ["src/wtfeat/covered.cs"])
        (sb.wt / "src" / "sub").mkdir(parents=True, exist_ok=True)
        launches = [
            ("main target, cwd = checkout", "main", sb.root, "src/feat/{}.cs"),
            ("main target, project = main checkout, cwd = worktree subfolder", "main",
             sb.wt / "src" / "sub", "src/feat/{}.cs"),
            ("worktree target", "worktree", sb.root, "src/wtfeat/{}.cs"),
        ]
        for label, kind, cwd, pattern in launches:
            for which, expected in (("covered", 0), ("uncovered", 2)):
                sb.drop_cache()
                target = sb.target(kind, pattern.format(which))
                off = sb.off(gate, target, cwd=cwd)
                cold = sb.run(gate, target, cwd=cwd)
                warm = sb.run(gate, target, cwd=cwd)
                conds = {
                    "off decision is the expected one": off.code == expected,
                    "cold decision equals off": decisions_equal(cold, off),
                    "warm decision equals off": decisions_equal(warm, off),
                    "cold run wrote an index file": bool(sb.index_files(kind, v)),
                    "warm run reports hits > 0": warm.hits(v) > 0,
                    "cold run reports misses > 0": cold.misses(v) > 0,
                }
                bad = [k for k, ok in conds.items() if not ok]
                check(f"(b) {gate}-gate, {label}, {which}: equals off, cold and warm",
                      not bad, f"failed: {bad}\ncold: {short(cold)}\nwarm: {short(warm)}")
        # the same root spelled with a lower- and an upper-case drive letter
        if os.name == "nt" and re.match(r"^[A-Za-z]:", str(sb.root)):
            sb.drop_cache()
            root = str(sb.root)
            up, lo = root[0].upper() + root[1:], root[0].lower() + root[1:]
            target_rel = "src/feat/covered.cs"

            def spelled(spelling: str) -> Run:
                return sb.run(
                    gate, spelling.replace("\\", "/") + "/" + target_rel,
                    cwd=spelling, project_dir=spelling,
                    script=Path(spelling) / ".claude" / "hooks" / GATE_FILE[gate],
                )

            r1, r2, r3 = spelled(up), spelled(lo), spelled(up)
            n_files = len(sb.index_files("main", v))
            conds = {
                "first (upper-case) run saved exactly one file": n_files == 1,
                "lower-case spelling is warm (hits > 0)": r2.hits(v) > 0,
                "upper-case again is still warm (not emptied)": r3.hits(v) > 0,
                "all three allowed": r1.code == r2.code == r3.code == 0,
            }
            bad = [k for k, ok in conds.items() if not ok]
            check(f"(b) {gate}-gate: drive-letter spellings share one warm index file",
                  not bad, f"failed: {bad}\nfiles={sb.index_files('main', v)}\n"
                           f"r2: {short(r2)}\nr3: {short(r3)}")
        else:
            check(f"(b) {gate}-gate: drive-letter spellings (not applicable off Windows)", True)


# ===========================================================================
# (c) never stale
# ===========================================================================
def _run3(sb: Sandbox, gate: str, target: str) -> tuple[Run, Run]:
    return sb.run(gate, target), sb.run(gate, target)


_WINDOW_NS = 2_000_000_000


def _parse_outside_window(rec) -> bool:
    """True when a stored record shows its parse fell OUTSIDE the two-second window.

    Such a run proves nothing about rule R1 (b), so the row retries. When the record
    shows the parse inside the window, R1 (b) rejects it at any later lookup, so the
    lookup's own timing no longer matters. No record at all is not "outside": the row's
    own conditions report that the index is not in use.
    """
    if not isinstance(rec, dict):
        return False
    try:
        return rec["parsed_at_ns"] - rec["mtime_ns"] >= _WINDOW_NS
    except (KeyError, TypeError):
        return False


def section_c() -> None:
    print("-- (c) never stale --")
    for gate in GATES:
        v = VARIANT[gate]
        for kind in ("main", "worktree"):
            sb = Sandbox("c")
            tag = f"(c) {gate}-gate, {kind} root"

            def fresh() -> None:
                sb.reset()

            # add
            fresh()
            sb.contract(kind, "c1.md", "approved", ["src/feat/other.cs"])
            T = sb.target(kind, "src/feat/new.cs")
            sb.run(gate, T)
            warm = sb.run(gate, T)
            sb.contract(kind, "c2.md", "approved", ["src/feat/new.cs"])
            after = sb.run(gate, T)
            check(f"{tag}: a contract added later is honoured",
                  warm.hits(v) > 0 and warm.code == 2 and after.code == 0,
                  f"warm: {short(warm)}\nafter: {short(after)}")

            # approved -> archived, equal size, inside the racy window,
            # modification time restored to the stored one
            ok_row, detail = False, "no attempt gave a conclusive timing"
            for _ in range(3):
                fresh()
                p = sb.contract(kind, "c1.md", "approved", ["src/feat/racy.cs"], age=0.0)
                m0 = p.stat().st_mtime_ns
                T = sb.target(kind, "src/feat/racy.cs")
                r1 = sb.run(gate, T)
                rec = sb.record(kind, v, "c1.md")
                if _parse_outside_window(rec):
                    detail = "inconclusive: the stored record shows a parse outside the window; retrying"
                    continue
                data = p.read_bytes()
                assert len(b"approved") == len(b"archived")
                p.write_bytes(data.replace(b"approved", b"archived"))
                os.utime(p, ns=(m0, m0))
                r2 = sb.run(gate, T)
                ok_row = (r1.code == 0 and bool(rec) and rec.get("status") == "approved"
                          and r2.code == 2)
                detail = f"record after first run: {rec}\nr1: {short(r1)}\nr2: {short(r2)}"
                break
            check(f"{tag}: same-size approved->archived inside the racy window is read",
                  ok_row, detail)

            # Fast same-size rewrite whose modification time did not move (the pattern a
            # stat trial saw on a closed-handle writer: a rewrite about 1 ms after the
            # previous write left mtime unchanged). Reproduced deterministically: the
            # stamp is forced back to its exact pre-rewrite value. The record was parsed
            # while its file was inside the racy window, so rule R1 (b) refuses it, however
            # long the lookup waits: the second row waits past the window to show that.
            for wait_s, wlabel in ((0.0, "lookup right after the rewrite"),
                                   (2.3, "lookup 2.3 s after the original parse")):
                ok_row, detail = False, "no attempt gave a conclusive timing"
                for _ in range(3):
                    fresh()
                    p = sb.contract(kind, "c1.md", "approved", ["src/feat/fast.cs"], age=0.0)
                    m0 = p.stat().st_mtime_ns
                    T = sb.target(kind, "src/feat/fast.cs")
                    r1 = sb.run(gate, T)                       # the gate parses "approved"
                    rec = sb.record(kind, v, "c1.md")
                    if _parse_outside_window(rec):
                        detail = "inconclusive: the stored record shows a parse outside the window; retrying"
                        continue
                    parsed_ok = bool(rec) and rec.get("status") == "approved"
                    time.sleep(0.001)
                    p.write_bytes(p.read_bytes().replace(b"approved", b"archived"))  # closed
                    os.utime(p, ns=(m0, m0))                   # force the unchanged stamp
                    forced = p.stat().st_mtime_ns == m0
                    if wait_s:
                        time.sleep(wait_s)
                    r2 = sb.run(gate, T)
                    off = sb.off(gate, T)
                    not_trusted = (bool(r2.of(v)) and r2.hits(v) == 0
                                   and (r2.misses(v) + r2.uncacheable(v)) >= 1)
                    conds = {
                        "index in use: record holds approved after first run": parsed_ok,
                        "first run allowed": r1.code == 0,
                        "mtime forced back to the exact pre-rewrite value": forced,
                        "off decision is the archived one (block)": off.code == 2,
                        "decision equals off": decisions_equal(r2, off),
                        "record not trusted (trace: miss or uncacheable, no hit)": not_trusted,
                    }
                    bad = [k for k, ok in conds.items() if not ok]
                    ok_row = not bad
                    detail = f"failed: {bad}\nrecord: {rec}\nr1: {short(r1)}\nr2: {short(r2)}"
                    break
                check(f"{tag}: fast same-size rewrite, mtime forced unchanged ({wlabel}): "
                      f"re-read, decision equals off, record not trusted", ok_row, detail)

            # same-size edit, then mtime moved 10 s BEHIND the stored one (and the reverse order)
            for order in ("edit then utime", "utime then edit"):
                fresh()
                p = sb.contract(kind, "c1.md", "approved", ["src/feat/aged.cs"], age=10.0)
                T = sb.target(kind, "src/feat/aged.cs")
                sb.run(gate, T)
                warm = sb.run(gate, T)
                m0 = p.stat().st_mtime_ns
                back = m0 - 10_000_000_000
                data = p.read_bytes().replace(b"approved", b"archived")
                if order == "edit then utime":
                    p.write_bytes(data)
                    os.utime(p, ns=(back, back))
                else:
                    os.utime(p, ns=(back, back))
                    p.write_bytes(data)
                after = sb.run(gate, T)
                check(f"{tag}: same-size edit, mtime moved back ({order}) is read",
                      warm.hits(v) > 0 and warm.code == 0 and after.code == 2,
                      f"warm: {short(warm)}\nafter: {short(after)}")

            # a modification time within two seconds of the lookup is read, not trusted
            ok_row, detail = False, "no attempt gave a conclusive timing"
            for _ in range(3):
                fresh()
                p = sb.contract(kind, "c1.md", "approved", ["src/feat/fresh.cs"], age=0.0)
                m0 = p.stat().st_mtime_ns
                T = sb.target(kind, "src/feat/fresh.cs")
                r1 = sb.run(gate, T)
                if _parse_outside_window(sb.record(kind, v, "c1.md")):
                    detail = "inconclusive: the stored record shows a parse outside the window; retrying"
                    continue
                r2 = sb.run(gate, T)
                ok_row = (bool(sb.record(kind, v, "c1.md")) and r2.hits(v) == 0
                          and r2.misses(v) >= 1 and r2.code == 0)
                detail = f"r1: {short(r1)}\nr2: {short(r2)}"
                break
            check(f"{tag}: a file modified within 2 s of the lookup is read, not trusted",
                  ok_row, detail)

            # a future modification time is never trusted
            fresh()
            sb.contract(kind, "c1.md", "approved", ["src/feat/future.cs"], age=-3600.0)
            T = sb.target(kind, "src/feat/future.cs")
            r1, r2 = _run3(sb, gate, T)
            check(f"{tag}: a file stamped in the future is never trusted",
                  bool(sb.record(kind, v, "c1.md")) and r2.hits(v) == 0 and r2.code == 0,
                  f"r1: {short(r1)}\nr2: {short(r2)}")

            # R1 (c) on its own: the stored record's parse time is forged to ten seconds
            # after the file's stamp, so R1 (b) passes. The stamp is a minute in the
            # future, so only (c) can reject the record.
            fresh()
            fp = sb.contract(kind, "c1.md", "approved", ["src/feat/future2.cs"], age=-60.0)
            T = sb.target(kind, "src/feat/future2.cs")
            f1 = sb.run(gate, T)
            idx_files = sb.index_files(kind, v)
            forged = False
            if idx_files:
                data = json.loads(idx_files[-1].read_text(encoding="utf-8"))
                frec = data.get("records", {}).get("c1.md")
                if isinstance(frec, dict):
                    frec["parsed_at_ns"] = frec["mtime_ns"] + 10_000_000_000
                    idx_files[-1].write_text(json.dumps(data), encoding="utf-8")
                    forged = True
            f2 = sb.run(gate, T)
            f_off = sb.off(gate, T)
            check(f"{tag}: R1 (c) alone: a forged parse time past the stamp, stamp in the "
                  f"future, is a miss and equals off",
                  forged and f2.of(v) != [] and f2.hits(v) == 0
                  and (f2.misses(v) + f2.uncacheable(v)) >= 1
                  and decisions_equal(f2, f_off) and f2.code == 0,
                  f"forged={forged}\nf1: {short(f1)}\nf2: {short(f2)}\noff: {short(f_off)}")

            # Files to touch change: different size, then same size + older mtime
            fresh()
            p = sb.contract(kind, "c1.md", "approved", ["src/feat/aaa.cs"], age=10.0)
            T1, T2 = sb.target(kind, "src/feat/aaa.cs"), sb.target(kind, "src/feat/bbb.cs")
            sb.run(gate, T1)
            warm = sb.run(gate, T1)
            write_contract(p, "approved", ["src/feat/bbb.cs", "src/feat/extra.cs"], age=0.0)
            a1, a2 = sb.run(gate, T1), sb.run(gate, T2)
            check(f"{tag}: Files to touch edited (size changes) is honoured",
                  warm.hits(v) > 0 and warm.code == 0 and a1.code == 2 and a2.code == 0,
                  f"warm: {short(warm)}\nT1 after: {short(a1)}\nT2 after: {short(a2)}")

            fresh()
            p = sb.contract(kind, "c1.md", "approved", ["src/feat/aaa.cs"], age=10.0)
            sb.run(gate, T1)
            warm = sb.run(gate, T1)
            m0 = p.stat().st_mtime_ns
            p.write_bytes(p.read_bytes().replace(b"aaa.cs", b"bbb.cs"))
            os.utime(p, ns=(m0 - 10_000_000_000,) * 2)
            a1, a2 = sb.run(gate, T1), sb.run(gate, T2)
            check(f"{tag}: Files to touch edited (same size, older mtime) is honoured",
                  warm.hits(v) > 0 and warm.code == 0 and a1.code == 2 and a2.code == 0,
                  f"warm: {short(warm)}\nT1 after: {short(a1)}\nT2 after: {short(a2)}")

            # rename: to another .md name (still honoured), to a non-.md name (gone)
            fresh()
            p = sb.contract(kind, "c1.md", "approved", ["src/feat/ren.cs"], age=10.0)
            T = sb.target(kind, "src/feat/ren.cs")
            sb.run(gate, T)
            warm = sb.run(gate, T)
            p2 = p.with_name("renamed.md")
            p.rename(p2)
            same = sb.run(gate, T)
            p3 = p2.with_name("renamed.txt")
            p2.rename(p3)
            gone = sb.run(gate, T)
            check(f"{tag}: rename to another .md keeps the grant, rename to .txt removes it",
                  warm.hits(v) > 0 and warm.code == 0 and same.code == 0 and gone.code == 2,
                  f"warm: {short(warm)}\nsame: {short(same)}\ngone: {short(gone)}")

            # delete
            fresh()
            p = sb.contract(kind, "c1.md", "approved", ["src/feat/del.cs"], age=10.0)
            T = sb.target(kind, "src/feat/del.cs")
            sb.run(gate, T)
            warm = sb.run(gate, T)
            p.unlink()
            gone = sb.run(gate, T)
            check(f"{tag}: a deleted contract no longer grants",
                  warm.hits(v) > 0 and warm.code == 0 and gone.code == 2,
                  f"warm: {short(warm)}\ngone: {short(gone)}")


# ===========================================================================
# (d) fails closed
# ===========================================================================
def _warm_with_real_module(sb: Sandbox, gate: str, t_allow: str) -> tuple[bool, str]:
    sb.run(gate, t_allow)
    w = sb.run(gate, t_allow)
    return w.hits(VARIANT[gate]) > 0 and w.code == 0, short(w)


def _equal_to_off(sb: Sandbox, gate: str, t_allow: str, t_block: str, **kw):
    rows = []
    ok = True
    for t, want in ((t_allow, 0), (t_block, 2)):
        on = sb.run(gate, t, **kw)
        off = sb.off(gate, t, **kw)
        good = decisions_equal(on, off) and on.code == want and "internal error" not in on.err
        ok = ok and good
        rows.append(f"{fs(t)[-24:]}: on={short(on)} off={short(off)}")
    return ok, "\n".join(rows)


def section_d() -> None:
    print("-- (d) fails closed --")
    real_src = INDEX_MODULE.read_text(encoding="utf-8") if INDEX_MODULE.exists() else None
    for gate in GATES:
        v = VARIANT[gate]

        def damaged(label: str, damage) -> None:
            sb, T_a, T_b = basic_sandbox("d")
            ok0, d0 = _warm_with_real_module(sb, gate, T_a)
            files = sb.index_files("main", v)
            if not files:
                check(f"(d) {gate}-gate: {label}: equals off, nothing partly usable", False,
                      f"no index file after a warm run (the index is not in use)\n{d0}")
                return
            damage(files[0])
            runs = [sb.run(gate, T_a), sb.run(gate, T_b)]
            offs = [sb.off(gate, T_a), sb.off(gate, T_b)]
            conds = {
                "warm index existed first": ok0,
                "decisions equal off": all(decisions_equal(a, b) for a, b in zip(runs, offs)),
                "no 'internal error'": all("internal error" not in r.err for r in runs),
                "no Traceback": all("Traceback" not in r.err for r in runs),
                "trace line present, hits == 0 (damaged file is empty)":
                    all(r.of(v) and r.hits(v) == 0 for r in runs[:1]),
            }
            bad = [k for k, ok in conds.items() if not ok]
            check(f"(d) {gate}-gate: {label}: equals off, nothing partly usable",
                  not bad, f"failed: {bad}\n" + "\n".join(short(r) for r in runs))

        poisoned: list[bool] = []

        def edit_json(key, value):
            def f(p: Path):
                data = json.loads(p.read_text(encoding="utf-8"))
                data[key] = value
                # Poison the archived contract's record (it keeps its true signature), so
                # a reader that wrongly accepts this header grants the uncovered target.
                recs = data.setdefault("records", {})
                rec2 = recs.get("c2.md")
                if not isinstance(rec2, dict):
                    # not stored by the warm run: forge it from the file's true stat
                    st = (p.parents[2] / "concepts" / "c2.md").stat()
                    rec2 = {"size": st.st_size, "mtime_ns": st.st_mtime_ns,
                            "file_id": st.st_ino,
                            "parsed_at_ns": st.st_mtime_ns + 10_000_000_000}
                    recs["c2.md"] = rec2
                if isinstance(rec2, dict):
                    rec2["status"] = "approved"
                    rec2["entries"] = ["src/feat/uncovered.cs"]
                    poisoned.append(True)
                p.write_text(json.dumps(data), encoding="utf-8")
            return f

        def unreadable(p: Path):
            p.unlink()
            p.mkdir()

        damaged("index file missing", lambda p: p.unlink())
        damaged("index file unreadable (a folder in its place)", unreadable)
        damaged("index file truncated",
                lambda p: p.write_bytes(p.read_bytes()[: max(1, len(p.read_bytes()) // 2)]))
        damaged("wrong schema", edit_json("schema", 99))
        damaged("wrong variant", edit_json("variant", "other-variant"))
        damaged("wrong root", edit_json("root", "z:/elsewhere/.claude/concepts"))
        damaged("wrong fingerprint", edit_json("fingerprint", "0" * 64))
        check(f"(d) {gate}-gate: the four damaged-header rows each planted a poisoned record",
              len(poisoned) == 4, f"poisoned {len(poisoned)} of 4")

        # module variants
        def module_row(label: str, build) -> None:
            sb, T_a, T_b = basic_sandbox("d")
            ok0, d0 = _warm_with_real_module(sb, gate, T_a)
            build(sb)
            ok, detail = _equal_to_off(sb, gate, T_a, T_b)
            check(f"(d) {gate}-gate: {label}: every decision equals off",
                  ok0 and ok, f"index in use before the swap: {ok0} ({d0})\n{detail}")

        mod_path = lambda sb: sb.scripts / "_contract_index.py"
        module_row("module deleted", lambda sb: mod_path(sb).unlink(missing_ok=True))
        module_row("module raises on import",
                   lambda sb: mod_path(sb).write_text("raise RuntimeError('import boom')\n"))
        module_row("module is empty (every function missing)",
                   lambda sb: mod_path(sb).write_text('"""stale copy"""\n'))
        module_row(
            "module whose every attribute raises when called",
            lambda sb: mod_path(sb).write_text(
                "def __getattr__(name):\n"
                "    if name.startswith('__'):\n        raise AttributeError(name)\n"
                "    def _f(*a, **k):\n        raise RuntimeError('boom ' + name)\n"
                "    return _f\n"))
        if real_src is None:
            check(f"(d) {gate}-gate: stale copies lacking one public function", False,
                  f"{INDEX_MODULE} does not exist yet")
            check(f"(d) {gate}-gate: real entry points that raise", False,
                  f"{INDEX_MODULE} does not exist yet")
        else:
            names = public_function_names(real_src)[:8]
            for name in names:
                module_row(f"stale copy lacking {name}()",
                           lambda sb, n=name: mod_path(sb).write_text(
                               remove_function(real_src, n), encoding="utf-8"))
            check(f"(d) {gate}-gate: the real module has public functions to remove",
                  bool(names), "no public top-level function found")
            src2, done = inject_into(real_src, lambda n: not n.startswith("_"),
                                     lambda n: ["raise RuntimeError('boom')"])
            module_row("every public function raises when called",
                       lambda sb: mod_path(sb).write_text(src2, encoding="utf-8"))

        # a contract read that fails once is not cached
        sb, T_a, T_b = basic_sandbox("d")
        p = sb.concepts / "c1.md"
        lock = _hold_exclusive(p)
        try:
            blocked_run = sb.run(gate, T_a)
            off_locked = sb.off(gate, T_a)
        finally:
            lock()
        after = sb.run(gate, T_a)
        off_after = sb.off(gate, T_a)
        check(f"(d) {gate}-gate: a contract read failing once is not cached",
              decisions_equal(blocked_run, off_locked)
              and blocked_run.uncacheable(v) >= 1
              and after.code == 0 and decisions_equal(after, off_after),
              f"locked run: {short(blocked_run)}\nafter: {short(after)}")


def _hold_exclusive(path: Path):
    """Make reads of ``path`` fail until the returned callable is invoked."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                    wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                    wintypes.HANDLE]
        h = k32.CreateFileW(str(path), 0x80000000, 0, None, 3, 0x80, None)
        if h in (None, wintypes.HANDLE(-1).value, 0xFFFFFFFFFFFFFFFF):
            raise OSError("could not hold the file exclusively")

        def release():
            k32.CloseHandle(wintypes.HANDLE(h))
        return release
    mode = path.stat().st_mode
    os.chmod(path, 0)
    return lambda: os.chmod(path, mode)


# ===========================================================================
# (e) concurrency, staggered
# ===========================================================================
def _overlaps(group: list[Run]) -> tuple[int, int]:
    ok_n = failed_n = 0
    for i, a in enumerate(group):
        for j, b in enumerate(group):
            if i == j:
                continue
            for ra in (t["read"] for t in a.trace if t["read"]):
                for rb in (t["replace"] for t in b.trace if t["replace"]):
                    if ra[0] < rb[1] and rb[0] < ra[1]:
                        if rb[2] == "ok":
                            ok_n += 1
                        else:
                            failed_n += 1
    return ok_n, failed_n


def section_e() -> None:
    print("-- (e) concurrency, staggered --")
    sb = Sandbox("e")
    # A few hundred synthetic contracts (scratch only) make the index file large, which
    # widens both the read and the replace window.
    for i in range(300):
        sb.contract("main", f"c{i}.md", "approved",
                    [f"src/feat/f{i}.cs", f"src/feat/g{i}.cs", f"src/feat/h{i}.cs"])
    mut = sb.contract("main", "m.md", "approved", ["src/feat/mut.cs"])
    T_ok, T_blk = sb.target("main", "src/feat/f0.cs"), sb.target("main", "src/feat/none.cs")
    serial = [sb.run("concept", T_ok).secs for _ in range(3)]
    delta = statistics.median(serial) / 8.0

    stop = threading.Event()

    def mutator() -> None:
        while not stop.is_set():
            try:
                os.utime(mut, None)
            except OSError:
                pass
            time.sleep(0.03)

    th = threading.Thread(target=mutator, daemon=True)
    th.start()
    ok_total = failed_total = 0
    problems: list[str] = []
    saw_trace = False
    attempts = 0
    try:
        while attempts < 3:
            attempts += 1
            delta_used = delta  # one process duration spread over the eight launches
            for _round in range(5 * attempts):  # more rounds on each retry
                for gate in GATES:
                    procs = []
                    wants = []
                    t0 = time.perf_counter()
                    for k in range(8):
                        while time.perf_counter() - t0 < k * delta_used:
                            time.sleep(0.001)
                        # allow and block targets alternate (and swap every round), so a
                        # wrong allow under contention differs from its own expected exit
                        allow = (k + _round) % 2 == 0
                        wants.append(0 if allow else 2)
                        procs.append(sb.popen(gate, T_ok if allow else T_blk))
                    runs = []
                    for p in procs:
                        out = p.stdout.read() if p.stdout else b""
                        err = p.stderr.read() if p.stderr else b""
                        p.wait()
                        runs.append(Run(subprocess.CompletedProcess([], p.returncode, out, err), 0.0))
                    for k, r in enumerate(runs):
                        want = wants[k]
                        if r.trace:
                            saw_trace = True
                        if r.code != want:
                            problems.append(f"{gate}: process {k} exit {r.code}, expected {want}")
                        for bad in ("Traceback", "internal error", "JSONDecodeError"):
                            if bad in r.err:
                                problems.append(f"{gate}: stderr has {bad}: {r.err[:200]!r}")
                    o, f = _overlaps(runs)
                    ok_total += o
                    failed_total += f
            if not saw_trace:
                break
            if ok_total + failed_total > 0:
                break
    finally:
        stop.set()
        th.join(timeout=2)
    stray = list(sb.index_dir("main").glob("*.tmp")) if sb.index_dir("main").is_dir() else []
    finals = [sb.run("concept", T_ok), sb.run("concept", T_blk)]
    final_ok = finals[0].code == 0 and finals[1].code == 2
    print(f"        overlaps: read met an ok replace {ok_total}x, a failed replace {failed_total}x "
          f"({attempts} attempt(s), stagger {delta_used * 1000:.0f} ms)")
    check("(e) 8 staggered processes: at least one read overlapped another's replace",
          saw_trace and (ok_total + failed_total) > 0,
          f"trace lines seen: {saw_trace}; ok overlaps {ok_total}; failed overlaps {failed_total}"
          + ("" if saw_trace else "\n(no process printed a trace line: the index is not in use)"))
    check("(e) no process crashed, printed a traceback, or failed open under contention",
          saw_trace and not problems, "\n".join(problems[:6]))
    check("(e) final decisions are correct and no stray temporary file remains",
          saw_trace and final_ok and not stray,
          f"finals={[r.code for r in finals]} stray={stray}")


# ===========================================================================
# (f) escape hatches and the inline-fallback fixture
# ===========================================================================
MARKER_STUB = (
    "import os\n"
    "def _mark(name):\n"
    "    with open(os.environ['CI_MARKER'], 'a', encoding='utf-8') as fh:\n"
    "        fh.write(name + '\\n')\n"
    "def __getattr__(name):\n"
    "    if name.startswith('__'):\n"
    "        raise AttributeError(name)\n"
    "    def _entry(*a, **k):\n"
    "        _mark(name)\n"
    "        raise RuntimeError('instrumented stub: ' + name)\n"
    "    return _entry\n"
)


def section_f() -> None:
    print("-- (f) escape hatches and D5 --")
    # CLAUDE_CONCEPT_GATE=off / CLAUDE_BASH_GATE=off: exit 0, index untouched, no trace
    for gate in GATES:
        for var, val in (("CLAUDE_CONCEPT_GATE", "off"), ("CLAUDE_CONCEPT_GATE", "0"),
                         ("CLAUDE_BASH_GATE", "off")):
            if gate == "concept" and var == "CLAUDE_BASH_GATE":
                continue
            sb, T_a, T_b = basic_sandbox("f")
            sb.run(gate, T_a)
            before = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                      for p in sb.index_files("main")}
            r = sb.run(gate, T_b, env={var: val})
            after = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in sb.index_files("main")}
            check(f"(f) {gate}-gate with {var}={val}: exit 0, no trace line, index untouched",
                  r.code == 0 and not r.trace and before == after, short(r))

    # the stub on the (CLAUDE_CONCEPT_GATE=off) path and the pinned-contract path
    sb, T_a, T_b = basic_sandbox("f")
    (sb.scripts / "_contract_index.py").write_text(MARKER_STUB, encoding="utf-8")
    marker = sb.root / "marker.txt"
    env = {"CI_MARKER": str(marker)}
    r = sb.run("concept", T_b, env={**env, "CLAUDE_CONCEPT_GATE": "off"})
    check("(f) CLAUDE_CONCEPT_GATE=off exits before any index entry point is called",
          r.code == 0 and not marker.exists(), short(r))
    pinned = sb.root / "pins" / "pinned.md"
    write_contract(pinned, "approved", ["src/feat/pinned.cs"])
    r = sb.run("concept", sb.target("main", "src/feat/pinned.cs"),
               env={**env, "CLAUDE_ACTIVE_CONTRACT": str(pinned)})
    check("(f) CLAUDE_ACTIVE_CONTRACT reads the pinned file directly: allowed, no entry point, no index",
          r.code == 0 and not marker.exists() and not sb.index_files("main") and not r.trace,
          short(r))
    # with a real module: pinned contract allow, nothing written
    sb2, _, _ = basic_sandbox("f")
    pinned2 = sb2.root / "pins" / "pinned.md"
    write_contract(pinned2, "approved", ["src/feat/pinned.cs"])
    r = sb2.run("concept", sb2.target("main", "src/feat/pinned.cs"),
                env={"CLAUDE_ACTIVE_CONTRACT": str(pinned2)})
    check("(f) a pinned contract that covers the target never reaches the index (no file, no trace)",
          r.code == 0 and not sb2.index_files("main") and not r.trace, short(r))

    # D5: the inline fallback never touches the index even if the module is importable
    for label, with_files, expect_marker in (
        ("_contract_files.py ABSENT (inline fallback)", False, False),
        ("_contract_files.py PRESENT (control)", True, True),
    ):
        sb = Sandbox("f5", with_files=with_files)
        sb.contract("main", "c1.md", "approved", ["src/feat/covered.cs"])
        (sb.scripts / "_contract_index.py").write_text(MARKER_STUB, encoding="utf-8")
        marker = sb.root / "marker.txt"
        env = {"CI_MARKER": str(marker)}
        T_a, T_b = sb.target("main", "src/feat/covered.cs"), sb.target("main", "src/feat/other.cs")
        on = [sb.run("concept", T_a, env=env), sb.run("concept", T_b, env=env)]
        off = [sb.off("concept", T_a, env=env), sb.off("concept", T_b, env=env)]
        marker_text = marker.read_text(encoding="utf-8") if marker.exists() else ""
        # the "off" runs are made first-class: they must not have written the marker either
        check(f"(f) D5 fixture, {label}: marker {'written' if expect_marker else 'absent'}, "
              f"decisions equal off, no index file",
              (bool(marker_text) == expect_marker) and not sb.index_files("main")
              and all(decisions_equal(a, b) for a, b in zip(on, off))
              and [r.code for r in on] == [0, 2],
              f"marker={marker_text!r}\n" + "\n".join(short(r) for r in on))


# ===========================================================================
# (g) storage
# ===========================================================================
_IGNORED_PARTS = ("__pycache__", "logs")


def _tree(root: Path) -> set[str]:
    out = set()
    for p in root.rglob("*"):
        rel = p.relative_to(root).as_posix()
        if any(part in _IGNORED_PARTS for part in rel.split("/")):
            continue
        out.add(rel)
    return out


def section_g() -> None:
    print("-- (g) storage --")
    for gate in GATES:
        v = VARIANT[gate]
        sb = Sandbox("g")
        sb.contract("main", "c1.md", "approved", ["src/feat/covered.cs"])
        sb.contract("worktree", "w1.md", "approved", ["src/wtfeat/covered.cs"])
        (sb.root / "wt2" / "src").mkdir(parents=True)  # a "worktree" with no concepts root
        before = _tree(sb.root)
        runs = [
            sb.run(gate, sb.target("main", "src/feat/covered.cs")),
            sb.run(gate, sb.target("worktree", "src/wtfeat/covered.cs")),
            sb.run(gate, sb.target("main", "src/feat/uncovered.cs")),
        ]
        after = _tree(sb.root)
        new = sorted(after - before)
        allowed_prefixes = (
            ".claude/cache/contract-index/",
            ".claude/worktrees/wt1/.claude/cache/contract-index/",
        )
        stray = [p for p in new if not (p.endswith("/") or p.startswith(allowed_prefixes)
                                        or p in (".claude/cache", ".claude/cache/contract-index",
                                                 ".claude/worktrees/wt1/.claude/cache",
                                                 ".claude/worktrees/wt1/.claude/cache/contract-index"))]
        conds = {
            "main root index folder holds a file for this variant": bool(sb.index_files("main", v)),
            "worktree root index folder holds a file for this variant": bool(sb.index_files("worktree", v)),
            "no new path outside the two index folders": not stray,
            "nothing inside .claude/concepts changed": not [p for p in new if "/concepts/" in "/" + p],
        }
        bad = [k for k, ok in conds.items() if not ok]
        check(f"(g) {gate}-gate: writes only <X>/.claude/cache/contract-index/ of the roots it reads",
              not bad, f"failed: {bad}\nstray={stray}")
        # a root that does not exist gets nothing
        sb3 = Sandbox("g3")
        sb3.contract("main", "c1.md", "approved", ["src/feat/covered.cs"])
        (sb3.root / "elsewhere" / "src").mkdir(parents=True)
        r1 = sb3.run(gate, sb3.target("main", "src/feat/covered.cs"))
        r2 = sb3.run(gate, fs(sb3.root / "elsewhere" / "src" / "x.cs"))
        check(f"(g) {gate}-gate: nothing is created for a root that does not exist "
              f"(and the existing root's file is)",
              bool(sb3.index_files("main", v)) and not (sb3.root / "elsewhere" / ".claude").exists(),
              f"{short(r1)}\n{short(r2)}")
    # git-ignored (pass today by design: the pattern already exists)
    cp = subprocess.run(
        ["git", "check-ignore", "-q", ".claude/cache/contract-index/concept-shared-fingerprint.json"],
        cwd=str(REPO_ROOT), capture_output=True)
    check("(g) the index folder is git-ignored", cp.returncode == 0,
          f"git check-ignore exit {cp.returncode}")


# ===========================================================================
# (h) the switch
# ===========================================================================
ON_VALUES = [None, "", "on", "1", "true", "yes", "ON", " Yes ", "True"]
OFF_VALUES = ["off", "0", "false", "no", "OFF", " No ", "False"]
TRACE_VALUES = ["trace", "TRACE", " Trace "]
OTHER_VALUES = ["bogus", "2", "enabled", "maybe-off"]


def section_h() -> None:
    print("-- (h) the lookup-mode switch --")
    for gate in GATES:
        v = VARIANT[gate]
        sb, T_a, T_b = basic_sandbox("h")
        for val in ON_VALUES:
            sb.drop_cache()
            env = {"CLAUDE_CONTRACT_INDEX": val} if val is not None else {"CLAUDE_CONTRACT_INDEX": None}
            r1 = sb.run(gate, T_a, mode=None, env=env)
            r2 = sb.run(gate, T_a, mode=None, env=env)
            off = sb.off(gate, T_a)
            check(f"(h) {gate}-gate: CLAUDE_CONTRACT_INDEX={val!r} is on: index written, silent",
                  bool(sb.index_files("main", v)) and not r1.trace and not r2.trace
                  and "[contract-index]" not in r1.err + r2.err and decisions_equal(r2, off),
                  short(r1))
        for val in OFF_VALUES:
            sb.drop_cache()
            r1 = sb.run(gate, T_a, mode=None, env={"CLAUDE_CONTRACT_INDEX": val})
            off = sb.off(gate, T_a)
            check(f"(h) {gate}-gate: CLAUDE_CONTRACT_INDEX={val!r} is off: no index read or write, no output",
                  not sb.cache_of("main").exists() and not r1.trace and decisions_equal(r1, off)
                  and "contract-index" not in r1.err,
                  short(r1))
        for val in TRACE_VALUES:
            sb.drop_cache()
            r1 = sb.run(gate, T_a, mode=None, env={"CLAUDE_CONTRACT_INDEX": val})
            r2 = sb.run(gate, T_a, mode=None, env={"CLAUDE_CONTRACT_INDEX": val})
            check(f"(h) {gate}-gate: CLAUDE_CONTRACT_INDEX={val!r} traces; warm run shows hits > 0",
                  bool(r1.of(v)) and r1.hits(v) == 0 and r2.hits(v) > 0,
                  f"cold: {short(r1)}\nwarm: {short(r2)}")
        for val in OTHER_VALUES:
            sb.drop_cache()
            r1 = sb.run(gate, T_a, mode=None, env={"CLAUDE_CONTRACT_INDEX": val})
            off = sb.off(gate, T_a)
            named = [ln for ln in r1.err.splitlines() if val in ln]
            rest = "\n".join(ln for ln in r1.err.splitlines() if val not in ln)
            check(f"(h) {gate}-gate: unknown value {val!r} acts as off and names the value on stderr",
                  not sb.cache_of("main").exists() and r1.code == off.code
                  and strip_trace(rest) == off.plain_err and len(named) == 1,
                  f"lines naming the value: {named}\n{short(r1)}")
    # st_ino
    probe = Path(scratch_parent()) / f"ci_ino_{uuid.uuid4().hex[:8]}.txt"
    probe.write_text("x")
    try:
        ino = os.stat(probe).st_ino
    finally:
        probe.unlink()
    check("(h) platform fact: os.stat(...).st_ino is non-zero here", ino != 0, f"st_ino={ino}")
    sb, T_a, _ = basic_sandbox("h")
    sb.run("concept", T_a)
    rec = sb.record("main", "concept-shared", "c1.md")
    real = os.stat(sb.concepts / "c1.md")
    check("(h) the stored record carries the file's real st_ino, size and mtime_ns",
          bool(rec) and rec.get("file_id") == real.st_ino and rec.get("size") == real.st_size
          and rec.get("mtime_ns") == real.st_mtime_ns,
          f"record={rec} real=({real.st_ino}, {real.st_size}, {real.st_mtime_ns})")


# ===========================================================================
# (i) save on every exit
# ===========================================================================
def _gate_targets(sb, gate):
    return {"allow": sb.target("main", "src/feat/covered.cs"),
            "block": sb.target("main", "src/feat/uncovered.cs")}


def section_i() -> None:
    print("-- (i) save on every exit --")
    real_src = INDEX_MODULE.read_text(encoding="utf-8") if INDEX_MODULE.exists() else None
    for gate in GATES:
        v = VARIANT[gate]
        # the index file exists after a block run and after an allow run
        for which, want in (("block", 2), ("allow", 0)):
            sb, T_a, T_b = basic_sandbox("i")
            t = {"allow": T_a, "block": T_b}[which]
            r = sb.run(gate, t, mode=None, env={"CLAUDE_CONTRACT_INDEX": None})
            files = sb.index_files("main", v)
            data = sb.read_index("main", v)
            check(f"(i) {gate}-gate: the index file exists after a {which} run",
                  r.code == want and bool(files) and isinstance(data, dict)
                  and bool(data.get("records")),
                  short(r))

        for which, want in (("block", 2), ("allow", 0)):
            # (1) a raising save, trace on, then trace off
            for trace_on in (True, False):
                sb, T_a, T_b = basic_sandbox("i")
                t = {"allow": T_a, "block": T_b}[which]
                label = (f"(i) {gate}-gate, {which}: raising save "
                         f"({'trace on' if trace_on else 'trace off'})")
                if real_src is None:
                    check(label, False, f"{INDEX_MODULE} does not exist yet")
                    continue
                marker = sb.root / "save-marker.txt"
                src2, done = inject_into(
                    real_src, lambda n: "save" in n.lower(),
                    lambda n: [f"open({str(marker)!r}, 'a').write({n + chr(10)!r})",
                               "raise OSError('injected save failure')"])
                if not done:
                    check(label, False, "no top-level function whose name contains 'save' found")
                    continue
                (sb.scripts / "_contract_index.py").write_text(src2, encoding="utf-8")
                env = {"CLAUDE_CONTRACT_INDEX": "trace" if trace_on else "on"}
                off = sb.off(gate, t)
                r = sb.run(gate, t, mode=None, env=env)
                proven = marker.exists()
                if trace_on:
                    proven = proven and any(x["write"].startswith("failed:") for x in r.of(v))
                clean = ("Exception ignored in atexit callback" not in r.err
                         and "Traceback" not in r.err)
                check(label + ": failure proven first, then exit code and stderr unchanged",
                      proven and r.code == want == off.code and clean,
                      f"marker exists: {marker.exists()}; traces: {r.trace}\n{short(r)}")

            # (2) the index folder cannot be created: <X>/.claude/cache is a plain file
            sb, T_a, T_b = basic_sandbox("i")
            t = {"allow": T_a, "block": T_b}[which]
            cache = sb.cache_of("main")
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text("not a folder", encoding="utf-8")
            off = sb.off(gate, t)
            r = sb.run(gate, t)
            proven = (any(x["write"].startswith("failed:") for x in r.of(v))
                      and not (cache / "contract-index").exists() and cache.is_file())
            clean = ("Exception ignored in atexit callback" not in r.err
                     and "Traceback" not in r.err)
            check(f"(i) {gate}-gate, {which}: unwritable index folder: write=failed: proven, "
                  f"then exit code and stderr unchanged",
                  proven and r.code == off.code and clean,
                  f"traces: {r.trace}\n{short(r)}")


# ===========================================================================
# Synced-file hygiene: no project token, no commit named
# ===========================================================================
def section_tokens() -> None:
    print("-- synced-file hygiene --")
    cfg = json.loads((CLAUDE_DIR / ".project-tokens.json").read_text(encoding="utf-8"))
    tokens = [t for t in cfg.get("tokens", []) if t]
    allowed = [a.get("string", "") for a in cfg.get("allowed", []) if a.get("string")]
    # The shared template is intentionally empty in the plugin (it ships no project's names). Then this case
    # supplies its OWN list: names that actually identify the consuming project. They are built from pieces so
    # this file does not contain them, which the scan below would otherwise report against itself.
    if not tokens:
        tokens = ["Scalping" + "Machine", "StockTool" + "Scalping" + "Machine"]

    def scan(files: list[tuple[str, Path]]) -> list[str]:
        found: list[str] = []
        for label, path in files:
            if not path.exists():
                found.append(f"{label}: {path} does not exist")
                continue
            text = path.read_text(encoding="utf-8")
            for a in allowed:
                text = text.replace(a, "")
            low = text.lower()
            for tok in tokens:
                if tok.lower() in low:
                    found.append(f"{label}: contains the project token {tok!r}")
            for m in re.finditer(r"\b[0-9a-f]{7,40}\b", text):
                word = m.group(0)
                if re.search(r"\d", word) and re.search(r"[a-f]", word):
                    found.append(f"{label}: names a commit-like hash {word!r}")
        return found

    problems = scan([("this test file", SELF), ("_contract_index.py", INDEX_MODULE)])
    # Positive control: a scratch file that names a token must make the scan report it, or the scan is blind.
    scratch = Path(tempfile.mkdtemp(prefix="ci-tokens-"))
    try:
        planted = scratch / "planted.py"
        planted.write_text(f"# belongs to {tokens[0]}\n", encoding="utf-8")
        control = scan([("planted scratch file", planted)])
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    if not any("project token" in c for c in control):
        problems.append("control failed: a scratch file naming a token was not reported, so the scan is blind")
    check("this file and _contract_index.py are free of project tokens and commit names",
          not problems, "\n".join(problems))


# ===========================================================================
def run_section(fn) -> None:
    try:
        fn()
    except Exception:  # noqa: BLE001 - reported as a harness fault, never silent
        check(f"HARNESS ERROR in {fn.__name__}", False, traceback.format_exc())


def main() -> int:
    try:
        for fn in (section_b, section_c, section_d, section_e, section_f,
                   section_g, section_h, section_i, section_tokens):
            run_section(fn)
    finally:
        cleanup()
    failed = sum(1 for _, ok, _ in _results if not ok)
    print()
    print(f"results: {len(_results) - failed} passed, {failed} failed (of {len(_results)})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
