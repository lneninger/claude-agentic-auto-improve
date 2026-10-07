#!/usr/bin/env python3
"""
land_contract.py -- Contract Landing: the one tooling path from a parent branch to the default branch.

A contract with two or more sub-tasks is built on a parent branch. Each sub-task's pull request
merges into that branch. When the last sub-task is recorded, this script lands the contract: it
merges the default branch into a private landing checkout of the parent branch, verifies the merged
head with a scripted gate, checks that every child issue is closed and that no review verdict is
blocked, pushes the parent branch, opens the parent pull request, and merges it pinned to the exact
commit it verified. Every halt names its gate and merges nothing into the default branch.

Two stages live in this one file (L-16):

  * the LAUNCHER (phase P0, ``--status``, and the baseline launch) runs from the operator's
    checkout. It is deliberately small. It builds the landing worktree at ``origin/<parent>`` and
    runs THAT worktree's own copy of this file with ``--stage land``, so the code that runs is the
    code being landed, never the operator checkout's.
  * the LANDING stage (``--stage land``, phases P1 to P15) and the RECORDING stage
    (``--stage record-baseline``) run inside the landing worktree.

The gate's own configuration (``contractLanding`` in the conventions file) and the failing-test
baseline are ALWAYS read with ``git show origin/<default>:<path>``: never from the merged head, from
``origin/<parent>`` or from any checkout's disk. A contract under test therefore cannot edit the
gate that tests it (L-16). Completion records and Sub-Task Work Items are read only from three
fetched refs (the Delivery record set), never from a disk.

Usage (from the operator checkout):

    py -3 .claude/scripts/land_contract.py --contract <slug> [--json] [--dry-run]
    py -3 .claude/scripts/land_contract.py --contract <slug> --status [--json]
    py -3 .claude/scripts/land_contract.py --record-baseline [--suite <id>] [--json]

Exit codes: 0 success, 8 GH_REPO is set, 9 every other halt. The report is printed and written to
``report.json`` every time, halts included.

The Landing Outcome set is closed (``LANDING_OUTCOMES``). The order of the phases is the
enforcement; it is pinned by ``evaluate_gates`` and by the tests.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _claude_paths  # noqa: E402
import pr_merged  # noqa: E402

# ---------------------------------------------------------------------------
# Closed sets
# ---------------------------------------------------------------------------
SUCCESS_OUTCOMES: Tuple[str, ...] = ("landed", "already-landed", "not-applicable")
HALT_OUTCOMES: Tuple[str, ...] = (
    "landing-in-progress", "not-complete", "ambiguous-parent", "parent-unresolved",
    "parent-is-default", "gh-repo-set", "landing-not-configured", "baseline-unreadable",
    "unverifiable", "parent-diverged", "blocked-verdict", "children-still-open",
    "environment-failure", "unresolvable-conflict", "regeneration-failed",
    "verification-not-ready", "push-rejected", "pr-mismatch", "pr-not-ready",
    "link-not-verified", "master-moved", "head-moved", "not-mergeable", "merge-refused",
    "merge-unconfirmed",
)
#: The closed Landing Outcome set: 3 successes and 25 halts.
LANDING_OUTCOMES = frozenset(SUCCESS_OUTCOMES) | frozenset(HALT_OUTCOMES)
#: The recording run's own outcomes (``--record-baseline``).
BASELINE_OUTCOMES: Tuple[str, ...] = ("baseline-recorded", "landing-in-progress",
                                      "landing-not-configured", "environment-failure",
                                      "unverifiable")
SUCCESS_EXIT = ("landed", "already-landed", "not-applicable", "baseline-recorded")

EXIT_OK = 0
EXIT_GH_REPO_SET = 8
EXIT_HALT = 9

CONVENTIONS_PATH = ".claude/work-item-conventions.json"
BASELINE_PATH = ".claude/test-baseline.json"
PROFILE_PATH = ".claude/project-profile.md"
SENTINEL_PATH = ".claude/hooks/sentinel-paths.json"
BRIEFS_DIR = ".claude/work-items"
RECORDS_ROOT = ".claude/orchestrator/results"
PASS_VERDICTS = ("pass", "pass-with-findings")
HEX40 = re.compile(r"[0-9a-f]{40}")

#: Remedy per halt: the one operator action that moves the landing on. Data, not prose a skill composes.
REMEDIES: Dict[str, str] = {
    "landing-in-progress": "wait for the live run to finish, or free the lock if its process is gone",
    "not-complete": "commit the record to docs/<slug>-records and push it (/pr-merged Step 3)",
    "ambiguous-parent": "make the Sub-Task Work Items agree on base:, parent_issue: and id:, then rerun",
    "parent-unresolved": "add the parent brief (branch: <parent branch>, id: <parent issue>) and push it",
    "parent-is-default": "a contract must not be built directly on a protected branch",
    "gh-repo-set": "unset GH_REPO in this shell and run again",
    "landing-not-configured": "add the contractLanding block to the conventions file on the default branch",
    "baseline-unreadable": "repair .claude/test-baseline.json on the default branch",
    "unverifiable": "make the read succeed (gh authenticated, network reachable) and rerun",
    "parent-diverged": "the local parent branch is ahead of origin; push or reset it, then rerun",
    "blocked-verdict": "add a remedy sub-task on the parent branch for the blocked review, then rerun",
    "children-still-open": "close or merge the open child issues, then rerun",
    "environment-failure": "fix the environment named in the detail, then rerun",
    "unresolvable-conflict": "merge the default branch into the parent branch by hand as a remedy sub-task",
    "regeneration-failed": "fix the regenerator named in the detail on the parent branch, then rerun",
    "verification-not-ready": "fix the new failures named in the detail, or re-record the baseline",
    "push-rejected": "fetch, reconcile the parent branch with origin, then rerun",
    "pr-mismatch": "close or retarget the existing pull request for the parent branch",
    "pr-not-ready": "mark the parent pull request ready by hand, then rerun",
    "link-not-verified": "repair the Closing Link in the pull request body, then rerun",
    "master-moved": "rerun: the default branch moved while verifying, so it merges and verifies again",
    "head-moved": "rerun: the pull request head is not the verified commit",
    "not-mergeable": "resolve the mergeability problem on the pull request, then rerun",
    "merge-refused": "read the refusal in the detail, then rerun",
    "merge-unconfirmed": "rerun: the next run reads the merged pull request and writes the bookkeeping",
}


# ---------------------------------------------------------------------------
# Edges: the only places that touch processes, sockets, git or GitHub
# ---------------------------------------------------------------------------
def _run(cmd: Sequence[Any], cwd: Any = None, timeout: int = 60) -> Tuple[int, str]:
    """Run a short command. Returns ``(returncode, stdout)``; stderr when stdout is empty."""
    try:
        proc = subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None,
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return 124, "timed out after %s seconds" % timeout
    except OSError as exc:
        return 127, str(exc)
    out = (proc.stdout or "").rstrip("\r\n")
    if not out.strip():
        out = (proc.stderr or "").rstrip("\r\n")
    return proc.returncode, out


def _kill_tree(proc: "subprocess.Popen[bytes]") -> None:
    """Stop a timed-out step and everything it started, by process id (never by image name)."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, timeout=60)
        else:
            proc.kill()
        proc.wait(timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass


def _run_long(cmd: Sequence[Any], timeout: float, log_path: Any, cwd: Any) -> Tuple[Optional[int], bool]:
    """Run a long command (a build, a test run), its combined output going to ``log_path``.

    Returns ``(returncode, timed_out)``. ``returncode`` is None when the process never started.
    """
    log = Path(log_path)
    log.parent.mkdir(parents=True, exist_ok=True)
    argv = [str(c) for c in cmd]
    with open(log, "wb") as fh:
        try:
            proc = subprocess.Popen(argv, cwd=str(cwd) if cwd else None, stdout=fh,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    env=dict(os.environ))
        except OSError as exc:
            fh.write(("launch failed: %s\n" % exc).encode("utf-8", "replace"))
            return None, False
        try:
            return proc.wait(timeout=timeout), False
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            return (proc.returncode if proc.returncode is not None else -1), True


def tcp_probe(host: str, port: int, timeout: float) -> bool:
    """One TCP connect: True when something is listening."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def exec_stage(argv: Sequence[Any], cwd: Any = None) -> int:
    """Run the landing (or recording) stage and wait for it. Output flows to this process."""
    try:
        return subprocess.run([str(a) for a in argv], cwd=str(cwd) if cwd else None).returncode
    except OSError:
        return 127


def probe_stage(path: Any) -> bool:
    """True when the script at ``path`` accepts ``--stage land`` (an older copy does not)."""
    rc, out = _run([sys.executable, "-B", str(path), "--stage", "land", "--probe"], timeout=60)
    return rc == 0 and "land-stage-ok" in out


def git_show(ref: str, path: str, cwd: Any = None) -> Optional[str]:
    """The text of ``path`` at ``ref``, or None when git cannot read it."""
    rc, out = _run(["git", "show", "%s:%s" % (ref, path)], cwd=cwd)
    return out if rc == 0 else None


def git_ls_remote(ref: str, cwd: Any = None) -> Optional[str]:
    """The sha ``origin`` reports for ``ref`` right now (a fresh network read), or None."""
    rc, out = _run(["git", "ls-remote", "origin", ref], cwd=cwd, timeout=120)
    if rc != 0 or not out.strip():
        return None
    first = out.splitlines()[0].split()
    return first[0] if first and HEX40.fullmatch(first[0]) else None


def git_push(parent: str, cwd: Any, default_branch: str, protected: Iterable[str]) -> Tuple[int, str]:
    """Push HEAD to the parent branch. Never forced; a protected destination is refused first."""
    blocked = {default_branch} | set(protected or ())
    if not parent or parent in blocked or parent.startswith(("-", "+")) or ":" in parent:
        return 1, "refused: %r is the default branch, a protected branch or not a branch name" % (parent,)
    return _run(["git", "push", "origin", "HEAD:refs/heads/%s" % parent], cwd=cwd, timeout=300)


def git_merge(ref: str, cwd: Any) -> Tuple[int, str]:
    """Merge ``ref`` into the checked-out head without committing, so conflicts can be resolved."""
    return _run(["git", "merge", "--no-ff", "--no-commit", ref], cwd=cwd, timeout=300)


def git_commit(cwd: Any, message: str) -> Tuple[int, str]:
    """Commit the staged merge. Hooks are skipped: this commit is verified by the gate, not by a hook."""
    return _run(["git", "commit", "--no-verify", "-m", message], cwd=cwd, timeout=300)


def gh_auth_status(cwd: Any = None) -> bool:
    return _run(["gh", "auth", "status"], cwd=cwd, timeout=60)[0] == 0


_PR_FIELDS = "number,state,isDraft,baseRefName,headRefName,headRefOid,mergeCommit,url"


def gh_pr_find(head: str, base: Optional[str] = None, cwd: Any = None) -> Optional[Dict[str, Any]]:
    """The pull request for ``head``: a merged one into ``base`` first, then an open one, then others."""
    rc, out = _run(["gh", "pr", "list", "--head", head, "--state", "all", "--limit", "30",
                    "--json", _PR_FIELDS], cwd=cwd, timeout=120)
    if rc != 0 or not out.strip():
        return None
    try:
        items = [i for i in json.loads(out) if isinstance(i, dict) and i.get("headRefName") == head]
    except (ValueError, TypeError):
        return None
    if not items:
        return None

    def rank(item: Dict[str, Any]) -> Tuple[int, int]:
        state = str(item.get("state") or "").upper()
        if state == "MERGED" and (base is None or item.get("baseRefName") == base):
            tier = 0
        elif state == "OPEN":
            tier = 1
        elif state == "MERGED":
            tier = 2
        else:
            tier = 3
        return tier, -int(item.get("number") or 0)

    return min(items, key=rank)


def gh_pr_view(number: Any, cwd: Any = None) -> Dict[str, Any]:
    """One pull request, fresh. ``{}`` when gh cannot answer."""
    rc, out = _run(["gh", "pr", "view", str(number), "--json",
                    _PR_FIELDS + ",mergeable,body"], cwd=cwd, timeout=120)
    if rc != 0 or not out.strip():
        return {}
    try:
        data = json.loads(out)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def gh_issue_state(number: Any, cwd: Any = None) -> Optional[str]:
    rc, out = _run(["gh", "issue", "view", str(number), "--json", "state"], cwd=cwd, timeout=120)
    if rc != 0:
        return None
    try:
        state = str(json.loads(out).get("state") or "").upper()
    except (ValueError, AttributeError):
        return None
    return state if state in ("OPEN", "CLOSED") else None


def read_children(parent_issue: Any, cwd: Any = None) -> Optional[Dict[str, Any]]:
    """The parent issue's sub-issues: ``{"nodes": [...], "totalCount": n}`` or None when unreadable.

    The argv is the conventions file's ``parentListCommand`` (``gh issue view <parent> --json subIssues``).
    """
    rc, out = _run(["gh", "issue", "view", str(parent_issue), "--json", "subIssues"], cwd=cwd, timeout=120)
    if rc != 0:
        return None
    try:
        sub = json.loads(out).get("subIssues")
    except (ValueError, AttributeError):
        return None
    if not isinstance(sub, dict) or not isinstance(sub.get("nodes"), list):
        return None
    return {"nodes": sub["nodes"], "totalCount": sub.get("totalCount")}


def gh_pr_create(base: str, head: str, title: str, body: str, cwd: Any = None) -> Tuple[int, str]:
    """Open the parent pull request, ready for review (never a draft). Returns ``(rc, url)``."""
    rc, out = _run(["gh", "pr", "create", "--base", base, "--head", head, "--title", title,
                    "--body", body], cwd=cwd, timeout=180)
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return rc, (lines[-1] if lines else "")


def gh_pr_ready(number: Any, cwd: Any = None) -> Tuple[int, str]:
    return _run(["gh", "pr", "ready", str(number)], cwd=cwd, timeout=120)


def gh_pr_edit_body(number: Any, body: str, cwd: Any = None) -> Tuple[int, str]:
    return _run(["gh", "pr", "edit", str(number), "--body", body], cwd=cwd, timeout=120)


def gh_pr_merge(number: Any, head_sha: str, cwd: Any = None) -> Tuple[int, str]:
    """Merge the parent pull request, pinned to the one verified commit. L-1: the only merge in the tooling.

    An abbreviated or malformed commit is refused BEFORE any process starts.
    """
    if not HEX40.fullmatch(str(head_sha or "")):
        raise ValueError("--match-head-commit needs the full 40-hex commit, got %r" % (head_sha,))
    return _run(["gh", "pr", "merge", str(number), "--merge", "--match-head-commit", head_sha],
                cwd=cwd, timeout=300)


def verify_closing_link(brief_path: Any, pr_number: Any, cwd: Any = None,
                        repair_attempted: bool = False, conventions_text: Optional[str] = None,
                        brief_text: Optional[str] = None) -> str:
    """The Closing Link verdict from ``verify_issue_link.py`` for the parent brief and pull request.

    L-16 (W1): the landing reads no brief or conventions file from a checkout's disk. With
    ``conventions_text`` (``git show origin/<default>:<conventions file>``) and ``brief_text`` (the
    parent brief from the fetched Delivery record set) the child runs in a temporary project
    root that holds exactly those two texts; ``CLAUDE_PROJECT_DIR`` points there for the call only
    and is restored afterwards. Without them the call is the plain one.
    """
    cmd = [sys.executable, "-B", str(SCRIPTS_DIR / "verify_issue_link.py"), "--brief", str(brief_path),
           "--pr", str(pr_number), "--json"]
    if repair_attempted:
        cmd.append("--repair-attempted")
    if conventions_text is None and brief_text is None:
        rc, out = _run(cmd, cwd=cwd, timeout=180)
    else:
        with tempfile.TemporaryDirectory(prefix="landing-link-") as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / ".claude" / "work-item-conventions.json").write_text(
                conventions_text if conventions_text is not None else "{}", encoding="utf-8")
            if brief_text is not None:
                supplied = root / (Path(str(brief_path)).name or "brief.md")
                supplied.write_text(brief_text, encoding="utf-8")
                cmd[cmd.index("--brief") + 1] = str(supplied)
            saved = os.environ.get("CLAUDE_PROJECT_DIR")
            os.environ["CLAUDE_PROJECT_DIR"] = str(root)
            try:
                rc, out = _run(cmd, cwd=cwd, timeout=180)
            finally:
                if saved is None:
                    os.environ.pop("CLAUDE_PROJECT_DIR", None)
                else:
                    os.environ["CLAUDE_PROJECT_DIR"] = saved
    try:
        return str(json.loads(out).get("verdict") or "unverifiable")
    except (ValueError, AttributeError):
        return "unverifiable"


def _set_frontmatter(text: str, updates: Dict[str, str]) -> str:
    """Set keys in a brief's frontmatter block, keeping its line endings."""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    if not lines or lines[0].strip() != "---":
        return text
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return text
    pending = dict(updates)
    for i in range(1, end):
        key = lines[i].partition(":")[0].strip()
        if key in pending:
            lines[i] = "%s: %s" % (key, pending.pop(key))
    for key, value in pending.items():
        lines.insert(end, "%s: %s" % (key, value))
        end += 1
    return newline.join(lines)


def write_bookkeeping(checkout: Any, parent_brief: str, pr: Dict[str, Any], report: Dict[str, Any]) -> None:
    """P15: the parent brief in the launching checkout's tree: shipped, its pull request, its link."""
    target = Path(checkout) / parent_brief
    if not target.is_file():
        raise FileNotFoundError("the parent brief is not on the launching checkout's disk: %s" % target)
    raw = target.read_bytes().decode("utf-8")
    updated = _set_frontmatter(raw, {"status": "shipped", "pr": str((pr or {}).get("url") or ""),
                                     "issue_link": "closes"})
    if updated != raw:
        target.write_bytes(updated.encode("utf-8"))


def list_worktrees(cwd: Any) -> List[str]:
    rc, out = _run(["git", "worktree", "list", "--porcelain"], cwd=cwd)
    if rc != 0:
        raise RuntimeError("git worktree list failed: %s" % out)
    return [ln.split(" ", 1)[1].strip() for ln in out.splitlines() if ln.startswith("worktree ")]


def worktree_remove(path: Any) -> None:
    """Remove a landing worktree. Never forced; raises when git refuses.

    C1: the path must be a landing worktree by name and folder, checked again here, right before
    the removal, whatever the caller already decided.
    """
    rc, out = _run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=path)
    if rc != 0 or not out.strip():
        raise RuntimeError("cannot locate the repository of %s: %s" % (path, out))
    root = Path(out.strip()).parent
    if not is_landing_worktree(path, root):
        raise RuntimeError("%s is not a landing worktree (<main root>/.claude/worktrees/<8 digits>-land-"
                           "<issue or baseline>); refusing to remove it" % path)
    rc, out = _run(["git", "worktree", "remove", str(path)], cwd=root, timeout=180)
    if rc != 0:
        raise RuntimeError(out or "git worktree remove failed")


def _norm(path: Any) -> str:
    return os.path.normcase(os.path.realpath(str(path)))


#: Any landing worktree's name: exactly eight digits, then ``-land-<parent issue>`` or ``-land-baseline``.
LANDING_NAME = re.compile(r"\d{8}-land-(?:\d+|baseline)")


def is_landing_worktree(path: Any, main_root: Any, suffix: Optional[str] = None) -> bool:
    """C1 / L-15: ``<main root>/.claude/worktrees/<8 digits><suffix>`` and nothing looser.

    With ``suffix`` (``-land-<issue>`` or ``-land-baseline``) the name must carry exactly it; without
    one any landing name matches. An operator's ``<date>-debug-land-<issue>`` never does.
    """
    p = Path(str(path).replace("\\", "/").rstrip("/"))
    if _norm(p.parent) != _norm(Path(str(main_root)) / ".claude" / "worktrees"):
        return False
    pattern = re.compile(r"\d{8}" + re.escape(suffix)) if suffix else LANDING_NAME
    return pattern.fullmatch(p.name) is not None


def _under(path: Any, root: Any) -> bool:
    p, r = _norm(path), _norm(root)
    return p == r or p.startswith(r + os.sep)


def landing_state_dir(main_root: Any) -> Path:
    """``<main root>/.claude/state/landing`` -- the runtime root (a cache, never authority; L-10)."""
    return Path(main_root) / ".claude" / "state" / "landing"


def worktree_reset(path: Any, main_root: Any, slug: str, ref: Optional[str] = None) -> None:
    """L-15: reset and clean a landing worktree, only after matching it to git and to phase.json.

    Ignored files survive (``git clean`` never uses -x), so installed packages and build output
    stay between runs. With ``ref`` the worktree is detached at it first.
    """
    def landing_only() -> None:
        if not is_landing_worktree(path, main_root):
            raise ValueError("%s is not a landing worktree (<main root>/.claude/worktrees/<8 digits>-land-"
                             "<issue or baseline>); refusing a destructive git command" % path)

    landing_only()
    listed = [_norm(p) for p in list_worktrees(main_root)]
    if _norm(path) not in listed:
        raise ValueError("%s is not in `git worktree list`; refusing a destructive git command" % path)
    phase = _read_json(landing_state_dir(main_root) / slug / "phase.json")
    if not isinstance(phase, dict) or _norm(phase.get("worktree") or "") != _norm(path):
        raise ValueError("%s is not the worktree phase.json records for %s; refusing a destructive "
                         "git command" % (path, slug))
    if ref:
        landing_only()
        rc, out = _run(["git", "checkout", "--detach"], cwd=path)
        if rc != 0:
            raise RuntimeError("git checkout --detach failed: %s" % out)
    landing_only()
    rc, out = _run(["git", "reset", "--hard", ref or "HEAD"], cwd=path, timeout=300)
    if rc != 0:
        raise RuntimeError("git reset --hard failed: %s" % out)
    landing_only()
    rc, out = _run(["git", "clean", "-fd"], cwd=path, timeout=300)
    if rc != 0:
        raise RuntimeError("git clean failed: %s" % out)


# ---------------------------------------------------------------------------
# Small pure helpers
# ---------------------------------------------------------------------------
def _read_json(path: Any) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("%s.tmp-%d" % (path.name, os.getpid()))
    tmp.write_text(text, encoding="utf-8")
    os.replace(str(tmp), str(path))


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]


def glob_regex(pattern: str) -> "re.Pattern[str]":
    """Glob to regex with the repository's semantics: ``**`` crosses '/', a single ``*`` does not."""
    pat = pattern.replace("\\", "/")
    if pat.startswith("./"):
        pat = pat[2:]
    out, i = [], 0
    while i < len(pat):
        if pat.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pat.startswith("**", i):
            out.append(".*")
            i += 2
        elif pat[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pat[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pat[i]))
            i += 1
    return re.compile("".join(out))


def path_matches(path: str, patterns: Iterable[str]) -> bool:
    p = path.replace("\\", "/")
    return any(glob_regex(g).fullmatch(p) for g in patterns if g)


def parse_frontmatter(text: str) -> Dict[str, str]:
    """A brief's frontmatter as ``key -> value`` strings (flat keys only)."""
    match = re.match(r"\A﻿?---\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", text or "", re.S)
    if not match:
        return {}
    fields: Dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line or line[0] in " \t":
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip("\"'")
    return fields


# ---------------------------------------------------------------------------
# Roots (L-14)
# ---------------------------------------------------------------------------
def resolve_roots(path: Any) -> Dict[str, Path]:
    """Explicit roots from ``git rev-parse --git-common-dir``: the same answer from every worktree.

    Sets ``CLAUDE_PROJECT_DIR`` to the main root for this process and its children before the
    ``state_dir`` / ``logs_dir`` locators run, and refuses a result outside the main root, so the
    runtime can never fall back to the home directory.
    """
    rc, out = _run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=path)
    if rc != 0 or not out.strip():
        raise RuntimeError("cannot find the main checkout from %s: %s" % (path, out))
    main_root = Path(out.strip()).parent
    os.environ["CLAUDE_PROJECT_DIR"] = str(main_root)
    state, logs = _claude_paths.state_dir(), _claude_paths.logs_dir()
    for name, resolved in (("state_dir", state), ("logs_dir", logs)):
        if not _under(resolved, main_root):
            raise RuntimeError("%s resolved to %s, outside the main root %s" % (name, resolved, main_root))
    return {"main_root": main_root, "state_dir": state, "logs_dir": logs,
            "landing_root": state / "landing"}


# ---------------------------------------------------------------------------
# Parsers (trx, vitest-json, unittest-text)
# ---------------------------------------------------------------------------
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_trx(text: Optional[str]) -> Optional[List[Dict[str, str]]]:
    """TRX -> ``[{unit, name, outcome, message}]``; None when empty or unparseable."""
    if not text or not text.strip():
        return None
    try:
        root = ET.fromstring(text.lstrip("﻿").encode("utf-8"))
    except ET.ParseError:
        return None
    classes: Dict[str, str] = {}
    for el in root.iter():
        if _local(el.tag) == "UnitTest":
            for child in el:
                if _local(child.tag) == "TestMethod":
                    classes[el.get("id", "")] = child.get("className", "")
    results: List[Dict[str, str]] = []
    for el in root.iter():
        if _local(el.tag) != "UnitTestResult":
            continue
        raw = (el.get("outcome") or "").lower()
        if raw == "passed":
            outcome = "passed"
        elif raw in ("failed", "error", "timeout", "aborted"):
            outcome = "failed"
        else:
            outcome = "skipped"
        message = ""
        for sub in el.iter():
            if _local(sub.tag) == "Message" and (sub.text or "").strip():
                message = sub.text.strip()
                break
        results.append({"unit": classes.get(el.get("testId", ""), "") or "(unknown class)",
                        "name": el.get("testName", ""), "outcome": outcome, "message": message})
    return results


def parse_vitest_json(text: Optional[str], root: Any = None) -> Optional[List[Dict[str, str]]]:
    """Vitest JSON reporter output -> results; the unit is the spec file (relative to ``root``)."""
    if not text or not text.strip():
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("testResults"), list):
        return None
    results: List[Dict[str, str]] = []
    for spec in data["testResults"]:
        if not isinstance(spec, dict):
            continue
        unit = str(spec.get("name") or "")
        if root is not None and os.path.isabs(unit):
            try:
                unit = Path(os.path.relpath(unit, str(root))).as_posix()
            except ValueError:
                pass
        unit = unit.replace("\\", "/")
        asserts = spec.get("assertionResults") or []
        if not asserts and str(spec.get("status") or "").lower() == "failed":
            results.append({"unit": unit, "name": "(spec file failed to run)", "outcome": "failed",
                            "message": str(spec.get("message") or "")})
            continue
        for item in asserts:
            status = str(item.get("status") or "").lower()
            outcome = "passed" if status == "passed" else "failed" if status == "failed" else "skipped"
            results.append({"unit": unit, "name": str(item.get("fullName") or item.get("title") or ""),
                            "outcome": outcome,
                            "message": "\n".join(str(m) for m in (item.get("failureMessages") or []))})
    return results


_UT_HEAD = re.compile(r"^(\S+) \(([\w.]+)\)(?: \(.*\))?(?: \.\.\. (.*))?$")
_UT_RESULT = re.compile(r"^(ok|FAIL|ERROR|skipped\b.*|expected failure|unexpected success)$")
_UT_DETAIL = re.compile(r"^(FAIL|ERROR): (\S+) \(([\w.]+)\)")


def parse_unittest_text(text: Optional[str]) -> Optional[List[Dict[str, str]]]:
    """``unittest -v`` output -> results; the unit is the dotted class. None when no test line is found."""
    if not text or not text.strip():
        return None
    lines = text.splitlines()
    results: List[Dict[str, str]] = []
    pending: Optional[Tuple[str, str]] = None
    for line in lines:
        head = _UT_HEAD.match(line)
        if head:
            name, dotted, tail = head.group(1), head.group(2), head.group(3)
            unit = dotted.rsplit(".", 1)[0] if "." in dotted else dotted
            if tail is not None and _UT_RESULT.match(tail):
                results.append(_ut_result(unit, name, tail))
                pending = None
            else:
                pending = (unit, name)
            continue
        if pending is not None:
            stripped = line.strip()
            tail = stripped.split(" ... ", 1)[-1] if " ... " in stripped else stripped
            if _UT_RESULT.match(tail):
                results.append(_ut_result(pending[0], pending[1], tail))
                pending = None
    if not results:
        return None
    messages: Dict[Tuple[str, str], List[str]] = {}
    current: Optional[Tuple[str, str]] = None
    for line in lines:
        detail = _UT_DETAIL.match(line)
        if detail:
            dotted = detail.group(3)
            current = (dotted.rsplit(".", 1)[0] if "." in dotted else dotted, detail.group(2))
            messages.setdefault(current, [])
            continue
        if current is not None and (line.startswith("Ran ") or line.startswith("=" * 10)):
            current = None
        elif current is not None and not line.startswith("-" * 10):
            messages[current].append(line)
    for r in results:
        if r["outcome"] == "failed":
            r["message"] = "\n".join(messages.get((r["unit"], r["name"]), [])).strip()
    return results


def _ut_result(unit: str, name: str, tail: str) -> Dict[str, str]:
    if tail == "ok":
        outcome = "passed"
    elif tail in ("FAIL", "ERROR", "unexpected success"):
        outcome = "failed"
    else:
        outcome = "skipped"
    return {"unit": unit, "name": name, "outcome": outcome, "message": ""}


def parse_results(fmt: str, text: Optional[str], root: Any = None) -> Optional[List[Dict[str, str]]]:
    if fmt == "trx":
        return parse_trx(text)
    if fmt == "vitest-json":
        return parse_vitest_json(text, root)
    if fmt == "unittest-text":
        return parse_unittest_text(text)
    return None


# ---------------------------------------------------------------------------
# Environment versus regression (L-7b, L-8)
# ---------------------------------------------------------------------------
def _gating_signatures(step: Dict[str, Any], emulators: Iterable[Dict[str, Any]]) -> List[str]:
    sigs: List[str] = []
    for emu in emulators or ():
        gates = emu.get("gates_steps")
        if gates is not None and step.get("id") not in gates:
            continue
        sigs.extend(s for s in (emu.get("signatures") or []) if s)
    return sigs


def read_step(step: Dict[str, Any], run: Dict[str, Any], baseline: Dict[str, Any],
              emulators: Iterable[Dict[str, Any]] = ()) -> Dict[str, Any]:
    """Classify one step's run as ``ok``, ``environment`` or ``regression`` (L-7b).

    A failure is NEW when its unit is in neither baseline list, or its unit is known-failing but its
    test name is not recorded there (L-8). A failure carrying an emulator signature is an environment
    failure, never new, whatever the baseline says.
    """
    sid = step.get("id")
    suite = step.get("suite", sid)
    fmt = (step.get("results") or {}).get("format", "exit-code")
    res: Dict[str, Any] = {"id": sid, "suite": suite, "reading": "ok", "new_failures": [],
                           "new_failure_items": [], "failed_tests": [], "baseline_now_passing": [],
                           "executed_count": 0, "environment_reason": None,
                           "exit_code": run.get("exit_code"), "log": run.get("log_path")}

    def environment(reason: str) -> Dict[str, Any]:
        res["reading"], res["environment_reason"] = "environment", reason
        return res

    if run.get("launched") is False:
        return environment("launch-failed")
    if run.get("timed_out"):
        return environment("timed-out")
    exit_code = run.get("exit_code")
    log_text = run.get("log_text") or ""
    log_sig = next((s for s in (step.get("environment_signatures") or []) if s and s in log_text), None)

    if fmt == "exit-code":
        if log_sig:
            return environment("log matches environment signature %r" % log_sig)
        if exit_code != 0:
            res["reading"] = "regression"
        return res

    parsed = parse_results(fmt, run.get("results_text"), run.get("root"))
    if parsed is None:
        return environment("result file missing or unparseable")
    executed = [r for r in parsed if r["outcome"] in ("passed", "failed")]
    res["executed_count"] = len(executed)
    if not executed:
        return environment("no tests executed")

    entry = (baseline or {}).get(suite) or {}
    known_failing = entry.get("known_failing") or {}
    known_flaky = set(entry.get("known_flaky") or [])
    signatures = _gating_signatures(step, emulators)
    signature_failed: List[str] = []
    failed = [r for r in parsed if r["outcome"] == "failed"]
    for r in failed:
        unit_id = "%s::%s" % (suite, r["unit"])
        test_id = "%s::%s" % (unit_id, r["name"])
        res["failed_tests"].append(test_id)
        if any(sig in (r.get("message") or "") for sig in signatures):
            signature_failed.append(test_id)
        elif unit_id in known_flaky or r["name"] in (known_failing.get(unit_id) or []):
            continue
        else:
            res["new_failures"].append(test_id)
            res["new_failure_items"].append({"unit": unit_id, "name": r["name"]})
    passed = {("%s::%s" % (suite, r["unit"]), r["name"]) for r in parsed if r["outcome"] == "passed"}
    for unit_id, names in known_failing.items():
        for name in names:
            if (unit_id, name) in passed:
                res["baseline_now_passing"].append("%s::%s" % (unit_id, name))

    if res["new_failures"]:
        res["reading"] = "regression"
    elif log_sig:
        return environment("log matches environment signature %r" % log_sig)
    elif signature_failed:
        return environment("emulator signature in %d failing test(s): %s"
                           % (len(signature_failed), signature_failed[0]))
    elif exit_code not in (0, None) and not failed:
        return environment("exit code %s with no parsed failure to account for it" % exit_code)
    return res


def roll_up_verdict(step_readings: Sequence[Dict[str, Any]]) -> str:
    """Any regression -> NOT-READY (environment steps listed too); else any environment; else READY."""
    readings = [r.get("reading") for r in step_readings]
    if "regression" in readings:
        return "NOT-READY"
    if "environment" in readings:
        return "ENVIRONMENT"
    return "READY"


def run_step(step: Dict[str, Any], emulators: Iterable[Dict[str, Any]], baseline: Dict[str, Any],
             results_dir: Any, cwd: Any) -> Dict[str, Any]:
    """Pre-flight the gating emulators, run one step, read its results (L-7b)."""
    results_dir = Path(results_dir)
    gating = [e for e in (emulators or ())
              if step.get("id") in (e.get("gates_steps") or [])]
    down = [e for e in gating if not tcp_probe(e.get("host"), e.get("port"), 5)]
    if down:
        reading = read_step(step, {"launched": False}, baseline, emulators)
        reading["reading"] = "environment"
        reading["environment_reason"] = "emulator-unreachable: " + "; ".join(
            "%s (%s)" % (e.get("id"), e.get("start_hint") or "start it") for e in down)
        return reading

    results_dir.mkdir(parents=True, exist_ok=True)

    def sub(value: Any) -> str:
        return str(value).replace("{results_dir}", str(results_dir))

    command = [sub(c) for c in (step.get("command") or [])]
    workdir = Path(cwd) / (step.get("cwd") or ".")
    log_path = results_dir / "output.log"
    rc, timed_out = _run_long(command, float(step.get("timeout_minutes") or 30) * 60, log_path, workdir)

    def read_file(path: Path) -> Optional[str]:
        try:
            return path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            return None

    results_spec = step.get("results") or {}
    results_text = None
    if results_spec.get("path"):
        rpath = Path(sub(results_spec["path"]))
        results_text = read_file(rpath if rpath.is_absolute() else workdir / rpath)
    run = {"launched": rc is not None, "exit_code": rc, "timed_out": bool(timed_out),
           "log_text": read_file(log_path) or "", "results_text": results_text,
           "log_path": str(log_path), "root": str(cwd)}
    return read_step(step, run, baseline, emulators)


def merge_recording(runs: Sequence[Optional[Sequence[Dict[str, str]]]]) -> Optional[Dict[str, Any]]:
    """Two or more runs' failures -> ``known_failing`` (failed in every run) and ``known_flaky``.

    ``runs`` holds one list of ``{"unit", "name"}`` per run, or None for a run that read environment,
    which makes the whole recording None (nothing is written).
    """
    if not runs or any(r is None for r in runs):
        return None
    per_run = [{(f["unit"], f["name"]) for f in r} for r in runs]
    everywhere = set.intersection(*per_run)
    anywhere = set.union(*per_run)
    failing: Dict[str, List[str]] = {}
    for unit, name in sorted(everywhere):
        failing.setdefault(unit, []).append(name)
    flaky = sorted({unit for unit, _ in anywhere - everywhere})
    return {"known_failing": failing, "known_flaky": flaky}


def run_recording(config: Dict[str, Any], cwd: Any, results_dir: Any, out_path: Any, commit: str,
                  default_branch: str = "master", suites: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """L-8: measure the default branch twice and write the failing-test baseline.

    Writes nothing when any step reads environment (an unreachable emulator, a timeout, a missing
    result file) or when a build step fails. A signature-matched failure is never recorded.
    """
    steps = list(((config or {}).get("verification") or {}).get("steps") or [])
    if suites:
        steps = [s for s in steps if s.get("suite") in suites or s.get("id") in suites]
    emulators = list((config or {}).get("emulators") or [])
    per_suite: Dict[str, List[Optional[List[Dict[str, str]]]]] = {}
    for run_no in (1, 2):
        for step in steps:
            reading = run_step(step, emulators, {}, Path(results_dir) / ("run%d" % run_no) / step["id"], cwd)
            if reading["reading"] == "environment":
                return {"outcome": "environment-failure", "gate": "record-baseline",
                        "detail": "step %s read environment: %s" % (step.get("id"), reading.get("environment_reason"))}
            if (step.get("results") or {}).get("format") == "exit-code":
                if reading["reading"] != "ok":
                    return {"outcome": "environment-failure", "gate": "record-baseline",
                            "detail": "step %s failed on the default branch, so nothing can be measured"
                                      % step.get("id")}
                continue
            suite = step.get("suite", step.get("id"))
            runs = per_suite.setdefault(suite, [])
            while len(runs) < run_no:
                runs.append([])
            runs[run_no - 1].extend({"unit": i["unit"], "name": i["name"]} for i in reading["new_failure_items"])
    out = Path(out_path)
    existing = _read_json(out) if out.exists() else None
    document: Dict[str, Any] = dict(existing) if isinstance(existing, dict) else {}
    for suite, runs in sorted(per_suite.items()):
        merged = merge_recording(runs)
        if merged is None:
            return {"outcome": "environment-failure", "gate": "record-baseline",
                    "detail": "suite %s did not produce two readings" % suite}
        document[suite] = {"measured_on": default_branch, "measured_at_commit": commit, "runs": 2,
                           "known_failing": merged["known_failing"], "known_flaky": merged["known_flaky"],
                           "note": "recorded by land_contract.py --record-baseline"}
    _atomic_write(out, json.dumps(document, indent=2, sort_keys=True) + "\n")
    return {"outcome": "baseline-recorded", "gate": "record-baseline",
            "detail": "recorded %d suite(s) at %s" % (len(per_suite), commit), "suites": sorted(per_suite)}


# ---------------------------------------------------------------------------
# Conflict policy (L-6)
# ---------------------------------------------------------------------------
def classify_conflict(path: str, config: Dict[str, Any]) -> str:
    """``union``, ``regenerate`` or ``halt``: the policy is closed."""
    if any(path_matches(path, [e.get("glob", "")]) for e in (config or {}).get("unionPaths") or []):
        return "union"
    if any(path_matches(path, r.get("paths") or []) for r in (config or {}).get("regenerators") or []):
        return "regenerate"
    return "halt"


def union_entry_key(path: str, config: Dict[str, Any]) -> str:
    for entry in (config or {}).get("unionPaths") or []:
        if path_matches(path, [entry.get("glob", "")]):
            return entry.get("entryKey", "heading")
    return "heading"


_HEADING_KEY = re.compile(r"^#{2,4}\s+(.*\S)\s*$")
_INDEX_KEY = re.compile(r"^\s*-\s*\[[^\]]*\]\(([^)\s]+)")


def _entry_key(line: str, kind: str) -> Optional[str]:
    match = (_INDEX_KEY if kind == "index-link" else _HEADING_KEY).match(line)
    return match.group(1).strip() if match else None


def _align(base: List[str], side: List[str]) -> Optional[List[List[str]]]:
    """Insertions per base gap if ``base`` is a subsequence of ``side`` (leftmost match), else None."""
    gaps: List[List[str]] = [[] for _ in range(len(base) + 1)]
    j = 0
    for line in side:
        if j < len(base) and line == base[j]:
            j += 1
        else:
            gaps[j].append(line)
    return gaps if j == len(base) else None


def merge_union(base: str, ours: str, theirs: str, entry_key: str) -> Dict[str, Any]:
    """Union two edits of a registry file. Admissible only when each side only INSERTED lines.

    Then a duplicate check over the inserted lines only, keyed by ``entry_key`` (a heading's text or a
    ``- [Title](file.md)`` link target). A key halts when its count in the result exceeds the larger of
    its base count and one, so repeats already in the base never fire.
    """
    base_l, ours_l, theirs_l = base.splitlines(), ours.splitlines(), theirs.splitlines()
    g_ours, g_theirs = _align(base_l, ours_l), _align(base_l, theirs_l)
    if g_ours is None or g_theirs is None:
        return {"ok": False, "text": "",
                "reason": "a side edited or deleted a base line; only insert-only hunks can be united"}
    merged: List[str] = []
    inserted: List[str] = []
    for i in range(len(base_l) + 1):
        a, b = g_ours[i], g_theirs[i]
        block = a if a == b else a + b
        merged.extend(block)
        inserted.extend(block)
        if i < len(base_l):
            merged.append(base_l[i])
    counts_result: Dict[str, int] = {}
    counts_base: Dict[str, int] = {}
    for line in merged:
        key = _entry_key(line, entry_key)
        if key is not None:
            counts_result[key] = counts_result.get(key, 0) + 1
    for line in base_l:
        key = _entry_key(line, entry_key)
        if key is not None:
            counts_base[key] = counts_base.get(key, 0) + 1
    for line in inserted:
        key = _entry_key(line, entry_key)
        if key is not None and counts_result[key] > max(counts_base.get(key, 0), 1):
            return {"ok": False, "text": "",
                    "reason": "the entry %r would appear %d times" % (key, counts_result[key])}
    trailing = "\n" if (base.endswith("\n") or ours.endswith("\n") or theirs.endswith("\n")) else ""
    return {"ok": True, "text": "\n".join(merged) + trailing, "reason": ""}


# ---------------------------------------------------------------------------
# Gate pieces (pure)
# ---------------------------------------------------------------------------
def evaluate_children(child_ids: Sequence[Any], read: Optional[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    """L-4: every child id must be listed on the parent issue and CLOSED; anything unreadable is unverifiable."""
    if not isinstance(read, dict) or not isinstance(read.get("nodes"), list):
        return {"outcome": "unverifiable"}
    nodes = read["nodes"]
    if child_ids and not nodes:
        return {"outcome": "unverifiable"}
    total = read.get("totalCount")
    if isinstance(total, int) and total > len(nodes):
        return {"outcome": "unverifiable"}
    states = {str(n.get("number")): str(n.get("state") or "").upper() for n in nodes if isinstance(n, dict)}
    if any(str(cid) not in states for cid in child_ids):
        return {"outcome": "unverifiable"}
    if any(states[str(cid)] != "CLOSED" for cid in child_ids):
        return {"outcome": "children-still-open"}
    return {"outcome": None}


#: P3 to P14 in order. ``p8_verification_verdict`` is read between P7 and P9.
GATE_ORDER: Tuple[Tuple[str, str], ...] = (
    ("p3_blocked_verdict", "blocked-verdict"),
    ("p4_children_still_open", "children-still-open"),
    ("p4_unverifiable", "unverifiable"),
    ("p6_environment_failure", "environment-failure"),
    ("p7_unresolvable_conflict", "unresolvable-conflict"),
    ("p7_environment_failure", "environment-failure"),
    ("p7_regeneration_failed", "regeneration-failed"),
    ("p8_verification_verdict", ""),
    ("p9_push_rejected", "push-rejected"),
    ("p10_pr_mismatch", "pr-mismatch"),
    ("p10_pr_not_ready", "pr-not-ready"),
    ("p11_link_not_verified", "link-not-verified"),
    ("p12_children_still_open", "children-still-open"),
    ("p12_master_moved", "master-moved"),
    ("p12_head_moved", "head-moved"),
    ("p12_not_mergeable", "not-mergeable"),
    ("p13_merge_refused", "merge-refused"),
    ("p14_merge_unconfirmed", "merge-unconfirmed"),
)


def evaluate_gates(facts: Dict[str, Any]) -> Optional[str]:
    """The first halt over P3 to P14, in gate order (the order is the enforcement)."""
    for key, outcome in GATE_ORDER:
        if key == "p8_verification_verdict":
            verdict = facts.get(key)
            if verdict == "NOT-READY":
                return "verification-not-ready"
            if verdict == "ENVIRONMENT":
                return "environment-failure"
            continue
        if facts.get(key):
            return outcome
    return None


def applicable_steps(steps: Sequence[Dict[str, Any]], contract_diff: Iterable[str],
                     merge_diff: Iterable[str]) -> List[str]:
    """Step ids whose ``when_paths`` match the contract diff UNION the merge diff (L-7)."""
    changed = sorted(set(contract_diff) | set(merge_diff))
    out: List[str] = []
    for step in steps:
        wanted = step.get("when_paths")
        if not wanted or any(path_matches(p, wanted) for p in changed):
            out.append(step["id"])
    return out


def required_coverage(rows: Sequence[Dict[str, Any]], contract_diff: Iterable[str],
                      resolved_paths: Iterable[str]) -> List[str]:
    """Reviewers whose rows match the contract diff UNION the hand-resolved paths (L-7)."""
    changed = sorted(set(contract_diff) | set(resolved_paths))
    out: List[str] = []
    for row in rows:
        if row.get("reviewer") not in out and any(path_matches(p, row.get("paths") or []) for p in changed):
            out.append(row["reviewer"])
    return out


def check_configuration(config: Any, worktree: Any, results_dir: Any) -> Optional[Dict[str, str]]:
    """``landing-not-configured`` when the block is absent, has no steps, or a result path is inside the tree."""
    fail = lambda detail: {"outcome": "landing-not-configured", "detail": detail}  # noqa: E731
    if not isinstance(config, dict) or not config:
        return fail("the conventions file has no contractLanding block on the default branch")
    steps = (config.get("verification") or {}).get("steps")
    if not steps:
        return fail("contractLanding.verification.steps is empty")
    for step in steps:
        if not step.get("id"):
            return fail("a verification step has no id")
        path = (step.get("results") or {}).get("path")
        if not path:
            continue
        resolved = Path(str(path).replace("{results_dir}", str(results_dir)))
        if not resolved.is_absolute():
            resolved = Path(worktree) / resolved
        if _under(resolved, worktree):
            return fail("step %s writes its results inside the worktree (%s); use {results_dir}"
                        % (step["id"], path))
    return None


def plan_worktree_by_suffix(worktree_paths: Sequence[str], suffix: str, main_root: Any,
                            today: str) -> Dict[str, Any]:
    """L-15: the landing worktree is found by git, not by date. One match reuses it; two halt.

    C1: only ``<main root>/.claude/worktrees/<8 digits><suffix>`` is a match. A worktree whose path
    merely ends with ``suffix`` (an operator's ``<date>-debug-land-<issue>``) is never adopted and
    never reset: the plan halts and names it.
    """
    lookalikes = [p for p in worktree_paths if p.replace("\\", "/").rstrip("/").endswith(suffix)]
    matches = [p for p in lookalikes if is_landing_worktree(p, main_root, suffix)]
    strangers = [p for p in lookalikes if p not in matches]
    if strangers:
        return {"outcome": "environment-failure",
                "detail": "%s ends with %s but is not a landing worktree (<main root>/.claude/worktrees/"
                          "<8 digits>%s); it is left untouched" % (" and ".join(strangers), suffix, suffix)}
    if len(matches) > 1:
        return {"outcome": "environment-failure",
                "detail": "two worktrees end with %s: %s" % (suffix, " and ".join(matches))}
    if matches:
        return {"path": matches[0], "create": False}
    return {"path": os.path.join(str(main_root), ".claude", "worktrees", "%s%s" % (today, suffix)),
            "create": True}


def plan_worktree(worktree_paths: Sequence[str], parent_issue: Any, main_root: Any,
                  today: str) -> Dict[str, Any]:
    return plan_worktree_by_suffix(worktree_paths, "-land-%s" % parent_issue, main_root, today)


def build_delivery_set(listings: Dict[str, Dict[str, str]], slug: str) -> Dict[str, Any]:
    """Merge the records and briefs found on the fetched refs. Identical copies collapse (L-10).

    ``listings`` is ``{ref: {path: text}}``. Two different records for one sub-task are
    ``unverifiable``; copies of one brief disagreeing on ``base:``, ``parent_issue:`` or ``id:`` are
    ``ambiguous-parent``.
    """
    import yaml  # PyYAML, as pr_merged.load_records

    records: Dict[str, Dict[str, Any]] = {}
    seen_text: Dict[str, str] = {}
    briefs: Dict[str, Dict[str, str]] = {}
    problem: Optional[Dict[str, str]] = None
    rec_prefix = "%s/%s/" % (RECORDS_ROOT, slug)
    for ref, files in listings.items():
        for path, text in files.items():
            posix = path.replace("\\", "/")
            if posix.startswith(rec_prefix) and posix.endswith(".yaml") and "/" not in posix[len(rec_prefix):]:
                sub_id = posix[len(rec_prefix):-len(".yaml")]
                canon = (text or "").replace("\r\n", "\n").strip()
                if sub_id in seen_text:
                    if seen_text[sub_id] != canon and problem is None:
                        problem = {"outcome": "unverifiable",
                                   "detail": "two different records for %s (second on %s)" % (sub_id, ref)}
                    continue
                try:
                    parsed = yaml.safe_load(text) or {}
                except yaml.YAMLError:
                    problem = problem or {"outcome": "unverifiable",
                                          "detail": "the record %s on %s is not valid YAML" % (path, ref)}
                    continue
                seen_text[sub_id] = canon
                records[sub_id] = parsed if isinstance(parsed, dict) else {}
            elif posix.startswith(BRIEFS_DIR + "/") and posix.endswith(".md"):
                fields = parse_frontmatter(text or "")
                if not pr_merged._brief_names_contract(fields, slug):
                    continue
                fields["_path"], fields["_ref"] = posix, ref
                if posix in briefs:
                    first = briefs[posix]
                    for key in ("base", "parent_issue", "id"):
                        if (first.get(key) or "") != (fields.get(key) or "") and problem is None:
                            problem = {"outcome": "ambiguous-parent",
                                       "detail": "the brief %s disagrees on %s: %r on %s, %r on %s"
                                                 % (posix, key, first.get(key), first["_ref"],
                                                    fields.get(key), ref)}
                    continue
                briefs[posix] = fields
    return {"records": records, "briefs": [briefs[k] for k in sorted(briefs)], "problem": problem}


def next_command_for_outcome(outcome: str, slug: str, **facts: Any) -> Dict[str, Any]:
    """The Next Command per outcome: data this script returns, never prose a skill composes."""
    advance_line = "/advance %s" % slug
    if outcome in ("landed", "already-landed"):
        return {"commands": [], "reason": "the parent pull request is merged; /advance commits the "
                                          "updated parent brief to the records draft"}
    if outcome == "not-applicable":
        return {"commands": ["/verify-before-done"],
                "reason": "no parent branch is declared, so today's ending applies"}
    if outcome == "children-still-open":
        return {"commands": [], "reason": "child issues are still open: %s"
                                          % (facts.get("open_children") or "see the detail")}
    if outcome == "landing-in-progress":
        reason = facts.get("live") or "a landing is running"
        if facts.get("dry_run"):
            reason = "dry run: P1 to P5 passed and nothing was changed"
        return {"commands": [], "reason": reason}
    if outcome == "baseline-recorded":
        return {"commands": [], "reason": "commit .claude/test-baseline.json through an ordinary pull request"}
    if outcome == "verification-not-ready":
        now = list(facts.get("new_failures") or [])
        previous = list(facts.get("previous_new_failures") or [])
        repeat = bool(now) and set(now) <= set(previous) \
            and facts.get("baseline_commit_now") != facts.get("baseline_commit_previous")
        if repeat:
            return {"commands": ["/design-first %s" % slug], "repeat_after_rerecord": True,
                    "reason": "every new failure was also new last time and the baseline was re-recorded "
                              "in between, so it is a real regression, not a missed flake"}
        suites = ", ".join(facts.get("suite_ids") or ["<suite ids>"])
        return {"commands": ["/task Re-record the failing-test baseline for %s" % suites, advance_line],
                "repeat_after_rerecord": False,
                "reason": "new failures: a flake the recording missed is caught by a fresh recording on the "
                          "default branch, which never runs this contract's code"}
    if outcome in ("blocked-verdict", "unresolvable-conflict", "regeneration-failed"):
        return {"commands": ["/design-first %s" % slug],
                "reason": "the fix is a remedy sub-task on the parent branch: %s"
                          % (REMEDIES.get(outcome) or outcome)}
    return {"commands": [advance_line], "reason": "after the operator action: %s" % (REMEDIES.get(outcome) or outcome)}


# ---------------------------------------------------------------------------
# L-11 containment scanner
# ---------------------------------------------------------------------------
SCAN_ROOTS: Tuple[str, ...] = (".claude/scripts", ".claude/hooks", ".claude/agents", ".claude/skills", "tools")
SCAN_EXTENSIONS: Tuple[str, ...] = (".py", ".ps1", ".cmd", ".sh", ".md", ".json")
SCAN_SKIP_DIRS = frozenset({"tests", "__pycache__", "node_modules", ".git"})
MERGE_ADMITTED_PATH = ".claude/scripts/land_contract.py"
PROTECTED_NAMES = frozenset({"master", "main"})
_SEPARATORS = re.compile(r"[\s\"',()\[\]]+")
_MERGE_WORDS = re.compile(r"(?<![\w.-])gh(?:\.exe)? pr merge(?![\w-])")
_API_MERGE = re.compile(r"(?<![\w.-])gh(?:\.exe)? api (?:\S+ ){0,8}?\S*pulls/\S+?/merge(?![\w-])")
_PUSH_START = re.compile(r"(?<![\w.-])git(?:\.exe)?[\s\"',()\[\]]+push\b")


def _squash(text: str) -> str:
    return _SEPARATORS.sub(" ", text)


def _names_protected_branch(token: str) -> bool:
    token = token.strip("`*.,;:!?<>{}").lstrip("+")
    if ":" in token:
        token = token.split(":", 1)[1]
    token = re.sub(r"^refs/heads/", "", token)
    return token in PROTECTED_NAMES


def scan_text(text: str) -> List[str]:
    """Pattern names found in ``text``: the merge command, the merge endpoint, a push to a protected branch."""
    found: List[str] = []
    squashed = _squash(text) + " "
    if _MERGE_WORDS.search(squashed):
        found.append("gh-pr-merge")
    if _API_MERGE.search(squashed):
        found.append("gh-api-pulls-merge")
    for match in _PUSH_START.finditer(text):
        quoted = text[max(0, match.start() - 1):match.start()] in ("\"", "'")
        tail = text[match.end():match.end() + 400]
        stop = re.search(r"[)\]]" if quoted else r"[\n;|&]", tail)
        segment = tail[:stop.start()] if stop else tail
        if any(_names_protected_branch(t) for t in _squash(segment).split()[:8]):
            found.append("git-push-protected")
            break
    return found


def scan_tree(root: Any) -> List[Tuple[str, str]]:
    """L-11: walk the file system under ``root`` and report ``(relative path, pattern)`` findings.

    ``tests`` folders are excluded (their guards hold the forbidden tuples on purpose). The merge
    command is admitted for the exact path ``.claude/scripts/land_contract.py`` only. A scan of zero
    files raises ``ValueError`` -- it must never pass vacuously.
    """
    root = Path(root)
    findings: List[Tuple[str, str]] = []
    scanned = 0
    for top in SCAN_ROOTS:
        base = root / top
        if not base.is_dir():
            continue
        for current, dirs, files in os.walk(str(base)):
            dirs[:] = sorted(d for d in dirs if d not in SCAN_SKIP_DIRS)
            for name in sorted(files):
                if not name.lower().endswith(SCAN_EXTENSIONS):
                    continue
                full = Path(current) / name
                rel = full.relative_to(root).as_posix()
                scanned += 1
                try:
                    text = full.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    findings.append((rel, "unreadable"))
                    continue
                for pattern in scan_text(text):
                    if pattern == "gh-pr-merge" and rel == MERGE_ADMITTED_PATH:
                        continue
                    findings.append((rel, pattern))
    if scanned == 0:
        raise ValueError("the containment scan found no file under %s; refusing a vacuous pass" % root)
    return findings


# ---------------------------------------------------------------------------
# Lock, phase and report files
# ---------------------------------------------------------------------------
def pid_alive(pid: Any) -> bool:
    """Is a process with this id running? Never ``os.kill(pid, 0)`` on Windows: that TERMINATES it."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        kernel = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel.OpenProcess(0x1000, 0, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return kernel.GetLastError() == 5  # access denied: it exists
        try:
            code = ctypes.c_ulong()
            if kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                return code.value == 259  # STILL_ACTIVE
            return True
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def lock_acquire(landing_dir: Path, info: Dict[str, Any]) -> Dict[str, Any]:
    """Take the ONE global lock exclusively. A holder whose process is gone is reclaimed and noted."""
    landing_dir.mkdir(parents=True, exist_ok=True)
    lock = landing_dir / "lock"
    note = None
    for _ in range(3):
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            holder = _read_json(lock)
            pid = holder.get("pid") if isinstance(holder, dict) else None
            if pid is None:
                try:
                    young = time.time() - lock.stat().st_mtime < 5
                except OSError:
                    young = False
                if young:  # a holder mid-write: not stale
                    return {"acquired": False, "holder": {}}
            elif pid_alive(pid):
                return {"acquired": False, "holder": holder}
            try:
                lock.unlink()
            except OSError:
                return {"acquired": False, "holder": holder if isinstance(holder, dict) else {}}
            note = "reclaimed a stale lock (pid %s, run %s)" % (
                pid, holder.get("run_id") if isinstance(holder, dict) else "?")
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(info, fh)
        return {"acquired": True, "note": note}
    return {"acquired": False, "holder": {}}


def lock_release(landing_dir: Path, run_id: str) -> None:
    lock = landing_dir / "lock"
    holder = _read_json(lock)
    if isinstance(holder, dict) and holder.get("run_id") == run_id:
        try:
            lock.unlink()
        except OSError:
            pass


def write_phase(contract_dir: Path, run_id: str, phase: str, worktree: Any = None,
                merge_commit: Optional[str] = None) -> None:
    previous = _read_json(contract_dir / "phase.json")
    started = previous.get("started_at") if isinstance(previous, dict) and previous.get("run_id") == run_id else None
    _atomic_write(contract_dir / "phase.json", json.dumps({
        "run_id": run_id, "phase": phase, "started_at": started or now_iso(), "heartbeat_at": now_iso(),
        "worktree": str(worktree) if worktree else (previous or {}).get("worktree") if isinstance(previous, dict) else None,
        "merge_commit": merge_commit}, indent=2) + "\n")


def write_report(contract_dir: Path, report: Dict[str, Any]) -> None:
    _atomic_write(contract_dir / "report.json", json.dumps(report, indent=2, default=str) + "\n")


def make_report(run_id: str, contract: Optional[str], outcome: str, gate: str, detail: str,
                remedy: Optional[str] = None, notes: Optional[List[str]] = None,
                **extra: Any) -> Dict[str, Any]:
    next_facts = {k: extra.pop(k) for k in list(extra) if k in (
        "new_failures", "previous_new_failures", "suite_ids", "baseline_commit_now",
        "baseline_commit_previous", "open_children", "live", "dry_run")}
    report: Dict[str, Any] = {
        "run_id": run_id, "contract": contract, "outcome": outcome, "gate": gate, "detail": detail,
        "remedy": remedy if remedy is not None else REMEDIES.get(outcome, ""),
        "parent_branch": None, "parent_issue": None, "merge_commit": None, "verification": None,
        "pull_request": None, "merged_commit": None, "parent_issue_state_after": None,
        "hand_resolved_in_merge": [], "bookkeeping_files": [], "notes": list(notes or []),
    }
    report.update(extra)
    report["next_command"] = next_command_for_outcome(outcome, contract or "", **next_facts)
    return report


def exit_code_for(outcome: str) -> int:
    if outcome in SUCCESS_EXIT:
        return EXIT_OK
    return EXIT_GH_REPO_SET if outcome == "gh-repo-set" else EXIT_HALT


# ---------------------------------------------------------------------------
# Git reading helpers used by the stages
# ---------------------------------------------------------------------------
def _git(cwd: Any, *args: str, timeout: int = 120) -> Tuple[int, str]:
    return _run(["git", "-c", "core.quotepath=false"] + list(args), cwd=cwd, timeout=timeout)


def rev_parse(cwd: Any, ref: str) -> Optional[str]:
    rc, out = _git(cwd, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
    return out.strip() if rc == 0 and out.strip() else None


def is_ancestor(cwd: Any, ancestor: str, descendant: str) -> bool:
    return _git(cwd, "merge-base", "--is-ancestor", ancestor, descendant)[0] == 0


def diff_names(cwd: Any, *args: str) -> List[str]:
    rc, out = _git(cwd, "diff", "--name-only", *args)
    return [ln.strip() for ln in out.splitlines() if ln.strip()] if rc == 0 else []


def status_snapshot(cwd: Any) -> str:
    return _git(cwd, "status", "--porcelain=v1", "--untracked-files=all")[1]


def detect_default_branch(cwd: Any) -> str:
    rc, out = _git(cwd, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if rc == 0 and out.strip().startswith("origin/"):
        return out.strip()[len("origin/"):]
    for candidate in ("master", "main"):
        if rev_parse(cwd, "refs/remotes/origin/" + candidate):
            return candidate
    return "master"


def _blob(cwd: Any, spec: str) -> Optional[str]:
    """Exact text of a staged blob (``:2:path``), keeping its trailing newline."""
    try:
        proc = subprocess.run(["git", "show", spec], cwd=str(cwd), capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.decode("utf-8", "replace") if proc.returncode == 0 else None


def _json_at(worktree: Any, path: str, ref: Optional[str]) -> Any:
    """A JSON file from ``git show <ref>:<path>`` when ``ref`` is given (absent reads as nothing), else from disk."""
    if ref is None:
        return _read_json(Path(worktree) / path)
    text = git_show(ref, path, cwd=worktree)
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def sentinel_patterns(worktree: Any, key: str, ref: Optional[str] = None) -> List[str]:
    data = _json_at(worktree, SENTINEL_PATH, ref)
    values = data.get(key) if isinstance(data, dict) else None
    return [v for v in (values or []) if isinstance(v, str)]


def profile_roots(worktree: Any, slot: str, ref: Optional[str] = None) -> List[str]:
    if ref is None:
        try:
            text = (Path(worktree) / PROFILE_PATH).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
    else:
        text = git_show(ref, PROFILE_PATH, cwd=worktree)
        if text is None:
            return []
    return list(pr_merged.load_slot(text, slot))


def expand_paths(entries: Iterable[str], worktree: Any, ref: Optional[str] = None) -> List[str]:
    """Expand ``profile:<slot>`` and ``sentinel:<key>`` tokens at run time; globs pass through.

    With ``ref`` (``origin/<default>``) the profile and the sentinel list are read from that ref, so a
    contract cannot narrow its own coverage by editing them (W2, L-16).
    """
    out: List[str] = []
    for entry in entries or ():
        if entry.startswith("profile:"):
            for root in profile_roots(worktree, entry[len("profile:"):], ref):
                out.append(root + "**" if root.endswith("/") else root)
        elif entry.startswith("sentinel:"):
            out.extend(sentinel_patterns(worktree, entry[len("sentinel:"):], ref))
        else:
            out.append(entry)
    return out


def module_tags(paths: Iterable[str], pr_title: Dict[str, Any]) -> List[str]:
    """The pull request title's module tags from the conventions ``prTitle`` block (same glob semantics)."""
    if not isinstance(pr_title, dict):
        return []
    ignore = (pr_title.get("ignore") or {}).get("globs") or []
    tags = set()
    for path in paths:
        if path_matches(path, ignore):
            continue
        hit = False
        for entry in pr_title.get("map") or []:
            if path_matches(path, entry.get("globs") or []):
                tags.add(entry["tag"])
                hit = True
        for shared in pr_title.get("shared") or []:
            if path in (shared.get("files") or []):
                tags.update(shared.get("emits") or [])
                hit = True
    order = pr_title.get("order") or []
    return [t for t in order if t in tags]


# ---------------------------------------------------------------------------
# The landing stage (P1 to P15)
# ---------------------------------------------------------------------------
class _Halt(Exception):
    def __init__(self, outcome: str, gate: str, detail: str, **extra: Any) -> None:
        super().__init__(detail)
        self.outcome, self.gate, self.detail, self.extra = outcome, gate, detail, extra


def _run_commands(commands: Sequence[Sequence[str]], cwd: Path, log_dir: Path, label: str,
                  timeout_minutes: float = 30) -> Optional[str]:
    """Run each argv in turn; returns a failure description or None."""
    for index, command in enumerate(commands):
        rc, timed_out = _run_long(command, timeout_minutes * 60,
                                  log_dir / ("%s-%d" % (label, index)) / "output.log", cwd)
        if rc is None or timed_out or rc != 0:
            return "%s command %d (%s) %s" % (
                label, index, " ".join(str(c) for c in command)[:160],
                "timed out" if timed_out else "did not start" if rc is None else "exited %s" % rc)
    return None


def _trigger_patterns(triggers: Iterable[str], worktree: Path, sentinel_file: Optional[str],
                      ref: Optional[str] = None) -> List[str]:
    out: List[str] = []
    for trig in triggers or ():
        if trig.startswith("sentinel:"):
            data = _json_at(worktree, sentinel_file or SENTINEL_PATH, ref)
            values = data.get(trig[len("sentinel:"):]) if isinstance(data, dict) else None
            out.extend(v for v in (values or []) if isinstance(v, str))
        else:
            out.append(trig)
    return out


def run_landing(args: Dict[str, Any]) -> Dict[str, Any]:
    """P1 to P15 for one contract, in the landing worktree. Always returns (and writes) a report."""
    slug, run_id = args["contract"], args["run_id"]
    roots: Optional[Dict[str, Path]] = None
    notes: List[str] = []
    try:
        roots = resolve_roots(args["project_root"])
        contract_dir = roots["landing_root"] / slug
        previous = _read_json(contract_dir / "report.json")
        report = _land(args, roots, contract_dir, notes, previous if isinstance(previous, dict) else {})
    except _Halt as halt:
        extra = dict(halt.extra)
        extra.setdefault("parent_branch", args.get("parent"))
        report_notes = list(extra.pop("notes", None) or notes)
        report = make_report(run_id, slug, halt.outcome, halt.gate, halt.detail,
                             remedy=extra.pop("remedy", None), notes=report_notes, **extra)
    except Exception as exc:  # fail closed: an unexpected error is an environment failure, never a landing
        import traceback
        report = make_report(run_id, slug, "environment-failure", "unexpected",
                             "%s: %s\n%s" % (type(exc).__name__, exc, traceback.format_exc(limit=6)),
                             notes=notes, parent_branch=args.get("parent"))
    if roots is not None:
        write_report(roots["landing_root"] / slug, report)
    return report


def _land(args: Dict[str, Any], roots: Dict[str, Path], contract_dir: Path, notes: List[str],
          previous: Dict[str, Any]) -> Dict[str, Any]:
    slug, parent, run_id = args["contract"], args["parent"], args["run_id"]
    wt = Path(args["worktree"])
    main_root = roots["main_root"]
    dry_run = bool(args.get("dry_run"))
    logs = roots["logs_dir"] / "landing" / slug / run_id

    def phase(name: str, merge_commit: Optional[str] = None) -> None:
        write_phase(contract_dir, run_id, name, worktree=args["worktree"], merge_commit=merge_commit)

    phase("p1")
    default = detect_default_branch(wt)
    default_ref = "origin/%s" % default
    mark_m = rev_parse(wt, "refs/remotes/origin/%s" % default)
    mark_p = rev_parse(wt, "refs/remotes/origin/%s" % parent)

    # The gate's configuration and baseline: ONLY `git show origin/<default>:<path>` (L-16).
    conventions_text = git_show(default_ref, CONVENTIONS_PATH, cwd=wt)
    conventions = None
    if conventions_text is not None:
        try:
            conventions = json.loads(conventions_text)
        except ValueError:
            conventions = None
    config = conventions.get("contractLanding") if isinstance(conventions, dict) else None
    protected = list((config or {}).get("protectedBranches") or [default])

    # ---- P1 identify: the Delivery record set, read from three fetched refs only -----------------
    listings: Dict[str, Dict[str, str]] = {}
    # The parent's copy is origin/<parent>. The launcher has just detached this worktree at exactly
    # that commit, so when --parent names a ref that is not fetched, HEAD IS the parent tip and the
    # topology check below reports the disagreement (ambiguous-parent) instead of a blind halt.
    parent_ref = "origin/%s" % parent if mark_p else "HEAD"
    for ref in (parent_ref, "origin/docs/%s-records" % slug, default_ref):
        if not rev_parse(wt, ref):
            continue
        rc, out = _git(wt, "ls-tree", "-r", "--name-only", ref, "--",
                       "%s/%s" % (RECORDS_ROOT, slug), BRIEFS_DIR)
        files: Dict[str, str] = {}
        for rel in (out.splitlines() if rc == 0 else []):
            text = git_show(ref, rel.strip(), cwd=wt)
            if text is None:
                raise _Halt("unverifiable", "P1", "cannot read %s at %s" % (rel, ref))
            files[rel.strip()] = text
        listings[ref] = files
    delivery = build_delivery_set(listings, slug)
    if delivery["problem"]:
        raise _Halt(delivery["problem"]["outcome"], "P1", delivery["problem"]["detail"])
    records, briefs = delivery["records"], delivery["briefs"]

    contract_file = wt / ".claude" / "concepts" / ("%s.md" % slug)
    try:
        contract_text = contract_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        raise _Halt("unverifiable", "P1", "the contract file is not in the landing worktree: %s" % contract_file)
    classification = pr_merged.classify_handoff(contract_text)
    move = pr_merged.advance(classification.sub_tasks, records, None, classification.defects)
    if move.get("action") != "complete":
        missing = [t.id for t in classification.sub_tasks if t.id not in records]
        raise _Halt("not-complete", "P1", "the contract is not complete (%s); records missing for: %s"
                    % (move.get("action"), ", ".join(missing) or "none"),
                    remedy="commit the record to docs/%s-records and push it (/pr-merged Step 3)" % slug)
    topology = pr_merged.declared_topology(slug, briefs, default, protected)
    if topology["reason"] == "parent-is-default":
        raise _Halt("parent-is-default", "P1", "the declared parent %r is the default or a protected branch"
                    % topology.get("declared_base"))
    if topology["parent_branch"] is None:
        if topology["reason"] == "ambiguous":
            raise _Halt("ambiguous-parent", "P1", "the Sub-Task Work Items disagree on base: or parent_issue:")
        raise _Halt("parent-unresolved", "P1", "no Sub-Task Work Item declares a parent branch")
    if topology["parent_branch"] != parent:
        raise _Halt("ambiguous-parent", "P1", "the briefs declare %r but the launcher passed %r"
                    % (topology["parent_branch"], parent))
    parent_issue = topology["parent_issue"]
    parent_brief = next((b for b in briefs if (b.get("branch") or "") == parent
                         and (b.get("id") or "") == (parent_issue or "")), None)
    if not parent_issue or parent_brief is None:
        raise _Halt("parent-unresolved", "P1", "no brief has branch: %s and id: %s" % (parent, parent_issue))
    parent_brief_path = parent_brief["_path"]
    child_ids = [c for c in topology["child_ids"]]
    base_report = {"parent_branch": parent, "parent_issue": parent_issue}
    if not mark_m or not mark_p:
        raise _Halt("unverifiable", "P1", "the fetched refs origin/%s and origin/%s are not both present"
                    % (default, parent), **base_report)

    def halt(outcome: str, gate: str, detail: str, **extra: Any) -> "_Halt":
        merged = dict(base_report)
        merged.update(extra)
        return _Halt(outcome, gate, detail, **merged)

    # ---- P2 environment ---------------------------------------------------------------------------
    phase("p2")
    bad = check_configuration(config, wt, logs)
    if bad:
        raise halt("landing-not-configured", "P2", bad["detail"])
    baseline_text = git_show(default_ref, BASELINE_PATH, cwd=wt)
    baseline: Dict[str, Any] = {}
    baseline_note = "absent"
    if baseline_text is None:
        notes.append("no %s on %s: every already-failing test reads as new" % (BASELINE_PATH, default_ref))
    else:
        try:
            baseline = json.loads(baseline_text)
        except ValueError:
            baseline = None  # type: ignore[assignment]
        if not isinstance(baseline, dict):
            raise halt("baseline-unreadable", "P2", "%s on %s is not a JSON object" % (BASELINE_PATH, default_ref))
        baseline_note = BASELINE_PATH
    if not gh_auth_status(cwd=wt):
        raise halt("unverifiable", "P2", "gh is not authenticated, so nothing about GitHub can be read")
    baseline_fingerprint = ",".join(sorted(str(e.get("measured_at_commit")) for e in baseline.values()
                                           if isinstance(e, dict))) or None

    facts: Dict[str, Any] = {}
    details: Dict[str, str] = {}

    def gate_check(gate: str) -> None:
        outcome = evaluate_gates(facts)
        if outcome:
            raise halt(outcome, gate, details.get(outcome) or details.get("last") or outcome)

    # ---- P3 review verdicts -----------------------------------------------------------------------
    phase("p3")
    blocked = [(tid, rec.get("review_verdict")) for tid, rec in sorted(records.items())
               if rec.get("review_verdict") is not None and rec.get("review_verdict") not in PASS_VERDICTS]
    facts["p3_blocked_verdict"] = bool(blocked)
    details["blocked-verdict"] = "blocked review verdict: " + ", ".join("%s=%s" % b for b in blocked)
    gate_check("P3")

    # ---- P4 children ------------------------------------------------------------------------------
    phase("p4")
    ev = evaluate_children(child_ids, read_children(parent_issue, cwd=wt))
    facts["p4_children_still_open"] = ev["outcome"] == "children-still-open"
    facts["p4_unverifiable"] = ev["outcome"] == "unverifiable"
    details["children-still-open"] = "child issues of #%s are still open" % parent_issue
    details["unverifiable"] = "the children of #%s could not be verified (empty, truncated, missing or unreadable)" % parent_issue
    gate_check("P4")

    # ---- P5 already landed ------------------------------------------------------------------------
    phase("p5")
    found = gh_pr_find(parent, default, cwd=wt)
    already = bool(found and str(found.get("state") or "").upper() == "MERGED"
                   and found.get("baseRefName") == default and found.get("headRefName") == parent)
    if already:
        return _finish_landed(args, "already-landed", found, found, base_report, parent_brief_path, notes,
                              run_id, slug, None, None, default, dry_run)
    if dry_run:
        raise halt("landing-in-progress", "P5",
                   "dry run: P1 to P5 passed; P6 onward was not run and nothing was changed",
                   dry_run=True, notes=notes + ["dry-run"])

    # ---- P6 setup ---------------------------------------------------------------------------------
    phase("p6")
    for entry in config.get("setup") or []:
        if (wt / entry.get("when_missing", "")).exists():
            continue
        failure = _run_commands([entry["command"]], wt / (entry.get("cwd") or "."), logs,
                                "setup-%s" % entry.get("id", "x"), float(entry.get("timeout_minutes") or 30))
        if failure:
            facts["p6_environment_failure"] = True
            details["environment-failure"] = "setup failed: " + failure
    gate_check("P6")

    # ---- P7 merge the default branch --------------------------------------------------------------
    phase("p7")
    contract_diff, merge_diff, resolved = _p7_merge(args, wt, default, mark_m, mark_p, config, logs,
                                                    parent, slug, facts, details, notes)
    gate_check("P7")
    head = rev_parse(wt, "HEAD")
    phase("p8", merge_commit=head)

    # ---- P8 verification --------------------------------------------------------------------------
    summary = _p8_verify(wt, head, config, baseline, baseline_note, baseline_fingerprint, contract_diff,
                         merge_diff, resolved, records, classification.sub_tasks, logs, contract_dir, run_id, default_ref)
    facts["p8_verification_verdict"] = summary["verdict"]
    shared = {"verification": summary, "merge_commit": head, "hand_resolved_in_merge": resolved}
    new_failures = summary.get("new_failures") or []
    suite_ids = sorted({f.split("::", 1)[0] for f in new_failures})
    prev_verification = previous.get("verification") if previous.get("outcome") == "verification-not-ready" else None
    prev_new = (prev_verification or {}).get("new_failures") or []
    prev_fp = (prev_verification or {}).get("baseline_commit")
    details["verification-not-ready"] = "verification is not READY: " + (
        "; ".join(summary.get("reasons") or []) or "new failures: " + ", ".join(new_failures))
    details["environment-failure"] = "verification could not run: " + "; ".join(
        "%s: %s" % (s["id"], s.get("environment_reason")) for s in summary["steps"]
        if s.get("reading") == "environment")
    outcome = evaluate_gates(facts)
    if outcome:
        raise halt(outcome, "P8", details[outcome], new_failures=new_failures, suite_ids=suite_ids,
                   previous_new_failures=prev_new, baseline_commit_now=baseline_fingerprint,
                   baseline_commit_previous=prev_fp, **shared)

    def stop(outcome: str, gate: str, detail: str) -> "_Halt":
        return halt(outcome, gate, detail, **shared)

    # ---- P9 push ----------------------------------------------------------------------------------
    phase("p9", merge_commit=head)
    rc, out = git_push(parent, wt, default, protected)
    if rc != 0:
        raise stop("push-rejected", "P9", "the push to %s was refused: %s" % (parent, out))

    # ---- P10 open or adopt the parent pull request ------------------------------------------------
    phase("p10", merge_commit=head)
    pr = gh_pr_find(parent, default, cwd=wt)
    if pr is None:
        title = _pr_title(parent_brief, contract_diff + merge_diff, conventions)
        body = _pr_body(parent_issue, slug, parent, default, summary, resolved)
        rc, url = gh_pr_create(default, parent, title, body, cwd=wt)
        number = _pr_number(url)
        if rc != 0 or number is None:
            raise stop("pr-not-ready", "P10", "the parent pull request could not be opened: %s" % url)
        pr = {"number": number, "url": url, "state": "OPEN", "isDraft": False, "baseRefName": default,
              "headRefName": parent}
    else:
        state = str(pr.get("state") or "").upper()
        if state != "OPEN" or pr.get("baseRefName") != default or pr.get("headRefName") != parent:
            raise stop("pr-mismatch", "P10", "pull request #%s is %s into %s; expected OPEN into %s"
                       % (pr.get("number"), state, pr.get("baseRefName"), default))
        if pr.get("isDraft"):
            rc, out = gh_pr_ready(pr["number"], cwd=wt)
            if rc != 0:
                raise stop("pr-not-ready", "P10", "pull request #%s is a draft and could not be marked ready: %s"
                           % (pr["number"], out))
    number = pr["number"]

    # ---- P11 closing link -------------------------------------------------------------------------
    phase("p11", merge_commit=head)
    # L-16 (W1): the conventions and the parent brief come from the fetched refs, never from a disk.
    brief_name = wt / parent_brief_path
    brief_text = git_show(parent_brief.get("_ref") or default_ref, parent_brief_path, cwd=wt)
    link_sources = {"conventions_text": conventions_text, "brief_text": brief_text}
    verdict = verify_closing_link(brief_name, number, cwd=wt, **link_sources)
    if verdict == "absent-repairable":
        current = gh_pr_view(number, cwd=wt)
        repaired = (current.get("body") or "").rstrip() + "\n\nCloses #%s\n" % parent_issue
        gh_pr_edit_body(number, repaired, cwd=wt)
        verdict = verify_closing_link(brief_name, number, cwd=wt, repair_attempted=True, **link_sources)
    if verdict != "linked":
        raise stop("link-not-verified", "P11", "the Closing Link verdict is %r, expected 'linked'" % verdict)

    # ---- P12 re-check, every value read fresh -----------------------------------------------------
    phase("p12", merge_commit=head)
    ev = evaluate_children(child_ids, read_children(parent_issue, cwd=wt))
    if ev["outcome"] == "unverifiable":
        raise stop("unverifiable", "P12", "the children of #%s could not be re-verified" % parent_issue)
    facts["p12_children_still_open"] = ev["outcome"] == "children-still-open"
    remote_default = git_ls_remote("refs/heads/%s" % default, cwd=wt)
    if remote_default is None:
        raise stop("unverifiable", "P12", "cannot read the %s tip from origin" % default)
    facts["p12_master_moved"] = remote_default != mark_m
    view = gh_pr_view(number, cwd=wt)
    for _ in range(5):
        if view and str(view.get("mergeable") or "").upper() == "UNKNOWN":
            time.sleep(3)
            view = gh_pr_view(number, cwd=wt)
    if not view:
        raise stop("unverifiable", "P12", "gh cannot read pull request #%s" % number)
    if view.get("baseRefName") != default or view.get("headRefName") != parent:
        raise stop("pr-mismatch", "P12", "pull request #%s is now %s into %s; expected %s into %s"
                   % (number, view.get("headRefName"), view.get("baseRefName"), parent, default))
    facts["p12_head_moved"] = view.get("headRefOid") != head
    facts["p12_not_mergeable"] = str(view.get("mergeable") or "").upper() != "MERGEABLE" or bool(view.get("isDraft"))
    details.update({"children-still-open": "a child issue was reopened while verifying",
                    "master-moved": "%s moved from %s to %s while verifying" % (default, mark_m, remote_default),
                    "head-moved": "pull request #%s head is %s, not the verified %s" % (number, view.get("headRefOid"), head),
                    "not-mergeable": "pull request #%s is %s%s" % (number, view.get("mergeable"),
                                                                   " (draft)" if view.get("isDraft") else "")})
    outcome = evaluate_gates(facts)
    if outcome:
        raise stop(outcome, "P12", details[outcome])

    # ---- P13 merge, pinned to H -------------------------------------------------------------------
    phase("p13", merge_commit=head)
    rc, out = gh_pr_merge(number, head, cwd=wt)
    if rc != 0:
        raise stop("merge-refused", "P13", "the merge was refused: %s" % out)

    # ---- P14 confirm ------------------------------------------------------------------------------
    phase("p14", merge_commit=head)
    after = gh_pr_view(number, cwd=wt)
    merge_oid = (after.get("mergeCommit") or {}).get("oid") if isinstance(after.get("mergeCommit"), dict) else None
    if str(after.get("state") or "").upper() != "MERGED" or not merge_oid:
        raise stop("merge-unconfirmed", "P14", "gh does not report pull request #%s as merged" % number)
    issue_state = gh_issue_state(parent_issue, cwd=wt) or "UNKNOWN"
    return _finish_landed(args, "landed", pr, after, base_report, parent_brief_path, notes, run_id, slug,
                          summary, head, default, dry_run, merged_commit=merge_oid, issue_state=issue_state,
                          resolved=resolved)


def _pr_number(url: str) -> Optional[int]:
    match = re.search(r"/pull/(\d+)", url or "")
    return int(match.group(1)) if match else None


def _pr_title(parent_brief: Dict[str, str], paths: List[str], conventions: Any) -> str:
    title = (parent_brief.get("title") or "").strip() or "Land the contract"
    cfg = conventions if isinstance(conventions, dict) else {}
    pattern = (cfg.get("issueTitle") or {}).get("pattern")
    if pattern:
        title = re.sub(r"^\[[A-Z-]+\]\s+", "", title) if re.match(pattern, title) else title
    tags = module_tags(paths, cfg.get("prTitle") or {})
    return "%s %s" % ("".join("[%s]" % t for t in tags), title) if tags else title


def _pr_body(parent_issue: str, slug: str, parent: str, default: str, summary: Dict[str, Any],
             resolved: List[str]) -> str:
    lines = ["Closes #%s" % parent_issue, "",
             "Contract landing of `%s`: parent branch `%s` into `%s`." % (slug, parent, default), "",
             "Verification: %s at `%s`; %d step(s) applied; new failures: %s." % (
                 summary["verdict"], summary["head"], len(summary["steps"]),
                 ", ".join(summary["new_failures"]) or "none"),
             "Baseline: %s." % summary.get("baseline", "absent")]
    if resolved:
        lines += ["", "Hand-resolved or regenerated in the merge:"] + ["- `%s`" % p for p in resolved]
    return "\n".join(lines) + "\n"


def _finish_landed(args: Dict[str, Any], outcome: str, pr: Dict[str, Any], view: Dict[str, Any],
                   base_report: Dict[str, Any], parent_brief_path: str, notes: List[str], run_id: str,
                   slug: str, summary: Optional[Dict[str, Any]], head: Optional[str], default: str,
                   dry_run: bool, merged_commit: Optional[str] = None, issue_state: Optional[str] = None,
                   resolved: Optional[List[str]] = None) -> Dict[str, Any]:
    """P15: idempotent bookkeeping. A failed removal never changes the outcome (master is already merged)."""
    merge_oid = merged_commit or ((view.get("mergeCommit") or {}).get("oid")
                                  if isinstance(view.get("mergeCommit"), dict) else None)
    if issue_state is None and base_report.get("parent_issue"):
        issue_state = gh_issue_state(base_report["parent_issue"], cwd=args["worktree"]) or "UNKNOWN"
    report = make_report(
        run_id, slug, outcome, "P14" if outcome == "landed" else "P5",
        "pull request #%s merged into %s" % (pr.get("number"), default), remedy="", notes=notes,
        pull_request={"number": pr.get("number"), "url": pr.get("url"), "base": default,
                      "head": pr.get("headRefName")},
        merged_commit=merge_oid, parent_issue_state_after=issue_state, verification=summary,
        merge_commit=head, hand_resolved_in_merge=list(resolved or []), **base_report)
    if dry_run:
        report["notes"].append("dry-run: bookkeeping skipped")
        return report
    try:
        write_bookkeeping(args["checkout"], parent_brief_path, pr, report)
        report["bookkeeping_files"] = [parent_brief_path]
    except Exception as exc:  # the merge is done: a bookkeeping problem is a note, not a halt
        report["notes"].append("bookkeeping-failed: %s" % exc)
    here = os.getcwd()
    try:
        # A process standing inside a directory blocks its removal on Windows: step out first.
        os.chdir(str(args["project_root"]))
        if not is_landing_worktree(args["worktree"], args["project_root"]):
            raise RuntimeError("not a landing worktree (<main root>/.claude/worktrees/<8 digits>-land-<issue>)")
        worktree_remove(args["worktree"])
    except Exception as exc:
        report["notes"].append("worktree-not-removed: %s" % args["worktree"])
        report["notes"].append("worktree-remove-error: %s" % exc)
    finally:
        if os.path.isdir(here):
            os.chdir(here)
    return report


def _p7_merge(args: Dict[str, Any], wt: Path, default: str, mark_m: str, mark_p: str,
              config: Dict[str, Any], logs: Path, parent: str, slug: str, facts: Dict[str, Any],
              details: Dict[str, str], notes: List[str]) -> Tuple[List[str], List[str], List[str]]:
    """Merge the default branch (record M), apply the conflict policy, regenerate, commit H.

    Returns ``(contract_diff, merge_diff, resolved_paths)``. Sets the P7 facts on a halt.
    """
    rc, base_sha = _git(wt, "merge-base", mark_m, mark_p)
    if rc != 0 or not base_sha.strip():
        facts["p7_environment_failure"] = True
        details["environment-failure"] = "no merge base between %s and %s" % (mark_m, mark_p)
        return [], [], []
    contract_diff = diff_names(wt, base_sha.strip(), mark_p)
    resolved: List[str] = []

    if is_ancestor(wt, mark_m, "HEAD"):
        head = rev_parse(wt, "HEAD")
        return contract_diff, diff_names(wt, mark_p, head), resolved  # nothing to merge: origin/<parent> holds M

    rc, out = git_merge(mark_m, wt)
    merging = _git(wt, "rev-parse", "-q", "--verify", "MERGE_HEAD")[0] == 0
    if rc != 0:
        unmerged = diff_names(wt, "--diff-filter=U")
        if not unmerged:
            _git(wt, "merge", "--abort")
            facts["p7_environment_failure"] = True
            details["environment-failure"] = "git merge failed without a conflict: %s" % out
            return contract_diff, [], resolved
        for path in unmerged:
            cls = classify_conflict(path, config)
            if cls == "halt":
                _git(wt, "merge", "--abort")
                facts["p7_unresolvable_conflict"] = True
                details["unresolvable-conflict"] = "%s conflicts and is neither a union path nor regenerated" % path
                return contract_diff, [], resolved
            if cls == "regenerate":
                failed = None
                for command in (("checkout", "--theirs", "--", path), ("add", "--", path)):
                    rc, out = _git(wt, *command)
                    if rc != 0:
                        failed = "git %s failed (exit %s): %s" % (" ".join(command), rc, out)
                        break
                if failed:
                    _git(wt, "merge", "--abort")
                    facts["p7_unresolvable_conflict"] = True
                    details["unresolvable-conflict"] = "%s cannot take the default branch's side: %s" % (path, failed)
                    return contract_diff, [], resolved
            else:
                base_t, ours_t, theirs_t = (_blob(wt, ":%d:%s" % (n, path)) for n in (1, 2, 3))
                merged = merge_union(base_t or "", ours_t or "", theirs_t or "", union_entry_key(path, config)) \
                    if ours_t is not None and theirs_t is not None else \
                    {"ok": False, "reason": "one side deleted the file"}
                if not merged["ok"]:
                    _git(wt, "merge", "--abort")
                    facts["p7_unresolvable_conflict"] = True
                    details["unresolvable-conflict"] = "%s cannot be united: %s" % (path, merged["reason"])
                    return contract_diff, [], resolved
                with open(wt / path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(merged["text"])
                _git(wt, "add", "--", path)
            resolved.append(path)
        merging = True

    if merging:
        staged = diff_names(wt, "--cached")
        touched = set(contract_diff) | set(staged)
        sentinel_file = config.get("sentinelFile")
        for regen in config.get("regenerators") or []:
            patterns = _trigger_patterns(regen.get("triggers") or [], wt, sentinel_file, "origin/%s" % default)
            if not any(path_matches(p, patterns) for p in touched):
                continue
            failure = _run_commands(regen.get("command") or [], wt, logs, "regen-%s" % regen.get("id", "x"),
                                    float(regen.get("timeout_minutes") or 30))
            if failure:
                facts["p7_regeneration_failed"] = True
                details["regeneration-failed"] = "regenerator %s failed: %s" % (regen.get("id"), failure)
                return contract_diff, staged, resolved
            rc, listing = _git(wt, "ls-files", "-m", "-d", "-o", "--exclude-standard")
            changed = [ln.strip() for ln in listing.splitlines() if ln.strip()] if rc == 0 else []
            owned = [p for p in changed if path_matches(p, regen.get("paths") or [])]
            if owned:
                _git(wt, "add", "-A", "--", *owned)
                touched.update(owned)
                resolved.extend(p for p in owned if p not in resolved)
        rc, listing = _git(wt, "ls-files", "-m", "-d", "-o", "--exclude-standard")
        stray = [ln.strip() for ln in listing.splitlines() if ln.strip()] if rc == 0 else []
        if stray:
            facts["p7_regeneration_failed"] = True
            details["regeneration-failed"] = "a regenerator wrote outside its declared paths: " + ", ".join(stray[:10])
            return contract_diff, staged, resolved
        rc, out = git_commit(wt, "Merge origin/%s into %s (contract landing of %s)" % (default, parent, slug))
        if rc != 0:
            facts["p7_environment_failure"] = True
            details["environment-failure"] = "committing the merge failed: %s" % out
            return contract_diff, staged, resolved
    head = rev_parse(wt, "HEAD")
    return contract_diff, diff_names(wt, mark_p, head), resolved


def _p8_verify(wt: Path, head: str, config: Dict[str, Any], baseline: Dict[str, Any], baseline_note: str,
               baseline_fingerprint: Optional[str], contract_diff: List[str], merge_diff: List[str],
               resolved: List[str], records: Dict[str, Dict[str, Any]], tasks: Sequence[Any],
               logs: Path, contract_dir: Path, run_id: str,
               default_ref: Optional[str] = None) -> Dict[str, Any]:
    """Gate 1: the Landing Verification of H. A READY record for H is reused while the worktree is clean."""
    cached = _read_json(contract_dir / "verification.yaml")
    if isinstance(cached, dict) and cached.get("head") == head and cached.get("verdict") == "READY" \
            and not status_snapshot(wt).strip():
        cached["reused"] = True
        return cached
    steps = list((config.get("verification") or {}).get("steps") or [])
    wanted = set(applicable_steps(steps, contract_diff, merge_diff))
    emulators = list(config.get("emulators") or [])
    before_head, before_status = rev_parse(wt, "HEAD"), status_snapshot(wt)
    readings: List[Dict[str, Any]] = []
    for step in steps:
        if step["id"] in wanted:
            readings.append(run_step(step, emulators, baseline, logs / step["id"], wt))
    after_head, after_status = rev_parse(wt, "HEAD"), status_snapshot(wt)
    tree_unchanged = before_head == after_head and before_status == after_status
    forbidden = [p for p in contract_diff if path_matches(p, config.get("forbiddenPaths") or [])
                 or path_matches(p.rsplit("/", 1)[-1], config.get("forbiddenPaths") or [])]
    rows = [dict(row, paths=expand_paths(row.get("paths") or [], wt, default_ref))
            for row in config.get("reviewCoverage") or []]
    needed = required_coverage(rows, contract_diff, resolved)
    review_files = {t.id: [f for f in getattr(t, "files", []) if f.startswith(".claude/reviews/")] for t in tasks}
    satisfied = {r for r in needed if any(
        any(f.endswith("-%s.md" % r) for f in review_files.get(tid, []))
        and records.get(tid, {}).get("review_verdict") in PASS_VERDICTS for tid in review_files)}
    missing = [r for r in needed if r not in satisfied]
    verdict = roll_up_verdict(readings)
    reasons: List[str] = []
    if not tree_unchanged:
        reasons.append("the steps changed the worktree (HEAD or git status differs)")
    if forbidden:
        reasons.append("forbidden paths in the contract diff: " + ", ".join(forbidden))
    if missing:
        reasons.append("no passing review artefact for: " + ", ".join(missing))
    if reasons:
        verdict = "NOT-READY"
    new_failures = sorted({f for r in readings for f in r["new_failures"]})
    summary = {
        "head": head, "verdict": verdict, "reasons": reasons, "contract_diff": contract_diff,
        "merge_diff": merge_diff, "resolved_paths": resolved, "new_failures": new_failures,
        "baseline": baseline_note, "baseline_commit": baseline_fingerprint,
        "steps": [{"id": r["id"], "suite": r["suite"], "reading": r["reading"], "exit_code": r.get("exit_code"),
                   "executed_count": r["executed_count"], "failed_tests": r["failed_tests"],
                   "new_failures": r["new_failures"], "baseline_now_passing": r["baseline_now_passing"],
                   "environment_reason": r["environment_reason"], "log": r.get("log")} for r in readings],
        "review_coverage": [{"reviewer": r, "satisfied": r in satisfied} for r in needed],
        "hygiene": {"tree_unchanged_by_steps": tree_unchanged, "forbidden_paths": forbidden},
    }
    if verdict == "READY" and not summary["steps"]:
        summary["reasons"] = ["configured, but no step applies"]
    summary = _readable_summary(summary)
    # JSON is valid YAML: the Verification Record is one format with one reader (_read_json above).
    _atomic_write(contract_dir / "verification.yaml", json.dumps(summary, indent=2) + "\n")
    return summary


def _readable_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    return json.loads(json.dumps(summary, default=str))


# ---------------------------------------------------------------------------
# The recording stage
# ---------------------------------------------------------------------------
def run_record_baseline(args: Dict[str, Any]) -> Dict[str, Any]:
    """``--stage record-baseline``: measure the default branch twice in the baseline worktree."""
    run_id = args["run_id"]
    roots: Optional[Dict[str, Path]] = None
    try:
        roots = resolve_roots(args["project_root"])
        report_dir = roots["landing_root"] / "_baseline"
        wt = Path(args["worktree"])
        write_phase(report_dir, run_id, "record", worktree=wt)
        default = detect_default_branch(wt)
        text = git_show("origin/%s" % default, CONVENTIONS_PATH, cwd=wt)
        try:
            config = (json.loads(text) if text else {}).get("contractLanding")
        except ValueError:
            config = None
        logs = roots["logs_dir"] / "landing" / "_baseline" / run_id
        bad = check_configuration(config, wt, logs)
        if bad:
            report = make_report(run_id, None, "landing-not-configured", "record-baseline", bad["detail"])
        else:
            failure = None
            for entry in config.get("setup") or []:
                if not (wt / entry.get("when_missing", "")).exists():
                    failure = _run_commands([entry["command"]], wt / (entry.get("cwd") or "."), logs,
                                            "setup-%s" % entry.get("id", "x"),
                                            float(entry.get("timeout_minutes") or 30))
                    if failure:
                        break
            if failure:
                report = make_report(run_id, None, "environment-failure", "record-baseline",
                                     "setup failed: " + failure)
            else:
                result = run_recording(config, wt, logs, args["out"], rev_parse(wt, "HEAD") or "",
                                       default_branch=default, suites=args.get("suites") or None)
                report = make_report(run_id, None, result["outcome"], "record-baseline", result["detail"],
                                     suites=result.get("suites"))
    except Exception as exc:
        import traceback
        report = make_report(run_id, None, "environment-failure", "unexpected",
                             "%s: %s\n%s" % (type(exc).__name__, exc, traceback.format_exc(limit=6)))
    if roots is not None:
        write_report(roots["landing_root"] / "_baseline", report)
    return report


# ---------------------------------------------------------------------------
# The launcher (P0), --status, and the baseline launch
# ---------------------------------------------------------------------------
def _emit(report: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print("%s: %s" % (report.get("outcome"), report.get("detail")))
        if report.get("remedy"):
            print("remedy: %s" % report["remedy"])
        nc = report.get("next_command") or {}
        print("next command: %s" % (", then ".join(nc.get("commands") or []) or "none - %s" % nc.get("reason")))


def read_status(landing_dir: Path, slug: Optional[str]) -> Dict[str, Any]:
    """The runtime root's story: a live run, an interrupted run, the last report, or nothing. Mutates nothing."""
    lock = _read_json(landing_dir / "lock")
    report = _read_json(landing_dir / slug / "report.json") if slug else None
    if isinstance(lock, dict) and lock:
        phase = _read_json(landing_dir / str(lock.get("contract") or "_baseline") / "phase.json")
        if pid_alive(lock.get("pid")):
            return {"state": "live", "lock": lock, "phase": phase}
        if isinstance(report, dict) and report.get("run_id") == lock.get("run_id"):
            return {"state": "report", "report": report}
        return {"state": "interrupted", "lock": lock, "phase": phase}
    if isinstance(report, dict):
        return {"state": "report", "report": report}
    return {"state": "none"}


def _briefs_on_disk(checkout: Path, slug: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    directory = checkout / BRIEFS_DIR
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.md")):
        try:
            fields = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if fields and pr_merged._brief_names_contract(fields, slug):
            fields["_path"] = "%s/%s" % (BRIEFS_DIR, path.name)
            out.append(fields)
    return out


def _resolve_slug(checkout: Path, given: str) -> str:
    name = Path(given).name
    if name.endswith(".md"):
        return name[:-3]
    if (checkout / ".claude" / "concepts" / ("%s.md" % name)).is_file():
        return name
    matches = sorted((checkout / ".claude" / "concepts").glob("*%s*.md" % name))
    return matches[0].stem if len(matches) == 1 else name


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Land a completed contract's parent branch on the default branch.")
    ap.add_argument("--contract", help="contract slug")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--dry-run", action="store_true", help="stop the landing after P5; change nothing")
    ap.add_argument("--status", action="store_true", help="report a live, interrupted or last run; mutate nothing")
    ap.add_argument("--record-baseline", action="store_true", help="record the failing-test baseline")
    ap.add_argument("--suite", action="append", default=[], help="with --record-baseline: only this suite")
    ap.add_argument("--stage", choices=("land", "record-baseline"), help=argparse.SUPPRESS)
    ap.add_argument("--probe", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--parent", help=argparse.SUPPRESS)
    ap.add_argument("--project-root", help=argparse.SUPPRESS)
    ap.add_argument("--checkout", help=argparse.SUPPRESS)
    ap.add_argument("--run-id", help=argparse.SUPPRESS)
    ap.add_argument("--worktree", help=argparse.SUPPRESS)
    ap.add_argument("--out", help=argparse.SUPPRESS)
    args = ap.parse_args(list(sys.argv[1:] if argv is None else argv))

    if args.stage:
        if args.probe:
            print("land-stage-ok")
            return EXIT_OK
        worktree = args.worktree or os.getcwd()
        if args.stage == "land":
            report = run_landing({"contract": args.contract, "parent": args.parent,
                                  "project_root": args.project_root, "checkout": args.checkout,
                                  "run_id": args.run_id, "worktree": worktree, "dry_run": args.dry_run})
        else:
            report = run_record_baseline({"project_root": args.project_root, "checkout": args.checkout,
                                          "run_id": args.run_id, "worktree": worktree, "out": args.out,
                                          "suites": args.suite})
        _emit(report, True)
        return exit_code_for(report["outcome"])

    if not args.contract and not args.record_baseline:
        ap.error("--contract is required (or --record-baseline)")
    return launch(args)


def launch(args: "argparse.Namespace") -> int:
    """P0 and the other launcher duties, from the operator's checkout."""
    rc, top = _run(["git", "rev-parse", "--show-toplevel"], cwd=os.getcwd())
    if rc != 0 or not top.strip():
        print(json.dumps({"error": "not-a-repository", "detail": top}))
        return 2
    checkout = Path(top.strip())
    try:
        roots = resolve_roots(checkout)
    except RuntimeError as exc:
        print(json.dumps({"error": "environment-failure", "detail": str(exc)}))
        return EXIT_HALT
    main_root, landing_dir = roots["main_root"], roots["landing_root"]
    baseline_run = bool(args.record_baseline)
    slug = None if baseline_run else _resolve_slug(checkout, args.contract)
    scope_dir = landing_dir / (slug or "_baseline")

    if args.status:
        status = read_status(landing_dir, slug)
        print(json.dumps(status, indent=2, default=str) if args.json else
              "state: %s" % status["state"])
        return EXIT_OK

    run_id = new_run_id()
    notes: List[str] = []

    def finish(outcome: str, gate: str, detail: str, remedy: Optional[str] = None, **extra: Any) -> int:
        report = make_report(run_id, slug, outcome, gate, detail, remedy=remedy, notes=notes, **extra)
        write_report(scope_dir, report)
        _emit(report, args.json)
        return exit_code_for(outcome)

    taken = lock_acquire(landing_dir, {"pid": os.getpid(), "run_id": run_id,
                                       "kind": "record-baseline" if baseline_run else "land",
                                       "contract": slug, "started_at": now_iso()})
    if not taken["acquired"]:
        holder = taken.get("holder") or {}
        phase = _read_json(landing_dir / str(holder.get("contract") or "_baseline") / "phase.json") or {}
        live = "a %s run for %s is live (pid %s, started %s, phase %s)" % (
            holder.get("kind"), holder.get("contract"), holder.get("pid"), holder.get("started_at"),
            phase.get("phase"))
        return finish("landing-in-progress", "P0", live, live=live)
    if taken.get("note"):
        notes.append(taken["note"])
    try:
        if baseline_run:
            return _launch_baseline(args, checkout, roots, run_id, finish, scope_dir)
        return _launch_land(args, checkout, roots, slug or "", run_id, finish, scope_dir)
    finally:
        lock_release(landing_dir, run_id)


def _launch_land(args: "argparse.Namespace", checkout: Path, roots: Dict[str, Path], slug: str, run_id: str,
                 finish: Any, scope_dir: Path) -> int:
    main_root, landing_dir = roots["main_root"], roots["landing_root"]
    default = detect_default_branch(checkout)
    known = _read_json_from_git(checkout, "origin/%s" % default, CONVENTIONS_PATH)
    protected = list(((known or {}).get("contractLanding") or {}).get("protectedBranches") or [default])
    disk_briefs = _briefs_on_disk(checkout, slug)
    topology = pr_merged.declared_topology(slug, disk_briefs, default, protected)
    if topology["reason"] == "parent-is-default" and topology.get("declared_base") != default:
        return finish("parent-is-default", "P0", "the declared parent %r is a protected branch"
                      % topology.get("declared_base"))
    if topology["reason"] in ("parent-is-default", "none-declared"):
        return finish("not-applicable", "P0", "no parent branch is declared; the contract is landed the "
                      "ordinary way", remedy="")
    if topology["reason"] == "ambiguous":
        return finish("ambiguous-parent", "P0", "the Sub-Task Work Items disagree on base: or parent_issue:")
    parent, parent_issue = topology["parent_branch"], topology["parent_issue"]
    if not parent_issue:
        return finish("parent-unresolved", "P0", "the Sub-Task Work Items name no parent issue")

    if os.environ.get("GH_REPO"):
        return finish("gh-repo-set", "P0", "GH_REPO is set, which would retarget every gh call")

    refspecs = ["+refs/heads/%s:refs/remotes/origin/%s" % (b, b) for b in (parent, default)]
    rc, out = _run(["git", "fetch", "origin"] + refspecs, cwd=main_root, timeout=300)
    if rc != 0:
        return finish("unverifiable", "P0", "git fetch failed: %s" % out)
    records_branch = "docs/%s-records" % slug
    _run(["git", "fetch", "origin", "+refs/heads/%s:refs/remotes/origin/%s" % (records_branch, records_branch)],
         cwd=main_root, timeout=300)

    refs = [r for r in ("origin/%s" % parent, "origin/%s" % records_branch, "origin/%s" % default)
            if rev_parse(main_root, r)]
    absent = [b["_path"] for b in disk_briefs
              if not any(_run(["git", "cat-file", "-e", "%s:%s" % (r, b["_path"])], cwd=main_root)[0] == 0
                         for r in refs)]
    if absent:
        return finish("not-complete", "P0", "briefs on the operator's disk are on none of the fetched refs: "
                      + ", ".join(absent), remedy="; ".join("commit and push the brief %s" % p for p in absent))

    local = "refs/heads/%s" % parent
    if rev_parse(main_root, local) and not is_ancestor(main_root, local, "refs/remotes/origin/%s" % parent):
        return finish("parent-diverged", "P0", "the local %s has commits origin/%s lacks" % (parent, parent))

    try:
        plan = plan_worktree(list_worktrees(main_root), parent_issue, main_root, datetime.now().strftime("%Y%m%d"))
    except RuntimeError as exc:
        return finish("environment-failure", "P0", str(exc))
    if "outcome" in plan:
        return finish(plan["outcome"], "P0", plan["detail"])
    path = Path(plan["path"])
    try:
        if plan["create"]:
            rc, out = _run(["git", "worktree", "add", "--detach", str(path), "origin/%s" % parent],
                           cwd=main_root, timeout=300)
            if rc != 0:
                return finish("environment-failure", "P0", "cannot create the landing worktree: %s" % out)
        if plan["create"]:
            write_phase(scope_dir, run_id, "p0", worktree=path)  # this run made it, so this run may record it
        worktree_reset(path, main_root, slug, ref="origin/%s" % parent)  # on reuse phase.json must already name it
        write_phase(scope_dir, run_id, "p0", worktree=path)
    except (ValueError, RuntimeError) as exc:
        return finish("environment-failure", "P0", str(exc))

    script = path / ".claude" / "scripts" / "land_contract.py"
    if not script.is_file():
        return finish("environment-failure", "P0", "the landing code is absent at origin/%s: %s" % (parent, script))
    if not probe_stage(str(script)):
        return finish("environment-failure", "P0", "the worktree's land_contract.py does not accept --stage "
                      "land; the launcher never lands with its own code (L-16)")

    argv = [sys.executable, "-B", str(script), "--stage", "land", "--contract", slug, "--parent", parent,
            "--project-root", str(main_root), "--checkout", str(checkout), "--run-id", run_id,
            "--worktree", str(path)]
    if args.dry_run:
        argv.append("--dry-run")
    argv.append("--json")
    exit_rc = exec_stage(argv, cwd=str(path))
    report = _read_json(scope_dir / "report.json")
    if isinstance(report, dict) and report.get("run_id") == run_id:
        return exit_code_for(str(report.get("outcome")))
    return finish("environment-failure", "P0", "the landing stage exited %s without writing a report for "
                  "run %s" % (exit_rc, run_id))


def _read_json_from_git(cwd: Any, ref: str, path: str) -> Any:
    text = git_show(ref, path, cwd=cwd)
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def _launch_baseline(args: "argparse.Namespace", checkout: Path, roots: Dict[str, Path], run_id: str,
                     finish: Any, scope_dir: Path) -> int:
    main_root = roots["main_root"]
    default = detect_default_branch(checkout)
    rc, out = _run(["git", "fetch", "origin", "+refs/heads/%s:refs/remotes/origin/%s" % (default, default)],
                   cwd=main_root, timeout=300)
    if rc != 0:
        return finish("unverifiable", "P0", "git fetch failed: %s" % out)
    try:
        plan = plan_worktree_by_suffix(list_worktrees(main_root), "-land-baseline", main_root,
                                       datetime.now().strftime("%Y%m%d"))
    except RuntimeError as exc:
        return finish("environment-failure", "P0", str(exc))
    if "outcome" in plan:
        return finish(plan["outcome"], "P0", plan["detail"])
    path = Path(plan["path"])
    try:
        if plan["create"]:
            rc, out = _run(["git", "worktree", "add", "--detach", str(path), "origin/%s" % default],
                           cwd=main_root, timeout=300)
            if rc != 0:
                return finish("environment-failure", "P0", "cannot create the baseline worktree: %s" % out)
        if plan["create"]:
            write_phase(scope_dir, run_id, "p0", worktree=path)
        worktree_reset(path, main_root, "_baseline", ref="origin/%s" % default)
        write_phase(scope_dir, run_id, "p0", worktree=path)
    except (ValueError, RuntimeError) as exc:
        return finish("environment-failure", "P0", str(exc))
    script = path / ".claude" / "scripts" / "land_contract.py"
    if not script.is_file() or not probe_stage(str(script)):
        return finish("environment-failure", "P0", "the baseline worktree has no land_contract.py that "
                      "accepts --stage")
    argv = [sys.executable, "-B", str(script), "--stage", "record-baseline", "--project-root", str(main_root),
            "--checkout", str(checkout), "--run-id", run_id, "--worktree", str(path),
            "--out", str(checkout / BASELINE_PATH)]
    for suite in args.suite:
        argv += ["--suite", suite]
    argv.append("--json")
    exit_rc = exec_stage(argv, cwd=str(path))
    report = _read_json(scope_dir / "report.json")
    if isinstance(report, dict) and report.get("run_id") == run_id:
        return exit_code_for(str(report.get("outcome")))
    return finish("environment-failure", "P0", "the recording stage exited %s without writing a report" % exit_rc)


if __name__ == "__main__":
    sys.exit(main())
