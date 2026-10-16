#!/usr/bin/env python3
"""
cleanup_delivered.py -- Delivery cleanup (contract 2026-10-15-auto-cleanup-delivered-worktrees, issue #50).

Once a contract is implemented on the default branch, the worktrees and the merged branches that belong to
its work item are only clutter. This script removes them, and only them, and only what is provably already
in ``origin/<default>``. It runs on EVERY ``/pr-merged`` and ``/advance`` call and is idempotent: until the
records pull request has merged it says "not delivered yet" and removes nothing.

Usage:
  py -3 cleanup_delivered.py --contract <slug> --from <starting dir> [--remove-remote] [--dry-run] [--json]
  py -3 cleanup_delivered.py --print-main-root

Exit codes: 0 cleaned or nothing-owned, 3 partial, 5 not-delivered (normal), 10 unverifiable, 2 usage.
``--json`` prints one Cleanup Report object; otherwise only its one-line ``line`` is printed.

Rules this module keeps (INV-1 to INV-9 of the contract):
  * Nothing is changed unless the contract reads ``Status: implemented`` at ``origin/<default>`` and every
    sub-task has a GitHub-verified record there (read AT the ref, never from the working tree).
  * Only the Owned set is examined: the brief's branch, ``task/<slug>/<id>``, ``docs/<slug>-records`` and the
    worktrees that hold them (or sit at the brief's path, or are this slug's advance worktree). Never the
    main checkout, never a landing worktree, never the default branch.
  * A worktree goes only when it is clean, its HEAD is in ``origin/<default>``, it is not locked, no ignored
    folder in it is itself a worktree, and nobody stands in it. A branch goes only after an ancestor check.
  * Directory links (junctions, symlinks) are removed as the link entry alone, last, right before the removal.
  * Never a forced removal, never a global tidy of stale entries, never a recursive delete of a worktree,
    never a switch or checkout in any tree.
  * A tree somebody stands in is deferred and left untouched; the next call from elsewhere clears it.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import stat
import subprocess
import sys
from typing import Any, Dict, Iterator, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# Every module is imported BEFORE any removal: a tree removed under the running script must not break an import.
import flat_worktree  # noqa: E402
import land_contract  # noqa: E402
import pr_merged  # noqa: E402

EXIT_OK, EXIT_USAGE, EXIT_PARTIAL, EXIT_NOT_DELIVERED, EXIT_UNVERIFIABLE = 0, 2, 3, 5, 10
LINE_LIMIT = 600
PROTECTED = ("master", "main")
UNSET_VALUES = ("", "none", "unknown", "null")
IS_WINDOWS = os.name == "nt"
RERUN_HINT = "runs again on the next /pr-merged or /advance"


class Halt(Exception):
    """A probe could not rename a folder back: every further mutation stops (INV-9)."""

    def __init__(self, path: str, sibling: str, exc: BaseException) -> None:
        super().__init__("%s: %s" % (path, exc))
        self.path, self.sibling, self.exc = path, sibling, exc


# ---------------------------------------------------------------------------
# Processes (git and gh are found by bare name through PATH)
# ---------------------------------------------------------------------------
def _exec(cmd: List[str]) -> Tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", "%s: %s" % (type(exc).__name__, exc)


def _git(*args: str) -> Tuple[int, str, str]:
    return _exec(["git", *args])


def _gh(*args: str) -> Tuple[int, str, str]:
    return _exec(["gh", *args])


# ---------------------------------------------------------------------------
# Text and path helpers
# ---------------------------------------------------------------------------
def _clean(text: Any) -> str:
    """Control characters removed (INV-8): a name echoed into a skill must not carry escape codes."""
    return re.sub(r"[\x00-\x1f\x7f]", "", str(text))


def _quote(text: str) -> str:
    """Single-quoted for a POSIX shell; a ``'`` inside is written ``'\\''`` (INV-6)."""
    return "'" + str(text).replace("'", "'\\''") + "'"


def _norm(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _inside(inner: str, outer: str) -> bool:
    i, o = _norm(inner), _norm(outer).rstrip("\\/")
    return i == o or i.startswith(o + os.sep)


def _real_target(path: str) -> str:
    try:
        target = os.readlink(path)
    except (OSError, ValueError):
        return ""
    target = target[4:] if target.startswith("\\\\?\\") else target
    if target and not os.path.isabs(target):
        target = os.path.join(os.path.dirname(path), target)  # a relative target is relative to the link's folder
    return os.path.normpath(target) if target else ""


@contextlib.contextmanager
def _in_dir(path: str) -> Iterator[None]:
    saved = os.getcwd()
    try:
        if os.path.isdir(path):
            os.chdir(path)
        yield
    finally:
        os.chdir(saved)


# ---------------------------------------------------------------------------
# Directory links (INV-4): found with os.lstat, never with the DirEntry helpers that differ before 3.12
# ---------------------------------------------------------------------------
def _is_link(path: str) -> bool:
    """A junction or symlink entry: the reparse-point flag on Windows, S_ISLNK elsewhere."""
    st = os.lstat(path)
    if IS_WINDOWS:
        return bool(getattr(st, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    return stat.S_ISLNK(st.st_mode)


def _is_dir_link(path: str) -> bool:
    """Whether removing the link takes ``os.rmdir`` (a directory link on Windows) rather than ``os.unlink``."""
    if not IS_WINDOWS:
        return False
    return bool(getattr(os.lstat(path), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_DIRECTORY)


def _walk(top: str) -> Iterator[Tuple[str, List[str], List[str]]]:
    """``(dir, subdirs, links)`` for every real directory under ``top``; a link is reported, never entered."""
    stack = [top]
    while stack:
        here = stack.pop()
        subdirs: List[str] = []
        links: List[str] = []
        try:
            with os.scandir(here) as it:
                names = sorted(e.name for e in it)
        except OSError:
            continue
        for name in names:
            full = os.path.join(here, name)
            try:
                if _is_link(full):
                    links.append(full)
                elif stat.S_ISDIR(os.lstat(full).st_mode):
                    subdirs.append(full)
            except OSError:
                continue
        yield here, subdirs, links
        stack.extend(d for d in subdirs if os.path.basename(d) != ".git")


def find_links(root: str, tracked: set) -> List[str]:
    """Every untracked directory or file link anywhere in the tree (a tracked link stays: git owns it)."""
    found: List[str] = []
    for _here, _subdirs, links in _walk(root):
        for link in links:
            rel = os.path.relpath(link, root).replace("\\", "/")
            if rel not in tracked:
                found.append(link)
    return found


def find_nested(root: str, ignored: List[str]) -> List[str]:
    """Ignored folders that hold a ``.git`` entry, i.e. a nested worktree git would delete with the tree."""
    nested: List[str] = []
    for rel in ignored:
        top = os.path.join(root, rel.rstrip("/"))
        try:
            if _is_link(top) or not stat.S_ISDIR(os.lstat(top).st_mode):
                continue
        except OSError:
            continue
        stack = [top]
        while stack:
            here = stack.pop()
            if os.path.lexists(os.path.join(here, ".git")):
                nested.append(os.path.relpath(here, root).replace("\\", "/"))
                continue
            stack.extend(_subdirs(here))
    return nested


def _subdirs(here: str) -> List[str]:
    """The real (non-link) sub-directories of ``here``."""
    subdirs: List[str] = []
    try:
        with os.scandir(here) as it:
            names = sorted(e.name for e in it)
    except OSError:
        names = []
    for name in names:
        full = os.path.join(here, name)
        try:
            if not _is_link(full) and stat.S_ISDIR(os.lstat(full).st_mode):
                subdirs.append(full)
        except OSError:
            continue
    return subdirs


def remove_link(path: str) -> Dict[str, Any]:
    """Remove ONE link as the entry itself, then re-check its target. Returns the Directory Link."""
    target = _real_target(path)
    kind = "junction" if IS_WINDOWS and _is_dir_link(path) else "symlink"
    link: Dict[str, Any] = {"path": path.replace("\\", "/"), "target": target.replace("\\", "/"), "kind": kind,
                            "removed": False, "target_survived": None}
    if IS_WINDOWS and _is_dir_link(path):
        os.rmdir(path)
    else:
        os.unlink(path)
    link["removed"] = True
    link["target_survived"] = os.path.exists(target) if target else None
    return link


# ---------------------------------------------------------------------------
# Delivery Reading (INV-1)
# ---------------------------------------------------------------------------
def read_delivery(slug: str) -> Dict[str, Any]:
    """The gate: fetch, then read the contract and the records AT ``origin/<default>`` and decide."""
    reading: Dict[str, Any] = {"slug": slug, "default_branch": None, "contract_status": None, "sub_tasks": [],
                               "delivered": False, "records_pull_request": None, "verdict": "not-delivered",
                               "reasons": []}
    default = pr_merged.default_branch_or_none()
    if not default:
        reading.update(verdict="unverifiable", reasons=["the default branch (origin/HEAD) cannot be read"])
        return reading
    reading["default_branch"] = default
    code, _out, err = _git("fetch", "origin", default)
    if code != 0:
        reading.update(verdict="unverifiable",
                       reasons=["git fetch origin %s failed: %s" % (default, _clean(err.strip())[:200])])
        return reading
    ref = "origin/%s" % default
    concept = "%s/%s.md" % (pr_merged.CONCEPTS_DIR.as_posix(), slug)
    text = pr_merged.file_at_commit(ref, concept)
    if text is None:
        reading["reasons"] = ["%s is not on %s" % (concept, ref)]
        return reading
    status = pr_merged.read_contract_status(text)
    classified = pr_merged.classify_handoff(text)
    records = pr_merged.load_records_at(ref, slug)
    delivery = pr_merged.load_delivery_at(ref, slug)
    ok, why = pr_merged.is_delivered(classified.sub_tasks, records, delivery, classified.defects)
    reading.update(contract_status=status, sub_tasks=[t.id for t in classified.sub_tasks], delivered=ok)
    reasons: List[str] = []
    if status != "implemented":
        open_prs = pr_merged.open_records_pull_requests(slug)
        if open_prs:
            reading["records_pull_request"] = open_prs[0].get("url") or open_prs[0].get("headRefName")
            reasons.append("records pull request %s not merged yet" % reading["records_pull_request"])
        reasons.append("the contract reads Status: %s at %s, not implemented" % (status or "none", ref))
    if not ok:
        reasons.extend(r.get("item", "") for r in why)
    reading["reasons"] = reasons
    reading["verdict"] = "delivered" if (status == "implemented" and ok) else "not-delivered"
    if reading["verdict"] == "delivered":
        reading["reasons"] = []
    return reading


# ---------------------------------------------------------------------------
# The Owned set (INV-2)
# ---------------------------------------------------------------------------
def _value(fields: Dict[str, str], key: str) -> Optional[str]:
    raw = (fields.get(key) or "").strip().strip("'\"")
    return None if raw.lower() in UNSET_VALUES else raw


def find_brief(slug: str, contract_text: str, ref: str, from_dir: str, default: str,
               records: Dict[str, Any], delivery: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """The linked brief's fields (``branch``, ``worktree``) or ``{}``: rule I-17 first, then the ``branch:`` fallback."""
    code, top, _err = _git("-C", from_dir, "rev-parse", "--show-toplevel")
    root = top.strip() if code == 0 and top.strip() else from_dir  # the tree's root, even when started in a sub-folder
    with _in_dir(root):
        path = pr_merged.find_linked_brief(contract_text, slug)
    if path is None:
        header = pr_merged.brief_header_path(contract_text)  # a brief that only exists at the ref
        path = header if header is not None and pr_merged.file_at_commit(ref, header.as_posix()) is not None else None
    if path is not None:
        text = pr_merged.file_at_commit(ref, path.as_posix())
        if text is not None:
            return pr_merged.parse_brief_frontmatter(text)
        return pr_merged.read_brief_frontmatter(path) or {}
    heads: List[Tuple[str, bool]] = []  # (branch, from the starting tree: adopted only if its brief names this slug)
    for record in [delivery] + list(records.values()):
        url = (record or {}).get("pull_request") or (record or {}).get("pr")
        if url:
            pr = pr_merged.gh_pr(url)
            if pr and pr.get("headRefName"):
                heads.append((pr["headRefName"], False))
    code, out, _err = _git("-C", from_dir, "symbolic-ref", "--short", "-q", "HEAD")
    if code == 0 and out.strip():
        heads.append((out.strip(), True))
    for head, strict in heads:
        if head in PROTECTED or head == default:
            continue
        try:
            brief = pr_merged.brief_for_branch(head, ref)
        except pr_merged.AmbiguousBrief:
            continue
        if not brief:
            continue
        named = _value(brief, "contract")
        if named and not pr_merged._names_contract(named, slug):
            continue  # that brief belongs to another contract's work item
        if strict and not named:
            continue  # the starting branch proves nothing without a brief that names this contract
        return brief
    return {}


def owned_branches(slug: str, tasks: List[str], brief: Dict[str, str]) -> Dict[str, str]:
    """Owned Branch name -> source. Order: brief, sub-tasks, records."""
    owned: Dict[str, str] = {}
    branch = _value(brief, "branch")
    if branch:
        owned[branch] = "brief-branch"
    for task_id in tasks:
        owned.setdefault(pr_merged.branch_for(slug, task_id), "sub-task")
    owned.setdefault(pr_merged.records_branch_prefix(slug), "records")
    return owned


def other_slugs(ref: str, slug: str) -> Optional[List[str]]:
    """The other contracts at the ref, or None when they cannot be listed (never an empty list on failure)."""
    code, out, _err = _git("ls-tree", "--name-only", "%s:%s" % (ref, pr_merged.CONCEPTS_DIR.as_posix()))
    if code != 0:
        return None
    return [n[:-3] for n in out.splitlines() if n.endswith(".md") and n[:-3] != slug]


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------
class Run:
    """State of one cleanup run."""

    def __init__(self, slug: str, main_root: str, ref: str, default: str, remove_remote: bool, dry_run: bool,
                 standing: List[str]) -> None:
        self.slug, self.main_root, self.ref, self.default = slug, main_root, ref, default
        self.remove_remote, self.dry_run, self.standing = remove_remote, dry_run, standing
        self.items: List[Dict[str, Any]] = []
        self.removed_paths: List[str] = []
        self.finish_needed = False
        self.repair: List[str] = []
        self.halted = False

    def add(self, item: Dict[str, Any]) -> Dict[str, Any]:
        self.items.append(item)
        return item

    def is_standing(self, tree: str) -> bool:
        return any(_inside(p, tree) for p in self.standing)


def _wt_item(w: Dict[str, Any], source: str) -> Dict[str, Any]:
    return {"kind": "worktree", "path": w["path"], "branch": w.get("branch"), "head": w.get("head"),
            "source": source, "locked": bool(w.get("locked")), "action": "left", "reason": None, "files": [],
            "detail": None, "links": []}


def _left(item: Dict[str, Any], reason: str, files: Optional[List[str]] = None, detail: Optional[str] = None,
          action: str = "left") -> Dict[str, Any]:
    item.update(action=action, reason=reason, files=files or [], detail=detail)
    return item


def _status_files(path: str) -> Tuple[Optional[List[str]], str]:
    """Changed and untracked paths of a worktree, or ``(None, error)``."""
    code, out, err = _git("-C", path, "status", "--porcelain", "-z", "--untracked-files=all")
    if code != 0:
        return None, err.strip()
    files: List[str] = []
    parts = out.split("\0")
    i = 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if len(entry) < 4:
            continue
        files.append(entry[3:])
        if entry[0] in "RC" or entry[1] in "RC":
            i += 1  # the original name of a rename or copy
    return sorted(files), ""


def _ignored_dirs(path: str) -> Optional[List[str]]:
    """Ignored top-level entries, or None when git cannot list them (never an empty list on failure)."""
    code, out, _err = _git("-C", path, "ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--directory")
    return [n for n in out.split("\0") if n] if code == 0 else None


def _tracked(path: str) -> Optional[set]:
    """Tracked paths, or None when git cannot list them (never an empty set on failure)."""
    code, out, _err = _git("-C", path, "ls-files", "-z")
    return {n for n in out.split("\0") if n} if code == 0 else None


def _probe(path: str) -> Optional[OSError]:
    """INV-6 (Windows): rename the folder to a sibling name and straight back. ``None`` when nobody holds it."""
    sibling = path.rstrip("/\\") + ".probe"
    count = 1
    while os.path.lexists(sibling):
        count += 1
        sibling = "%s.probe%d" % (path.rstrip("/\\"), count)
    try:
        os.rename(path, sibling)
    except OSError as exc:
        return exc
    try:
        os.rename(sibling, path)
    except OSError as exc:
        raise Halt(path, sibling, exc)
    return None


def clean_worktree(run: Run, item: Dict[str, Any]) -> None:
    """INV-3, INV-4, INV-6 for one owned worktree: every check first, links last, then the removal."""
    path = item["path"]
    if item["locked"]:
        _left(item, "locked")
        return
    if not os.path.isdir(path):
        _left(item, "remove-failed", detail="the folder is missing; git still lists it")
        return
    changed, err = _status_files(path)
    if changed is None:
        _left(item, "unverifiable", detail=err)
        return
    if changed:
        _left(item, "uncommitted-changes", files=changed)
        return
    head = item["head"]
    if not head:  # read the tree's own HEAD; never fall back to the main checkout's
        code, out, _err = _git("-C", path, "rev-parse", "HEAD")
        head = out.strip() if code == 0 and out.strip() else None
    if not head:
        _left(item, "unverifiable", detail="the HEAD of this tree cannot be read")
        return
    item["head"] = head
    code, _out, _err = _git("merge-base", "--is-ancestor", head, run.ref)
    if code != 0:
        if code != 1:
            _left(item, "unverifiable", detail="merge-base answered %d" % code)
            return
        _c, diff, _e = _git("diff", "--name-only", "%s...%s" % (run.ref, head))
        _left(item, "unpushed-commits", files=[n for n in diff.splitlines() if n.strip()])
        return
    ignored = _ignored_dirs(path)
    tracked = _tracked(path)
    if ignored is None or tracked is None:
        _left(item, "unverifiable", detail="git could not list the ignored or tracked files of this tree")
        return
    nested = find_nested(path, ignored)
    if nested:
        _left(item, "nested-worktree", files=sorted(nested))
        return
    if run.is_standing(path):
        _left(item, "standing-tree", action="deferred")
        run.finish_needed = True
        return
    if run.dry_run:
        links = [{"path": l.replace("\\", "/"), "target": _real_target(l).replace("\\", "/"), "removed": False}
                 for l in find_links(path, tracked)]
        item.update(action="removed", links=links, detail="dry run: would be removed")
        run.removed_paths.append(path)
        return
    found_links = find_links(path, tracked)
    # One halt rule (INV-9): a link that sits outside every ignored folder (a node_modules link in the tree's own
    # folders) and lost its target. Dangling links inside an ignored folder such as .venv are ordinary: no halt.
    def is_inside_ignored(link: str) -> bool:
        parent = os.path.relpath(os.path.dirname(link), path).replace("\\", "/")
        if parent == ".":
            return False
        code, _o, _e = _git("-C", path, "check-ignore", "-q", "--", parent)
        return code == 0  # an error or "not ignored" keeps the halt: the safe direction

    vanished = [(l, _real_target(l)) for l in found_links if _real_target(l) and not os.path.exists(_real_target(l))
                and not is_inside_ignored(l)]
    if vanished:
        run.halted = True  # like a failed rename-back: nothing else is removed after it
        _left(item, "remove-failed", detail="a link lost its target folder, nothing was removed: " + "; ".join(
            "%s -> %s" % (l.replace("\\", "/"), t.replace("\\", "/")) for l, t in vanished))
        return
    if IS_WINDOWS:
        try:
            failure = _probe(path)
        except Halt as halt:
            run.halted = True
            run.repair.append(halt.path)
            item["repair"] = halt.path
            _left(item, "remove-failed", detail="the folder could not be renamed back and now sits at '%s'; "
                  "rename it to '%s', then run: git worktree repair '%s'" % (halt.sibling, halt.path, halt.path))
            return
        if failure is not None:
            _left(item, "in-use", action="deferred", detail=_clean(failure))
            run.finish_needed = True
            return
    links: List[Dict[str, Any]] = []
    for link in found_links:
        try:
            links.append(remove_link(link))
        except OSError as exc:
            links.append({"path": link.replace("\\", "/"), "target": _real_target(link).replace("\\", "/"),
                          "removed": False, "target_survived": None})
            item["links"] = links
            _left(item, "link-not-removed", detail="%s: %s" % (link.replace("\\", "/"), _clean(exc)))
            return
    item["links"] = links
    code, _out, err = _git("worktree", "remove", path)
    if code != 0 or os.path.exists(path):
        recreate = "; ".join("%s -> %s" % (l["path"], l["target"]) for l in links)
        detail = (err.strip() or "the folder is still present after git worktree remove")
        if recreate:
            detail += "; removed links: " + recreate
        _left(item, "remove-failed", detail=detail)
        return
    item.update(action="removed", reason=None)
    run.removed_paths.append(path)


def plan_worktrees(run: Run, owned: Dict[str, str], brief: Dict[str, str]) -> List[Dict[str, Any]]:
    """Owned Worktrees as items, decided by checked-out branch or exact brief path, never by folder name alone."""
    entries = flat_worktree.worktree_entries(run.main_root)
    brief_wt = _value(brief, "worktree")
    brief_path = _norm(brief_wt if os.path.isabs(brief_wt) else os.path.join(run.main_root, brief_wt)) if brief_wt else None
    others = other_slugs(run.ref, run.slug)
    planned: List[Dict[str, Any]] = []
    for entry in entries[1:]:
        path = entry["path"]
        if _norm(path) == _norm(run.main_root) or land_contract.is_landing_worktree(path, run.main_root):
            continue
        branch = entry.get("branch")
        item = None
        if branch in owned:
            item = _wt_item(entry, "owned-branch")
        elif brief_path and _norm(path) == brief_path:
            item = _wt_item(entry, "brief-worktree")
            if branch is not None:
                item["pre"] = "holds-foreign-branch"
        elif branch is None and _advance_name_matches(path, run.slug):
            item = _wt_item(entry, "advance-name")
            if others is None:
                item["pre"] = "unverifiable"  # the other contracts cannot be read: no advance name is provably ours
            elif _advance_name_matches(path, run.slug) == "cut" or any(_advance_name_matches(path, s) for s in others):
                item["pre"] = "ambiguous-name"
        if item is None:
            continue
        if branch is not None and (branch in PROTECTED or branch == run.default):
            item["pre"] = "protected-name"
        if not flat_worktree.is_flat(run.main_root, path):
            item["pre"] = "outside-worktrees-folder"
        planned.append(item)
    return sorted(planned, key=lambda i: i["path"])


def _advance_name_matches(path: str, slug: str) -> str:
    """``"exact"`` when the folder is this slug's whole advance worktree name (``-2`` to ``-9`` allowed), ``"cut"``
    when it is that name cut at the 60-character limit (a longer or a shorter slug may own it too), else ``""``."""
    name = os.path.basename(os.path.normpath(path))
    date = name[:8]
    if not re.fullmatch(r"\d{8}", date):
        return ""
    for n in range(1, flat_worktree.MAX_SUFFIX + 1):
        if name == flat_worktree.flat_name("advance", slug, date, n):
            whole = "%s-advance-%s" % (date, slug) + ("-%d" % n if n > 1 else "")
            return "exact" if name == whole else "cut"
    return ""


def orphan_folders(run: Run, brief: Dict[str, str], listed: List[str]) -> None:
    """A folder where an owned worktree used to be, which git no longer lists (a failed removal can leave one)."""
    folder = flat_worktree.worktrees_dir(run.main_root)
    try:
        names = sorted(os.listdir(folder)) if os.path.isdir(folder) else []
    except OSError:
        return  # a report that cannot be made must not crash a run that already changed things
    brief_wt = _value(brief, "worktree")
    brief_path = _norm(brief_wt if os.path.isabs(brief_wt) else os.path.join(run.main_root, brief_wt)) if brief_wt else None
    known = {_norm(p) for p in listed} | {_norm(i["path"]) for i in run.items if i.get("kind") == "worktree"}
    for name in names:
        path = os.path.join(folder, name)
        try:
            if _norm(path) in known or not os.path.isdir(path) or _is_link(path):
                continue
            if not ((brief_path and _norm(path) == brief_path) or _advance_name_matches(path, run.slug) == "exact"):
                continue
            try:
                count = "%d entries" % len(os.listdir(path))
            except OSError:
                count = "entries unreadable"
        except OSError:
            continue
        item = {"kind": "worktree", "path": path.replace("\\", "/"), "branch": None, "head": None,
                "source": "orphan-folder", "locked": False, "links": []}
        run.add(_left(item, "remove-failed", detail="git no longer lists this folder and never checked it (%s): it may "
                                                     "hold the only copy of someone's work, so inspect it before "
                                                     "deleting anything" % count))


def clean_branches(run: Run, owned: Dict[str, str]) -> Dict[str, bool]:
    """Local branches, after the worktrees (INV-3, INV-9). Returns which owned branches existed locally."""
    code, out, _err = _git("for-each-ref", "--format=%(refname) %(objectname)", "refs/heads")
    tips: Dict[str, str] = {}
    for line in out.splitlines():
        name, _, sha = line.partition(" ")
        if name.startswith("refs/heads/"):
            tips[name[len("refs/heads/"):]] = sha.strip()
    existed = {b: b in tips for b in owned}
    held: Dict[str, str] = {}
    gone = {_norm(p) for p in run.removed_paths}
    for entry in flat_worktree.worktree_entries(run.main_root):
        if entry.get("branch") and _norm(entry["path"]) not in gone:
            held[entry["branch"]] = entry["path"]
    for branch, source in owned.items():
        if branch not in tips:
            continue
        item = {"kind": "local-branch", "name": branch, "source": source, "action": "left", "reason": None,
                "files": [], "detail": None}
        run.add(item)
        if branch in PROTECTED or branch == run.default:
            _left(item, "protected-name")
        elif branch in held:
            _left(item, "checked-out", detail="held by %s" % held[branch].replace("\\", "/"))
        else:
            code, _o, _e = _git("merge-base", "--is-ancestor", tips[branch], run.ref)
            if code != 0:
                _left(item, "not-in-default", detail="%s is not in %s" % (tips[branch][:10], run.ref))
            elif run.dry_run:
                item.update(action="removed", detail="dry run: would be deleted")
            else:
                code, _o, err = _git("branch", "-D", branch)
                if code != 0:
                    _left(item, "delete-failed", detail=err.strip())
                else:
                    item["action"] = "removed"
    return existed


def clean_remote(run: Run, owned: Dict[str, str], existed: Dict[str, bool]) -> None:
    """Remote branches, last (INV-7). Without ``remove-remote`` nothing is changed."""
    for branch, source in owned.items():
        item = {"kind": "remote-branch", "name": "origin/%s" % branch, "source": source, "action": "left",
                "reason": None, "files": [], "detail": None}
        code, out, err = _git("ls-remote", "--heads", "origin", "refs/heads/%s" % branch)
        if code != 0:
            run.add(_left(item, "unverifiable", detail=err.strip()))
            continue
        tip = ""
        for line in out.splitlines():
            sha, _, name = line.partition("\t")
            if name.strip() == "refs/heads/%s" % branch:
                tip = sha.strip()
        if not tip:
            if run.remove_remote and existed.get(branch):
                run.add(dict(item, action="already-gone"))
            continue
        run.add(item)
        if branch in PROTECTED or branch == run.default:
            _left(item, "protected-name")
        elif not run.remove_remote:
            _left(item, "remote-kept")
        else:
            code, _o, _e = _git("merge-base", "--is-ancestor", tip, run.ref)
            if code != 0:
                _left(item, "not-in-default", detail="%s is not in %s" % (tip[:10], run.ref))
                continue
            code, out, err = _gh("pr", "list", "--head", branch, "--state", "open", "--json", "number,url")
            try:
                open_prs = json.loads(out) if code == 0 else None
            except ValueError:
                open_prs = None
            if not isinstance(open_prs, list):
                _left(item, "unverifiable", detail="gh could not list the open pull requests")
            elif open_prs:
                _left(item, "open-pull-request", detail=str(open_prs[0].get("url") or ""))
            elif run.dry_run:
                item.update(action="removed", detail="dry run: would be deleted")
            else:
                lease = "--force-with-lease=refs/heads/%s:%s" % (branch, tip)  # fails if the branch moved since the check
                code, _o, err = _git("push", lease, "origin", "--delete", branch)
                if code != 0:
                    _left(item, "delete-failed", detail=err.strip())
                else:
                    item["action"] = "removed"


# ---------------------------------------------------------------------------
# The report (INV-8)
# ---------------------------------------------------------------------------
def _name(item: Dict[str, Any]) -> str:
    if item["kind"] == "worktree":
        return _clean(item["path"].replace("\\", "/").rstrip("/").rsplit("/", 1)[-1])
    return _clean(item["name"])


def _listing(entries: List[str], cap: int, sep: str) -> str:
    shown = entries[:cap]
    parts = list(shown)
    if len(entries) > len(shown):
        parts.append("+%d more" % (len(entries) - len(shown)))
    return sep.join(parts)


def _left_entry(item: Dict[str, Any], file_cap: int) -> str:
    text = "%s: %s" % (_name(item), item["reason"])
    files = [_clean(f.replace("\\", "/")) for f in item.get("files") or []]
    if files:
        text += " [%s]" % _listing(files, file_cap, ", ")
    return text


def build_line(slug: str, items: List[Dict[str, Any]], finish: Optional[str]) -> str:
    removed = [i for i in items if i["action"] == "removed"]
    left = [i for i in items if i["action"] in ("left", "deferred")]
    repairs = [i["repair"] for i in items if i.get("repair")]
    tail = "".join("; repair: git worktree repair %s" % _quote(_clean(p)) for p in repairs)
    if finish:
        tail += "; finish: " + finish  # never cut: a cut command is useless
    line = ""
    for cap, file_cap in ((8, 3), (6, 3), (4, 2), (3, 2), (2, 1), (1, 1), (0, 0), (-1, 0)):
        if cap >= 0:
            line = "CLEANUP %s: removed %d (%s); left %d (%s)" % (
                _clean(slug), len(removed), _listing([_name(i) for i in removed], cap, ", "), len(left),
                _listing([_left_entry(i, file_cap) for i in left], cap, "; "))
        else:  # last resort: the parenthesised lists go, the counts and the tail stay
            line = "CLEANUP %s: removed %d; left %d" % (_clean(slug), len(removed), len(left))
        line += tail
        if len(line) <= LINE_LIMIT:
            return line
    return line if tail else line[:LINE_LIMIT]


def not_delivered_line(slug: str, reading: Dict[str, Any]) -> str:
    first = _clean((reading.get("reasons") or ["no reason given"])[0])
    if reading["verdict"] == "unverifiable":
        return "CLEANUP %s: unverifiable (%s); nothing removed" % (_clean(slug), first)
    return "CLEANUP %s: not delivered yet (%s); nothing removed; %s" % (_clean(slug), first, RERUN_HINT)


def finish_command(slug: str, main_root: str, remove_remote: bool) -> str:
    script = os.path.abspath(__file__)
    cmd = "py -3 %s --contract %s --from %s" % (_quote(script), _quote(slug), _quote(main_root))
    return cmd + " --remove-remote" if remove_remote else cmd


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def cleanup(slug: str, start: str, start_cwd: str, remove_remote: bool, dry_run: bool) -> Tuple[Dict[str, Any], int]:
    info = flat_worktree.describe(start if os.path.isdir(start) else start_cwd)
    main_root = info.get("main_root")
    base: Dict[str, Any] = {"contract": slug, "main_root": main_root, "remove_remote": remove_remote,
                            "dry_run": dry_run, "items": []}
    if not main_root:
        reading = {"verdict": "unverifiable", "reasons": ["the main checkout cannot be found from %s" % start]}
        base.update(outcome="unverifiable", delivery=reading, line=not_delivered_line(slug, reading))
        return base, EXIT_UNVERIFIABLE
    os.chdir(main_root)  # the main checkout is never an owned tree; nothing below runs from a tree it removes
    reading = read_delivery(slug)
    base["delivery"] = reading
    if reading["verdict"] != "delivered":
        base.update(outcome=reading["verdict"], line=not_delivered_line(slug, reading))
        return base, EXIT_UNVERIFIABLE if reading["verdict"] == "unverifiable" else EXIT_NOT_DELIVERED

    default = reading["default_branch"]
    ref = "origin/%s" % default
    text = pr_merged.file_at_commit(ref, "%s/%s.md" % (pr_merged.CONCEPTS_DIR.as_posix(), slug)) or ""
    records = pr_merged.load_records_at(ref, slug)
    delivery = pr_merged.load_delivery_at(ref, slug)
    brief = find_brief(slug, text, ref, start, default, records, delivery)
    owned = owned_branches(slug, reading["sub_tasks"], brief)
    standing = [start_cwd, start]
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        standing.append(os.environ["CLAUDE_PROJECT_DIR"])
    run = Run(slug, main_root, ref, default, remove_remote, dry_run, standing)

    for item in plan_worktrees(run, owned, brief):
        if run.halted:
            break
        run.add(item)
        pre = item.pop("pre", None)
        if pre:
            _left(item, pre)
        else:
            clean_worktree(run, item)
    if not run.halted:
        try:
            orphan_folders(run, brief, [e["path"] for e in flat_worktree.worktree_entries(main_root)])
        except OSError:
            pass  # the orphan report is best effort; the branch steps and the line must still follow
        existed = clean_branches(run, owned)
        clean_remote(run, owned, existed)

    items = run.items
    finish = finish_command(slug, main_root, remove_remote) if run.finish_needed else None
    actionable = [i for i in items if i["action"] != "already-gone" and i.get("reason") != "remote-kept"]
    problems = [i for i in actionable if i["action"] in ("left", "deferred")]
    if run.halted or problems:
        outcome, code = "partial", EXIT_PARTIAL
    elif actionable:
        outcome, code = "cleaned", EXIT_OK
    else:
        outcome, code = "nothing-owned", EXIT_OK
    base.update(outcome=outcome, items=items, line=build_line(slug, items, finish))
    if finish:
        base["finish_command"] = finish
    if run.repair:
        base["repair"] = ["git worktree repair %s" % _quote(p) for p in run.repair]
    return base, code


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Remove the worktrees and merged branches of a delivered work item.")
    ap.add_argument("--contract", help="the contract slug")
    ap.add_argument("--from", dest="start", help="the folder the session stands in")
    ap.add_argument("--remove-remote", action="store_true", help="also delete the remote branches (off by default)")
    ap.add_argument("--dry-run", action="store_true", help="report what would be done and change nothing")
    ap.add_argument("--json", action="store_true", help="print the whole Cleanup Report as JSON")
    ap.add_argument("--print-main-root", action="store_true", help="print the main checkout root and exit")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if args.print_main_root:
        root = flat_worktree.describe().get("main_root")
        if not root:
            sys.stderr.write("not inside a git repository\n")
            return 1
        print(root)
        return EXIT_OK
    if not args.contract or not args.start:
        ap.error("--contract and --from are required")
    slug = re.sub(r"\.md$", "", os.path.basename(args.contract.replace("\\", "/")))
    start_cwd = os.path.realpath(os.getcwd())
    report, code = cleanup(slug, os.path.realpath(args.start), start_cwd, args.remove_remote, args.dry_run)
    print(json.dumps(report) if args.json else report["line"])
    return code


if __name__ == "__main__":
    sys.exit(main())
