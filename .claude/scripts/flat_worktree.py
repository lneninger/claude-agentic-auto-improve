#!/usr/bin/env python3
"""
flat_worktree.py -- plan, create or reuse a FLAT worktree (contract
2026-10-07-worktree-isolation-by-default, I-4 and I-5).

A flat worktree is a linked worktree whose root sits directly in
``<main checkout>/.claude/worktrees/``, so its path holds exactly one worktree
segment. A worktree inside another worktree is nested and is refused: a nested
path broke the SqlClient ``SNI.dll`` load.

Usage:
  py -3 .claude/scripts/flat_worktree.py --describe
  py -3 .claude/scripts/flat_worktree.py --create --action A --slug S [--date YYYYMMDD]
        ( --base BRANCH --branch NEW | --existing --branch B | --detached REF )

Both print one JSON object (the Flat worktree plan): ``main_root``, ``name``, ``path``,
``branch`` (or null), ``source``, ``current_tree`` and ``outcome``. ``outcome`` is ``created``,
``reused``, or ``refused: <nested | branch-in-main-checkout | path-taken | fetch-failed |
git-failed>``. Exit 0 for created or reused (and for ``--describe``), 3 for a refusal.

Rules this module keeps:
  * The main checkout root comes only from ``main_checkout_root`` (it reads ``.git`` entries);
    ``git rev-parse --git-common-dir`` is never run.
  * It never runs ``switch`` or ``checkout`` in any tree, so the main checkout's HEAD, index and
    working files are byte-identical before and after every call (I-4).
  * A name is ``<YYYYMMDD>-<action>-<slug>``, cut at a hyphen to at most 60 characters; a taken
    name gets ``-2`` to ``-9``, then ``path-taken`` (I-5).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import _claude_paths as _cp

NAME_LIMIT = 60
MAX_SUFFIX = 9
WORKTREES_SEGMENT = "/.claude/worktrees/"

#: A runner: ``run(cmd) -> (exit code, stdout)``. ``pr_merged._run`` is one.
Run = Callable[[List[str]], Tuple[int, str]]


def today() -> str:
    """Today's date as ``YYYYMMDD``."""
    return datetime.now().strftime("%Y%m%d")


def _cut(full: str, limit: int) -> str:
    """``full`` cut at a hyphen to at most ``limit`` characters."""
    if len(full) <= limit:
        return full
    if full[limit:limit + 1] == "-":
        return full[:limit]
    head = full[:limit]
    return head.rsplit("-", 1)[0] if "-" in head else head


def flat_name(action: str, slug: str, date: Optional[str] = None, suffix: int = 1) -> str:
    """``<date>-<action>-<slug>`` (at most 60 characters), plus ``-<suffix>`` when ``suffix`` > 1."""
    full = "%s-%s-%s" % (date or today(), action, slug)
    if suffix <= 1:
        return _cut(full, NAME_LIMIT)
    tail = "-%d" % suffix
    return _cut(full, NAME_LIMIT - len(tail)) + tail


def worktrees_dir(main_root: str) -> str:
    """``<main root>/.claude/worktrees``."""
    return os.path.join(main_root, ".claude", "worktrees")


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def is_flat(main_root: str, path: str) -> bool:
    """True when ``path``'s parent is exactly ``<main root>/.claude/worktrees`` and it holds one segment."""
    name = os.path.basename(os.path.normpath(path))
    if name in ("", ".", ".."):
        return False
    if _norm(os.path.dirname(os.path.normpath(os.path.abspath(path)))) != _norm(worktrees_dir(main_root)):
        return False
    slashed = os.path.normcase(os.path.abspath(path)).replace("\\", "/") + "/"
    return slashed.count(WORKTREES_SEGMENT) <= 1


def plan_path(main_root: str, action: str, slug: str, date: Optional[str] = None,
              exists: Callable[[str], bool] = os.path.exists) -> Tuple[str, Optional[str], Optional[str]]:
    """``(name, path, refusal)``: the first free flat path, or why there is none.

    ``refusal`` is ``nested`` (the name climbs, nests or holds a separator) or ``path-taken``
    (``-2`` to ``-9`` are all in use). Nothing is created.
    """
    first = flat_name(action, slug, date)
    if not first or re.search(r"[\\/:]|\.\.", first):
        return first, None, "nested"
    for number in range(1, MAX_SUFFIX + 1):
        name = flat_name(action, slug, date, number)
        path = os.path.join(worktrees_dir(main_root), name)
        if not is_flat(main_root, path):
            return name, None, "nested"
        if not exists(path):
            return name, path, None
    return first, None, "path-taken"


def add_worktree(run: Run, path: str, *, branch: Optional[str] = None, start: Optional[str] = None,
                 detach: bool = False) -> Tuple[int, str]:
    """``git worktree add`` through ``run``. Never ``switch`` or ``checkout``.

    ``branch`` with ``start`` cuts a new branch at ``start``; ``branch`` alone checks the existing
    branch out there; ``detach`` with ``start`` leaves a detached HEAD at ``start``.
    """
    cmd = ["git", "worktree", "add"]
    if detach:
        cmd += ["--detach", path] + ([start] if start else [])
    elif branch and start:
        cmd += ["-b", branch, path, start]
    else:
        cmd += [path] + ([branch] if branch else [])
    return run(cmd)


# ---------------------------------------------------------------------------
# Real-process helpers (the CLI side)
# ---------------------------------------------------------------------------
def _git(cwd: str, *args: str) -> Tuple[int, str, str]:
    try:
        p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", "%s: %s" % (type(exc).__name__, exc)


def worktree_entries(cwd: str) -> List[Dict[str, Any]]:
    """``git worktree list --porcelain`` as dicts: path, head, branch (short name or None), detached.

    The first entry is the main worktree.
    """
    code, out, _err = _git(cwd, "worktree", "list", "--porcelain")
    if code != 0:
        return []
    entries: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for line in out.splitlines() + [""]:
        if not line.strip():
            if current is not None:
                entries.append(current)
            current = None
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            current = {"path": value, "head": None, "branch": None, "detached": False}
        elif current is not None and key == "HEAD":
            current["head"] = value
        elif current is not None and key == "branch":
            current["branch"] = value[len("refs/heads/"):] if value.startswith("refs/heads/") else value
        elif current is not None and key == "detached":
            current["detached"] = True
    return entries


def describe(cwd: Optional[str] = None) -> Dict[str, Any]:
    """The tree this process stands in and its main checkout root."""
    here = os.path.realpath(cwd or os.getcwd())
    return {"main_root": _cp.main_checkout_root(here), "current_tree": _cp.tree_kind(here), "cwd": here}


def _plan(main_root: Optional[str], tree: str, name: Optional[str], path: Optional[str],
          branch: Optional[str], source: str, outcome: str, detail: str = "") -> Dict[str, Any]:
    plan: Dict[str, Any] = {"main_root": main_root, "name": name, "path": path, "branch": branch,
                            "source": source, "current_tree": tree, "outcome": outcome}
    if detail:
        plan["detail"] = detail
    return plan


def create(action: str, slug: str, *, base: Optional[str] = None, branch: Optional[str] = None,
           existing: bool = False, detached: Optional[str] = None, date: Optional[str] = None,
           cwd: Optional[str] = None) -> Dict[str, Any]:
    """Plan and create (or reuse) one flat worktree. Returns the Flat worktree plan."""
    info = describe(cwd)
    tree, main_root = info["current_tree"], info["main_root"]
    if detached is not None:
        source, plan_branch = "detached-at %s" % detached, None
    elif existing:
        source, plan_branch = "existing-branch", branch
    else:
        source, plan_branch = "new-from-base %s" % base, branch

    def refuse(reason: str, detail: str = "", name: Optional[str] = None, path: Optional[str] = None):
        return _plan(main_root, tree, name, path, plan_branch, source, "refused: " + reason, detail)

    if main_root is None:
        return refuse("git-failed", "not inside a git repository, or its git directory cannot be read")
    if detached is None and not branch:
        return refuse("git-failed", "a branch name is required")
    if detached is None and not existing and not base:
        return refuse("git-failed", "--base is required to cut a new branch")

    name, path, refusal = plan_path(main_root, action, slug, date)
    if refusal == "nested":
        return refuse("nested", "the worktree name %r would not sit directly in %s" % (name, worktrees_dir(main_root)),
                      name)

    entries = worktree_entries(main_root)
    if branch and detached is None:
        for position, entry in enumerate(entries):
            if entry.get("branch") != branch:
                continue
            if position == 0:
                return refuse("branch-in-main-checkout",
                              "the main checkout holds %s; plan a detached worktree at it instead" % branch, name)
            return _plan(main_root, tree, os.path.basename(entry["path"]), entry["path"], branch, source, "reused")
    if refusal == "path-taken":
        return refuse("path-taken", "%s-2 to %s-9 are all in use" % (name, name), name)

    assert path is not None
    path_text = path.replace("\\", "/")

    def fail(step: str, err: str) -> Dict[str, Any]:
        return refuse("git-failed", "%s failed: %s" % (step, err or "no output"), name, path)

    def run(cmd: List[str]) -> Tuple[int, str]:
        code, out, err = _git(main_root, *cmd[1:])
        return code, (out if code == 0 else (err or out))

    if detached is not None:
        if detached.startswith("origin/"):
            code, _out, err = _git(main_root, "fetch", "origin", detached[len("origin/"):])
            if code != 0:
                return refuse("fetch-failed", "git fetch origin %s: %s" % (detached[len("origin/"):], err), name, path)
        code, out = add_worktree(run, path_text, start=detached, detach=True)
        return fail("git worktree add --detach", out) if code != 0 else _plan(
            main_root, tree, name, path, None, source, "created")

    if existing:
        code, _out, _err = _git(main_root, "rev-parse", "--verify", "--quiet", "refs/heads/%s" % branch)
        if code == 0:
            code, out = add_worktree(run, path_text, branch=branch)
        else:
            code, _out, err = _git(main_root, "fetch", "origin", branch)
            if code != 0:
                return refuse("fetch-failed", "git fetch origin %s: %s" % (branch, err), name, path)
            code, out = add_worktree(run, path_text, branch=branch, start="origin/%s" % branch)
        return fail("git worktree add", out) if code != 0 else _plan(
            main_root, tree, name, path, branch, source, "created")

    code, _out, err = _git(main_root, "fetch", "origin", base)
    if code != 0:
        return refuse("fetch-failed", "git fetch origin %s: %s" % (base, err), name, path)
    code, out = add_worktree(run, path_text, branch=branch, start="origin/%s" % base)
    return fail("git worktree add -b", out) if code != 0 else _plan(
        main_root, tree, name, path, branch, source, "created")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Plan, create or reuse a flat worktree.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--describe", action="store_true", help="name the tree this process stands in")
    mode.add_argument("--create", action="store_true", help="create (or reuse) a flat worktree")
    ap.add_argument("--action", help="the action word in the folder name (task, advance, ...)")
    ap.add_argument("--slug", help="the slug in the folder name")
    ap.add_argument("--date", help="YYYYMMDD, default today")
    ap.add_argument("--base", help="cut a NEW branch from origin/<base>")
    ap.add_argument("--branch", help="the branch to create or check out")
    ap.add_argument("--existing", action="store_true", help="check an existing branch out")
    ap.add_argument("--detached", metavar="REF", help="leave a detached HEAD at REF")
    args = ap.parse_args(argv)
    if args.describe:
        print(json.dumps(describe()))
        return 0
    if not args.action or not args.slug:
        ap.error("--create needs --action and --slug")
    if sum(bool(x) for x in (args.base, args.existing, args.detached)) != 1:
        ap.error("--create needs exactly one of --base, --existing, --detached")
    plan = create(args.action, args.slug, base=args.base, branch=args.branch, existing=args.existing,
                  detached=args.detached, date=args.date)
    print(json.dumps(plan))
    return 0 if plan["outcome"] in ("created", "reused") else 3


if __name__ == "__main__":
    sys.exit(main())
