#!/usr/bin/env python3
"""
test_cleanup_delivered.py -- RED suite for Delivery cleanup, ``.claude/scripts/cleanup_delivered.py``.

Contract: .claude/concepts/2026-10-15-auto-cleanup-delivered-worktrees.md (issue #50), Data Shapes INV-1 to
INV-9 and the TASK block of sub-task 1 (required cases [1] to [9] and the "Also:" list). The trials T1 to T4
of the same contract live in test_cleanup_delivered_trials.py; the new readers and the ``locked`` key are
tested in test_pr_merged.py and test_flat_worktree.py.

Run:
    py -3 .claude/scripts/tests/test_cleanup_delivered.py
    (or: cd .claude/scripts/tests && py -3 -m unittest test_cleanup_delivered)

RED TODAY: ``cleanup_delivered.py`` does not exist. Every test goes through ``cleanup()`` or
``load_module()``, which fail with "cleanup_delivered.py does not exist yet", so each RED test reads as an
assertion about the missing script and never as a collection or import error. Controls (the source scanner's
positive controls, the fixture sanity tests) pass today by design.

THE INTERFACE THIS SUITE PINS (everything below is named by the contract; nothing is invented):

    cleanup_delivered.py --contract <slug> --from <starting dir> [--remove-remote] [--dry-run] [--json]
    cleanup_delivered.py --print-main-root
    exit codes: 0 cleaned or nothing-owned, 3 partial, 5 not-delivered, 10 unverifiable, 2 usage.
    --json prints one Cleanup Report object: outcome, delivery{verdict, reasons}, items[{kind, action,
    reason, files, detail, links}], line, finish_command (only when something is deferred), dry_run,
    remove_remote. Without --json the single ``line`` is printed.
    The process is started in the MAIN root (as the skills do: ``cd <main root> && py -3 $CLN ...``), except
    where a test names another folder on purpose.

THE WORLD EVERY TEST BUILDS (real temporary git repositories, a local bare origin, a fake ``gh`` and a
wrapper ``git`` that are real executables on PATH, see test_flat_worktree.py):

    origin/master  ->  the contract (``Status: approved``, ``**Work Item Brief:**`` header), a brief whose
                       ``contract:`` is ``none`` (like this very work item's), a sibling contract.
    main checkout  ->  sits on the non-owned branch ``main-side``.
    owned          ->  feature worktree + branch, sub-task worktree + branch ``task/<slug>/t1-cleanup``,
                       detached advance worktree ``<date>-advance-<slug>``, records branch
                       ``docs/<slug>-records``.
    stage 1        ->  the feature is merged into origin/master; the records pull request is OPEN (fake gh).
    stage 2        ->  ``merge_records``: the records commit (contract ``implemented`` plus the completion
                       record) reaches origin/master from a second clone, so the main checkout's own
                       ``origin/master`` is stale until the script fetches.
"""
from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tokenize
import unittest
from itertools import takewhile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_flat_worktree import (  # noqa: E402
    REAL_GIT, REPO_ROOT, SCRIPTS_DIR, Tools, add_worktree, clean_env, clone_of, commit, git, make_world, real,
    rmtree_force, run as run_cmd, run_py, snapshot, worktree_paths, write_exe,
)
from test_cleanup_delivered_trials import IS_WINDOWS, find_git_bash, is_link_entry, make_directory_link  # noqa: E402

CLEANUP = SCRIPTS_DIR / "cleanup_delivered.py"
MISSING = ("cleanup_delivered.py does not exist yet: the Delivery cleanup script (INV-1..INV-9) is the "
           "implementer's job in the GREEN step; this test is RED until it is added next to flat_worktree.py")

SLUG = "2026-10-15-demo-feature"
OTHER_SLUG = "2026-10-15-demo-other"
CONTRACT_REL = f".claude/concepts/{SLUG}.md"
BRIEF_REL = ".claude/work-items/2026-10-15-50.md"
RESULTS_REL = f".claude/orchestrator/results/{SLUG}"
FEATURE = "feature/50-demo"
TASK_BRANCH = f"task/{SLUG}/t1-cleanup"
RECORDS_BRANCH = f"docs/{SLUG}-records"
WT_DIR = ".claude/worktrees"
FW_NAME = "20261015-feature-50-demo"
TW_NAME = "20261015-task-t1-cleanup"
AW_NAME = f"20261015-advance-{SLUG}"
RECORDS_URL = "https://github.com/acme/app/pull/60"
OWNED_BRANCHES = (FEATURE, TASK_BRANCH, RECORDS_BRANCH)

REASONS = {"uncommitted-changes", "unpushed-commits", "nested-worktree", "not-in-default", "checked-out", "locked",
           "holds-foreign-branch", "ambiguous-name", "standing-tree", "in-use", "link-not-removed", "remove-failed",
           "delete-failed", "open-pull-request", "protected-name", "remote-kept", "unverifiable",
           "outside-worktrees-folder"}
ACTIONS = {"removed", "left", "deferred", "already-gone"}
GITIGNORE = "__pycache__/\n.venv/\n*.log\n.claude/worktrees/\nnode_modules\n"


# ---------------------------------------------------------------------------
# The wrapper ``git``: logs every call, can be told to fail one, and shows what a worktree held at the
# moment it was removed.
# ---------------------------------------------------------------------------
FAKE_GIT_CODE = r'''
import json, os, shutil, stat, subprocess, sys
HERE = os.path.dirname(os.path.abspath(sys.argv[0]))
cfg = json.load(open(os.path.join(HERE, "git_wrapper.json"), encoding="utf-8"))
args = sys.argv[1:]


def is_link(p):
    try:
        st = os.lstat(p)
    except OSError:
        return False
    if os.name == "nt":
        return bool(getattr(st, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    return stat.S_ISLNK(st.st_mode)


def find_links(top):
    """Every link entry anywhere under top (a link is reported, never entered)."""
    found, stack = [], [top]
    while stack:
        here = stack.pop()
        try:
            names = os.listdir(here)
        except OSError:
            continue
        for n in names:
            full = os.path.join(here, n)
            if is_link(full):
                found.append(os.path.relpath(full, top).replace("\\", "/"))
            elif os.path.isdir(full) and n != ".git":
                stack.append(full)
    return sorted(found)


def host_shaped_failure(target):
    """What trial T1 recorded on Windows: every file deleted, the worktree deregistered, an empty folder left."""
    admin = None
    try:
        text = open(os.path.join(target, ".git"), encoding="utf-8").read().strip()
        if text.startswith("gitdir:"):
            admin = text[len("gitdir:"):].strip()
    except OSError:
        pass
    for n in os.listdir(target):
        full = os.path.join(target, n)
        if is_link(full):
            (os.rmdir if os.name == "nt" and os.path.isdir(full) else os.unlink)(full)
        elif os.path.isdir(full):
            shutil.rmtree(full, ignore_errors=True)
        else:
            os.remove(full)
    if admin and os.path.isdir(admin):
        shutil.rmtree(admin, ignore_errors=True)
    sys.stderr.write("error: failed to delete '%s': Permission denied\n" % target.replace("\\", "/"))
    sys.exit(255)

entry = {"args": args, "cwd": os.getcwd()}
i = 0
while i < len(args) and args[i] in ("-C", "-c"):
    i += 2
sub = args[i:]
if sub[:2] == ["worktree", "remove"] and len(sub) > 2:
    try:
        entry["children"] = sorted(os.listdir(sub[-1]))
        entry["links"] = find_links(sub[-1])
    except OSError:
        entry["children"] = None
with open(os.path.join(HERE, "git_calls.jsonl"), "a", encoding="utf-8") as fh:
    fh.write(json.dumps(entry) + "\n")
for rule in cfg.get("fail", []):
    excluded = any(any(tok in a for a in args) for tok in rule.get("unless", []))
    if all(any(tok in a for a in args) for tok in rule["tokens"]) and not excluded:
        if rule.get("mode") == "strip-head":  # `git worktree list --porcelain` without HEAD lines: the head read "fails"
            done = subprocess.run([cfg["real_git"]] + args, capture_output=True, text=True, encoding="utf-8", errors="replace")
            sys.stdout.write("".join(l for l in done.stdout.splitlines(True) if not l.startswith("HEAD ")))
            sys.stderr.write(done.stderr)
            sys.exit(done.returncode)
        if rule.get("mode") == "t1":
            host_shaped_failure(sub[-1])
        sys.stderr.write("fatal: wrapper git failing on purpose (%s)\n" % rule["tokens"])
        sys.exit(rule.get("code", 1))
sys.exit(subprocess.call([cfg["real_git"]] + args))
'''


def install_git_wrapper(tools: Tools) -> None:
    write_exe(tools.bin, "git", FAKE_GIT_CODE)
    (tools.bin / "git_wrapper.json").write_text(json.dumps({"real_git": REAL_GIT, "fail": []}), encoding="utf-8")


def set_git_fail(tools: Tools, *token_lists: list, mode: str | None = None, unless: list | None = None) -> None:
    """Make every git call that carries all these tokens fail. ``mode="t1"`` fails the way trial T1 recorded;
    ``mode="strip-head"`` answers without the HEAD lines; ``unless`` tokens exclude a call from the rule."""
    rules = [dict({"tokens": t}, **({"mode": mode} if mode else {}), **({"unless": unless} if unless else {}))
             for t in token_lists]
    (tools.bin / "git_wrapper.json").write_text(json.dumps({"real_git": REAL_GIT, "fail": rules}), encoding="utf-8")


def git_calls(tools: Tools) -> list:
    return tools.git_calls()


def sub_command(args: list) -> list:
    i = 0
    while i < len(args) and args[i] in ("-C", "-c"):
        i += 2
    while i < len(args) and args[i].startswith("-"):
        i += 1
    return args[i:]


def is_mutating(args: list) -> bool:
    sub = sub_command(args)
    if not sub:
        return False
    head = sub[0]
    if head in ("push", "switch", "checkout", "reset", "clean", "update-ref", "prune", "gc", "commit", "merge",
                "rebase", "stash", "restore", "tag"):
        return True
    if head == "worktree" and len(sub) > 1 and sub[1] in ("remove", "prune", "add", "move", "lock", "unlock", "repair"):
        return True
    if head == "branch" and any(a in ("-d", "-D", "-m", "-M", "--delete", "-f", "--force", "-c", "-C", "--move",
                                      "--copy") for a in sub[1:]):
        return True
    return False


LEASE_FORM = re.compile(r"--force-with-lease=refs/heads/.+:[0-9a-f]{40}")


def forbidden_git_use(args: list) -> str | None:
    """Why this git argument vector breaks INV-5, or None. The one allowed force form is the remote delete's
    lease: ``push --force-with-lease=refs/heads/<b>:<sha> origin --delete <b>``."""
    sub = sub_command(args)
    if not sub:
        return None
    if sub[0] in ("switch", "checkout", "rm", "clean", "reset"):
        return f"`git {sub[0]}` is never run"
    if "prune" in sub:
        return "no prune, ever"
    for arg in sub:
        if arg in ("--force", "-f", "-ff") or arg.startswith("--force"):
            if LEASE_FORM.fullmatch(arg) and sub[0] == "push" and "--delete" in sub:
                continue
            return f"{arg} is not allowed (only the lease form of the remote delete)"
    return None


def forbidden_gh_use(call: dict) -> str | None:
    args = call.get("args", [])
    if call.get("unexpected"):
        return "the fake gh did not expect this command"
    if args[:2] not in (["pr", "list"], ["pr", "view"]):
        return "gh may only read (pr list, pr view)"
    if any(a in ("-X", "--method", "--delete") for a in args):
        return "a writing flag"
    return None


def mutating_calls(tools: Tools) -> list:
    return [c["args"] for c in git_calls(tools) if is_mutating(c["args"])]


# ---------------------------------------------------------------------------
# Texts of the world
# ---------------------------------------------------------------------------
def task_name(i: int) -> str:
    return "Cleanup" if i == 1 else f"Part{i}"


def task_id(i: int) -> str:
    return f"t{i}-{task_name(i).lower()}"


def contract_text(status: str, *, header: bool = True, n_tasks: int = 1) -> str:
    lines = ["# Contract: demo feature", "", f"**Status:** {status}"]
    if header:
        lines.append(f"**Work Item Brief:** {BRIEF_REL}")
    lines += ["", "## Implementation Handoff", ""]
    for i in range(1, n_tasks + 1):
        lines += [f"### {i}. {task_name(i)} (`python-ai-developer`)", "", "**Depends on:** none", "",
                  "**Files to touch:**", f"- `src/part{i}.txt`", ""]
    return "\n".join(lines) + "\n"


def brief_text(branch: str, *, status: str = "implementing", contract: str = "none") -> str:
    return "\n".join([
        "---", "id: 50", "title: Demo feature", "type: FEATURE", "source: github", "repo: acme/app",
        "url: https://github.com/acme/app/issues/50", "labels: []", "milestone: none", "project: demo",
        f"branch: {branch}", f"worktree: {WT_DIR}/{FW_NAME}", "north_stars: none", f"contract: {contract}", "pr: none",
        "issue_link: unknown", f"status: {status}", "created: 2026-10-15", "---", "", "# Demo feature", ""])


def record_text(i: int) -> str:
    return ("status: completed\ncommit: abcdef0\ntests_passed: unknown\ntests_verified_by: none\n"
            f"completed_by: pr-merged\npull_request: https://github.com/acme/app/pull/{40 + i}\n"
            "merged_at: '2026-10-14T00:00:00Z'\nverified: github\nbase_ref: master\nbase_is_default: true\n")


# ---------------------------------------------------------------------------
# The world
# ---------------------------------------------------------------------------
def build_world(root: Path, *, n_tasks: int = 1, header: bool = True, brief_branch: str = FEATURE,
                fw_branch: str = FEATURE, with_advance: bool = True, other_contract: bool = True,
                brief_in_base: bool = True, brief_contract: str = "none") -> SimpleNamespace:
    files = {".gitignore": GITIGNORE, CONTRACT_REL: contract_text("approved", header=header, n_tasks=n_tasks)}
    if brief_in_base:  # False: the brief reaches origin/master only with the records commit, so no tree has it on disk
        files[BRIEF_REL] = brief_text(brief_branch, contract=brief_contract)
    if other_contract:  # a sibling contract that IS on origin/master; without it the sibling is only in flight
        files[f".claude/concepts/{OTHER_SLUG}.md"] = "# Contract: other\n\n**Status:** approved\n"
    world = make_world(root, files=files)
    main = world.main
    git(main, "switch", "-q", "-c", "main-side")
    if brief_branch == "main":
        git(main, "branch", "main", "master")

    fw = main / WT_DIR / FW_NAME
    tw = main / WT_DIR / TW_NAME
    aw = main / WT_DIR / AW_NAME
    add_worktree(main, fw, "-b", fw_branch, "master")
    commit(fw, {"src/feature.txt": "feature\n"}, "feature work")
    add_worktree(main, tw, "-b", TASK_BRANCH, fw_branch)
    commit(tw, {"src/task.txt": "task\n"}, "task work")
    git(fw, "merge", "--no-ff", "-q", "-m", "merge task", TASK_BRANCH)
    git(main, "push", "-q", "origin", fw_branch, TASK_BRANCH)
    if with_advance:
        add_worktree(main, aw, "--detach", "master")

    ghub = clone_of(world, "github_side")  # the GitHub side: merges happen here, never in the main checkout
    git(ghub, "merge", "--ff-only", "-q", f"origin/{fw_branch}")
    git(ghub, "push", "-q", "origin", "master")
    git(ghub, "switch", "-q", "-c", RECORDS_BRANCH)
    records = {CONTRACT_REL: contract_text("implemented", header=header, n_tasks=n_tasks),
               BRIEF_REL: brief_text(brief_branch, status="done", contract=brief_contract)}
    for i in range(1, n_tasks + 1):
        records[f"{RESULTS_REL}/{task_id(i)}.yaml"] = record_text(i)
    commit(ghub, records, "records and flip")
    git(ghub, "push", "-q", "origin", RECORDS_BRANCH)
    git(ghub, "switch", "-q", "master")
    git(main, "fetch", "-q", "origin", f"{RECORDS_BRANCH}:{RECORDS_BRANCH}")

    tools = Tools(root)
    tools.install_gh({"open_prs": [{"headRefName": RECORDS_BRANCH, "url": RECORDS_URL, "baseRefName": "master"}]})
    install_git_wrapper(tools)
    install_fake_claude(tools)  # a fake `claude` on PATH in every world: a test never reaches a real one
    return SimpleNamespace(root=Path(root), world=world, main=main, origin=world.origin, ghub=ghub, tools=tools,
                           fw=fw, tw=tw, aw=aw, n_tasks=n_tasks, fw_branch=fw_branch)


def remote_delete(w, *names: str) -> None:
    for name in names:
        git(w.ghub, "push", "-q", "origin", "--delete", name)


def merge_records(w, *, delete_remote: bool = True) -> None:
    """GitHub merges the records pull request; by default GitHub also deletes the three remote branches."""
    git(w.ghub, "merge", "--ff-only", "-q", RECORDS_BRANCH)
    git(w.ghub, "push", "-q", "origin", "master")
    w.tools.set_gh(open_prs=[])
    if delete_remote:
        remote_delete(w, w.fw_branch, TASK_BRANCH, RECORDS_BRANCH)


def remote_heads(w) -> list:
    out = git(w.main, "ls-remote", "--heads", "origin")
    return sorted(line.split("refs/heads/", 1)[1] for line in out.splitlines() if "refs/heads/" in line)


def local_branches(w) -> dict:
    out = git(w.main, "for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads")
    return dict(line.split(" ", 1) for line in out.splitlines() if line.strip())


def tree_listing(top: Path) -> list:
    found = []
    for dirpath, dirnames, filenames in os.walk(str(top)):
        for name in dirnames + filenames:
            found.append(os.path.relpath(os.path.join(dirpath, name), str(top)).replace("\\", "/"))
    return sorted(found)


def state(w) -> dict:
    """Everything a cleanup could change, as plain data (the main checkout is checked by ``snapshot``)."""
    worktrees_root = w.main / WT_DIR
    return {"worktrees": sorted(worktree_paths(w.main)), "branches": local_branches(w), "remote": remote_heads(w),
            "folders": {p.name: tree_listing(p) for p in sorted(worktrees_root.iterdir()) if p.is_dir()}
            if worktrees_root.is_dir() else {}}


SIBLING_BRANCH = "feature/60-sibling"
SIBLING_WT = "20261015-feature-60-sibling"


def add_sibling_item(w, contract_field: str) -> Path:
    """Another work item (#60) whose brief is on origin/master and whose tree is clean and merged, so a run that
    wrongly adopted it would remove it. ``contract_field`` is the brief's ``contract:`` value.
    Call it AFTER ``merge_records`` (the records commit must stay a fast-forward on the GitHub side)."""
    brief = "\n".join(["---", "id: 60", "title: Sibling item", "type: FEATURE", f"branch: {SIBLING_BRANCH}",
                       f"worktree: {WT_DIR}/{SIBLING_WT}", f"contract: {contract_field}", "status: implementing",
                       "---", "", "# Sibling", ""])
    git(w.ghub, "switch", "-q", "master")
    commit(w.ghub, {".claude/work-items/2026-10-15-60.md": brief}, "sibling brief")
    git(w.ghub, "push", "-q", "origin", "master")
    wt = w.main / WT_DIR / SIBLING_WT
    add_worktree(w.main, wt, "-b", SIBLING_BRANCH, "master")
    return wt


def commit_off_master(w, branch: str) -> str:
    """A local branch that holds one commit origin/master does not have (made without any checkout)."""
    tree = git(w.main, "rev-parse", "master^{tree}")
    sha = git(w.main, "commit-tree", tree, "-p", "master", "-m", f"unmerged work for {branch}")
    git(w.main, "branch", "-f", branch, sha)
    return sha


def land_on_master(w, files: dict) -> dict:
    """Put files on origin/master from the GitHub side, shaped like ``add_sibling_item``: commit them on
    ``w.ghub`` master and push, then fetch into the main checkout so ``origin/master`` holds them there too.
    ``files`` maps a path to its text or bytes (bytes are written as they are, so a CRLF stays a CRLF).
    Call it AFTER ``merge_records`` (the records commit must stay a fast-forward on the GitHub side).
    Returns the path -> bytes map that was committed."""
    git(w.ghub, "switch", "-q", "master")
    landed = {}
    for rel, data in files.items():
        raw = data if isinstance(data, bytes) else data.encode("utf-8")
        target = w.ghub / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        landed[rel] = raw
    git(w.ghub, "add", "-A")
    git(w.ghub, "commit", "-q", "-m", "land files on master")
    git(w.ghub, "push", "-q", "origin", "master")
    git(w.main, "fetch", "-q", "origin")
    return landed


# ---------------------------------------------------------------------------
# Reading a report
# ---------------------------------------------------------------------------
def item_id(item: dict) -> str:
    return str(item.get("name") or item.get("path") or "").replace("\\", "/")


def pick(report: dict, kind: str, needle: str, required: bool = True) -> dict | None:
    """The one item of ``kind`` for the worktree folder (``needle`` is its folder name) or the branch.

    A missing item is an assertion failure that lists what the report holds, unless ``required`` is False."""
    found = []
    for it in report.get("items", []):
        if it.get("kind") != kind:
            continue
        ident = item_id(it)
        if kind == "worktree":
            hit = ident.rstrip("/").rsplit("/", 1)[-1] == needle
        else:
            hit = ident in (needle, "origin/" + needle)
        if hit:
            found.append(it)
    if len(found) > 1:
        raise AssertionError(f"more than one {kind} item names {needle}: {found}")
    if not found and required:
        raise AssertionError(f"the report has no {kind} item for {needle}; its items are "
                             f"{[(i.get('kind'), item_id(i), i.get('action'), i.get('reason')) for i in report.get('items', [])]}")
    return found[0] if found else None


def collect_strings(obj) -> list:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in collect_strings(v)]
    if isinstance(obj, (list, tuple)):
        return [s for v in obj for s in collect_strings(v)]
    return []


def shell_words(text: str) -> list:
    """Split a line quoted the way INV-6 says: single quotes, a ``'`` inside a path written ``'\\''``."""
    words, cur, has, i = [], "", False, 0
    while i < len(text):
        c = text[i]
        if c == "'":
            j = text.index("'", i + 1)
            cur, has, i = cur + text[i + 1:j], True, j + 1
        elif c == "\\" and text[i + 1:i + 2] == "'":
            cur, has, i = cur + "'", True, i + 2
        elif c.isspace():
            if has:
                words.append(cur)
                cur, has = "", False
            i += 1
        else:
            cur, has, i = cur + c, True, i + 1
    if has:
        words.append(cur)
    return words


# ---------------------------------------------------------------------------
# The forbidden-token scanner (INV-5) and its positive control
# ---------------------------------------------------------------------------
def code_tokens(text: str) -> list:
    """(kind, text) of every NAME and string token, leaving out comments and docstrings."""
    fstring_middle = getattr(tokenize, "FSTRING_MIDDLE", -1)
    sig = [t for t in tokenize.generate_tokens(io.StringIO(text).readline) if t.type not in (tokenize.NL, tokenize.COMMENT)]
    out = []
    for i, tok in enumerate(sig):
        if tok.type == tokenize.NAME:
            out.append(("name", tok.string))
        elif tok.type in (tokenize.STRING, fstring_middle):
            prev = sig[i - 1].type if i else None
            nxt = sig[i + 1].type if i + 1 < len(sig) else None
            is_docstring = tok.type == tokenize.STRING and prev in (None, tokenize.NEWLINE, tokenize.INDENT,
                                                                     tokenize.DEDENT) and nxt == tokenize.NEWLINE
            if not is_docstring:
                out.append(("string", tok.string))
    return out


#: The ONE force form INV-5 allows: the remote delete's lease on the tip that was checked (W8). Everything else
#: that holds `--force` is a hit, including a bare `--force-with-lease`.
LEASE_PREFIX = "--force-with-lease=refs/heads/"


def forbidden_hits(text: str) -> list:
    """INV-5 tripwire over code tokens (docstrings and comments excluded): force, prune, rmtree, switch, checkout,
    rm -rf. A tripwire, not a proof: the call-log invariant of every world test is the proof for git commands."""
    hits = []
    for kind, value in code_tokens(text):
        if kind == "name" and value == "rmtree":
            hits.append("rmtree")
        elif kind == "string":
            if "--force" in value.replace(LEASE_PREFIX, ""):
                hits.append("--force")
            if re.search(r"\bprune\b", value):
                hits.append("prune")
            if "rmtree" in value:
                hits.append("rmtree")  # the string form, e.g. getattr(shutil, "rmtree")
            bare = value.strip("'\"")
            if bare == "-f":
                hits.append("-f")
            if bare in ("switch", "checkout"):
                hits.append(bare)
            if bare in ("-rf", "-fr") or re.search(r"\brm\s+-[a-zA-Z]*[rf]", value):
                hits.append("rm -rf")
    return hits


# ---------------------------------------------------------------------------
# Holder reading (contract 2026-10-18-cleanup-names-worktree-holder.md): a fake ``claude``, the session records
# it prints, a cleaned environment, and the process-control tripwire
# ---------------------------------------------------------------------------
#: The fake ``claude``. It may be called ONLY as ``agents --json --all`` (the call log proves it). It logs its
#: argv, optionally writes its pid, sleeps (rewriting a heartbeat file every 0.2 s while it does), then prints
#: the configured text and exits with the configured code. Default: prints ``[]``.
FAKE_CLAUDE_CODE = r'''
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(sys.argv[0]))
with open(os.path.join(HERE, "claude_calls.jsonl"), "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"args": sys.argv[1:], "cwd": os.getcwd()}) + "\n")
with open(os.path.join(HERE, "claude_config.json"), encoding="utf-8") as fh:
    cfg = json.load(fh)
if cfg.get("pidfile"):
    with open(cfg["pidfile"], "w", encoding="utf-8") as fh:
        fh.write(str(os.getpid()))
end = time.time() + float(cfg.get("sleep", 0))
while time.time() < end:
    if cfg.get("heartbeat"):
        with open(cfg["heartbeat"], "w", encoding="utf-8") as fh:
            fh.write(repr(time.time()))
    time.sleep(0.2)
if cfg.get("stdout_b64") is not None:  # raw-bytes mode: exactly these bytes, valid UTF-8 or not
    import base64
    raw = base64.b64decode(cfg["stdout_b64"])
else:
    raw = cfg.get("stdout", "[]").encode("utf-8")
if cfg.get("pad_to"):  # trailing spaces after the JSON, up to this many bytes in all (a very large answer)
    raw += b" " * max(0, int(cfg["pad_to"]) - len(raw))
sys.stdout.buffer.write(raw)
sys.stdout.flush()
sys.exit(int(cfg.get("code", 0)))
'''

#: The variables the cleanup must never see unless a test sets them: a run inside a real Claude Code session
#: would otherwise leak its own id into the tests (HN-7).
HOLDER_ENV_STRIPPED = ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID", "CLAUDE_JOB_DIR", "CLAUDE_CODE_AGENT")
STOP_ARGV = ["agents", "--json", "--all"]
NOTE_TEXT = ("; note: the session list shows background sessions only; a session typed into a terminal, "
             "an editor or another program may also hold this folder")
NONE_FOUND_BRACKET = "[no background session in the list is in it]"
WARNING_TEXT = "; warning: the running session was not recognised, so one stop command may be its own"
REASON_NOT_FOUND = "the claude command was not found"
REASON_NOT_STARTED = "the claude command could not be started"
REASON_FORM = "the session list was not in the expected form"
PRECEDENCE_SENTENCE = "If the user tells you to keep working, their instruction comes first and you keep working."
HN11_PARAGRAPH = ("Once the pull request is merged and the work is delivered, end this session with `/stop` before the "
                  "delivery cleanup runs (or runs again): a session left running keeps its worktree folder in use, and "
                  "the cleanup then has to leave that folder behind. `/exit` only detaches and leaves the session "
                  "running; from another terminal, `claude stop <id>` stops it, where `<id>` is the 8-character id "
                  "that `claude agents` shows.")


def cleanup_env(extra: dict | None, tools: Tools) -> dict:
    """``clean_env`` with the session variables stripped, then ``extra`` (so a test can set one on purpose)."""
    env = clean_env(None, tools=tools)
    for key in HOLDER_ENV_STRIPPED:
        env.pop(key, None)
    if extra:
        env.update(extra)
    return env


def install_fake_claude(tools: Tools) -> None:
    """The executable is written ONCE per folder (like install_gh); the default list is ``[]``."""
    if not (tools.bin / ("claude.exe" if os.name == "nt" else "claude")).exists():
        write_exe(tools.bin, "claude", FAKE_CLAUDE_CODE)
    set_claude(tools, [])


def set_claude(tools: Tools, sessions=None, *, stdout: str | None = None, code: int = 0, sleep: float = 0,
               heartbeat=None, pidfile=None, raw: bytes | None = None, pad_to: int = 0) -> None:
    """``raw`` makes the fake print exactly these bytes (non-ASCII UTF-8, invalid UTF-8); ``pad_to`` adds trailing
    spaces up to that many bytes in all (the 4 MiB limit)."""
    text = stdout if stdout is not None else json.dumps(sessions if sessions is not None else [])
    cfg = {"stdout": text, "code": code, "sleep": sleep, "heartbeat": str(heartbeat) if heartbeat else None,
           "pidfile": str(pidfile) if pidfile else None, "pad_to": pad_to}
    if raw is not None:
        import base64
        cfg["stdout_b64"] = base64.b64encode(raw).decode("ascii")
    (tools.bin / "claude_config.json").write_text(json.dumps(cfg), encoding="utf-8")


def end_fake_claude(pidfile: Path) -> None:
    """Cleanup of a fake `claude` this run started and a timeout left running: end it by the pid it wrote, wait until
    it is gone (polling, not a fixed sleep), so the folder holding its executable can be deleted."""
    try:
        pid = int(Path(pidfile).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return
    deadline = time.time() + 10
    while time.time() < deadline:
        if IS_WINDOWS:
            run_cmd(["taskkill", "/F", "/PID", str(pid)], cwd=Path(pidfile).parent)
            alive = str(pid) in run_cmd(["tasklist", "/FI", "PID eq %d" % pid, "/NH"], cwd=Path(pidfile).parent).out
        else:
            try:
                os.kill(pid, 9)
                os.waitpid(pid, os.WNOHANG)
                alive = True
            except OSError:
                alive = False
        if not alive:
            return
        time.sleep(0.1)


def claude_calls(tools: Tools) -> list:
    f = tools.bin / "claude_calls.jsonl"
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()] if f.exists() else []


#: The shape of one record of ``claude agents --json --all`` on a real machine (A8): a bare list of these.
REAL_RECORD_KEYS = ("cwd", "id", "kind", "name", "pid", "sessionId", "startedAt", "state", "status")
REAL_STATES = ("blocked", "done", "stopped", "working")


def sess(short: str, cwd, *, name: str = "worker", state: str = "done", full: str | None = None, kind: str = "background",
         pid: int | None = None, status: str | None = None, drop: tuple = (), **extra) -> dict:
    """One record in the real shape: cwd, id, kind, name, pid, sessionId, startedAt, state, status."""
    try:
        default_pid = 1000 + int(short, 16) % 50000
    except ValueError:
        default_pid = 4242
    rec = {"id": short, "sessionId": full if full is not None else short + "-0000-4000-8000-000000000000",
           "cwd": str(cwd), "kind": kind, "name": name, "startedAt": 1760000000000, "state": state,
           "pid": pid if pid is not None else default_pid, "status": status if status is not None else "Idle for 3m"}
    rec.update(extra)
    for key in drop:
        rec.pop(key, None)
    return rec


def full_id(short: str) -> str:
    return short + "-0000-4000-8000-000000000000"


def many_ids(n: int) -> list:
    return ["a%07x" % i for i in range(1, n + 1)]


def synth_holder(short, *, name: str = "worker", state: str = "done", this: bool = False, stop: str | None = "auto") -> dict:
    """A Holder as the contract's Data Shapes write it, for ``build_line`` on synthetic items."""
    if stop == "auto":
        stop = None if (this or short is None) else "claude stop " + short
    return {"id": short, "session_id": full_id(short) if short else None, "name": name, "state": state, "kind": "background",
            "started_at": 1760000000000, "cwd": "C:/r/.claude/worktrees/" + FW_NAME, "this_session": this, "stop_command": stop}


def synth_item(holders, *, verdict: str = "found", reason: str | None = None, recognised: bool = False,
               name: str = FW_NAME, repair: str | None = None) -> dict:
    item = {"kind": "worktree", "path": "C:/r/.claude/worktrees/" + name, "action": "deferred", "reason": "standing-tree",
            "files": [], "detail": None, "links": [], "identical": [],
            "holders": {"verdict": verdict, "sessions": holders, "this_session_recognised": recognised}}
    if reason:
        item["holders"]["reason"] = reason
    if repair:
        item["repair"] = repair
    return item


def need_names(testcase: unittest.TestCase, module, *names: str) -> None:
    """A missing production name is a clear failure of THIS test, never an AttributeError."""
    missing = [n for n in names if not hasattr(module, n)]
    if missing:
        testcase.fail("cleanup_delivered.py does not define " + ", ".join(missing) + " yet (contract "
                      "2026-10-18-cleanup-names-worktree-holder.md, Extension Points): the implementer adds it in GREEN")


#: Tripwire for the holder lookup (HN-9, decision A1): the runner ends ONLY its own child, with ``proc.kill()``.
#: FORBIDDEN_*: never allowed anywhere, not even in the exempt functions (no killpg, no taskkill, no new session or
#: process group, no signals, no terminate). Exactly three exemptions (HN-9), each ONE name in ONE function:
#: ``subprocess.run`` inside ``_exec``, ``Popen`` inside ``_run_holder_list``, ``kill`` inside ``_end_own_child``.
#: Every other spawner (``run`` elsewhere, ``call``, ``check_*``, ``os.spawn*``, ``os.exec*``, ``os.posix_spawn*``)
#: is flagged in every function. A tripwire, not a proof: the in-process recorders are the proof.
FORBIDDEN_NAMES = {"killpg", "terminate", "send_signal", "signal", "system", "popen", "startfile", "TerminateProcess",
                   "OpenProcess", "start_new_session", "setsid", "CREATE_NEW_PROCESS_GROUP", "process_group", "preexec_fn"}
FORBIDDEN_STRINGS = {"taskkill", "pkill", "killall", "Stop-Process"}
NAME_HOMES = {"kill": "_end_own_child", "Popen": "_run_holder_list", "subprocess.run": "_exec"}
EXEMPT_ONLY_STRINGS = {"stop", "kill", "rm", "del", "rmdir"}
SPAWN_FUNCTIONS = {"subprocess": {"run", "call", "check_call", "check_output", "getoutput", "getstatusoutput"}}
SPAWN_PREFIXES = {"os": ("spawn", "exec", "posix_spawn"), "asyncio": ("create_subprocess",)}
#: Names that start a process or a job object by another route (Windows API through ctypes, a pty), forbidden by
#: prefix everywhere, the three exempt functions included. The hit is the prefix, e.g. ``CreateProcess``.
FORBIDDEN_PREFIXES = ("CreateProcess", "CreateJobObject", "TerminateJobObject")
FORBIDDEN_MODULE_NAMES = {"pty", "ctypes"}
#: Modules that may be imported only as a plain ``import x`` (no alias, no ``from x import ...``): an alias or a
#: bare imported name would hide ``subprocess.Popen`` / ``os.kill`` from the token scan.
PLAIN_IMPORT_ONLY = {"subprocess", "os", "asyncio", "signal", "ctypes", "pty"}
PROCESS_EXEMPT = ("_run_holder_list", "_end_own_child")


def _starts_claude_stop(node) -> bool:
    """True when the expression is text that begins ``claude stop``: a literal, a ``%`` or ``.format`` or f-string of one."""
    import ast
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str) and node.value.lstrip().startswith("claude stop")
    if isinstance(node, ast.JoinedStr):
        return bool(node.values) and _starts_claude_stop(node.values[0])
    if isinstance(node, ast.BinOp):
        return _starts_claude_stop(node.left)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("format", "strip", "lstrip"):
        return _starts_claude_stop(node.func.value)
    return False


def process_control_hits(text: str, exempt: tuple = PROCESS_EXEMPT, homes: dict = NAME_HOMES) -> list:
    import ast
    tree = ast.parse(text)
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    ranges = [(n.lineno, n.end_lineno) for n in funcs if n.name in exempt]

    def home_ranges(name: str) -> list:
        return [(n.lineno, n.end_lineno) for n in funcs if n.name == homes.get(name)]

    fstring_middle = getattr(tokenize, "FSTRING_MIDDLE", -1)
    sig = [t for t in tokenize.generate_tokens(io.StringIO(text).readline) if t.type not in (tokenize.NL, tokenize.COMMENT)]
    hits = []
    for node in ast.walk(tree):  # an alias or a bare import hides the dotted name from the token scan
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in PLAIN_IMPORT_ONLY and alias.asname:
                    hits.append("import %s as" % alias.name)
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in PLAIN_IMPORT_ONLY:
            hits.append("from %s import" % node.module)
    stack: list = []  # per open bracket: [opening char, token before it, saw a `for`]
    for i, tok in enumerate(sig):
        if tok.type == tokenize.OP and tok.string in "([{":
            stack.append([tok.string, sig[i - 1].string if i else "", False])
        elif tok.type == tokenize.OP and tok.string in ")]}" and stack:
            stack.pop()
        elif tok.type == tokenize.NAME and tok.string == "for" and stack:
            stack[-1][2] = True
        line = tok.start[0]
        exempt_here = any(a <= line <= b for a, b in ranges)

        def at_home(name: str) -> bool:
            return any(a <= line <= b for a, b in home_ranges(name))

        if tok.type == tokenize.NAME:
            if tok.string in FORBIDDEN_NAMES or tok.string in FORBIDDEN_MODULE_NAMES:
                hits.append(tok.string)
            elif tok.string.startswith(FORBIDDEN_PREFIXES):
                hits.append(next(p for p in FORBIDDEN_PREFIXES if tok.string.startswith(p)))
            elif tok.string in ("kill", "Popen"):
                if not at_home(tok.string):
                    hits.append(tok.string)
            elif i + 2 < len(sig) and sig[i + 1].string == "." and sig[i + 2].type == tokenize.NAME:
                attr = sig[i + 2].string
                dotted = tok.string + "." + attr
                if attr in SPAWN_FUNCTIONS.get(tok.string, ()) or attr.startswith(SPAWN_PREFIXES.get(tok.string, ("\0",))):
                    if not at_home(dotted):
                        hits.append(dotted)
                elif dotted == "os.kill":  # a process id of its own choosing: never, not even inside _end_own_child
                    hits.append(dotted)
        elif tok.type in (tokenize.STRING, fstring_middle):
            prev = sig[i - 1].type if i else None
            nxt = sig[i + 1].type if i + 1 < len(sig) else None
            if tok.type == tokenize.STRING and prev in (None, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT) \
                    and nxt == tokenize.NEWLINE:
                continue  # a docstring
            bare = tok.string.strip("'\"")
            if bare in FORBIDDEN_STRINGS or (bare in EXEMPT_ONLY_STRINGS and not exempt_here):
                hits.append(bare)
            if not exempt_here and bare.startswith("claude stop") and "%" not in bare and "{" not in bare:
                for opener in stack:  # a plain "claude stop ..." literal inside a list handed to a call
                    if opener[0] == "[" and opener[1] in ("(", ",") and not opener[2]:
                        hits.append("claude stop in an argument list")
                        break
    for node in ast.walk(tree):  # text beginning "claude stop" cut into words: that is how a stop would be launched
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "split" and _starts_claude_stop(func.value):
            hits.append("claude stop split into words")
        elif isinstance(func, (ast.Attribute, ast.Name)) and getattr(func, "attr", getattr(func, "id", "")) == "split" \
                and node.args and _starts_claude_stop(node.args[0]):
            hits.append("claude stop split into words")
    return hits


def name_references(text: str, name: str) -> list:
    """Every use of ``name`` outside its own definition: a call, an alias (``x = name``), an argument, an attribute
    or a string that spells it. Returns ``(enclosing function, kind)`` pairs, kind ``call`` or ``reference``."""
    import ast
    tree = ast.parse(text)
    found: list = []

    def visit(node, owner):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name:
                return  # its own definition (a recursive call would still be a use, but it has none)
            owner = node.name
        if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) == name:
            found.append((owner, "call"))
            for child in list(node.args) + [k.value for k in node.keywords]:
                visit(child, owner)
            return
        if (isinstance(node, ast.Name) and node.id == name) or (isinstance(node, ast.Attribute) and node.attr == name) \
                or (isinstance(node, ast.Constant) and node.value == name):
            found.append((owner, "reference"))
        for child in ast.iter_child_nodes(node):
            visit(child, owner)

    visit(tree, "<module>")
    return found


def end_own_child_problems(text: str) -> list:
    """B7(4): the body of ``_end_own_child`` holds exactly ONE call, and it is ``<first parameter>.kill()`` with no
    arguments at all. (A ``try/except OSError`` around it is allowed; a second call, an argument, another receiver is not.)"""
    import ast
    tree = ast.parse(text)
    funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_end_own_child"]
    if len(funcs) != 1:
        return ["_end_own_child is defined %d times" % len(funcs)]
    func = funcs[0]
    params = [a.arg for a in func.args.args]
    if len(params) != 1:
        return ["_end_own_child takes %d parameters, not one" % len(params)]
    calls = [c for c in ast.walk(func) if isinstance(c, ast.Call)]
    if len(calls) != 1:
        return ["%d calls in the body, not exactly one" % len(calls)]
    call = calls[0]
    func_node = call.func
    if not (isinstance(func_node, ast.Attribute) and func_node.attr == "kill" and isinstance(func_node.value, ast.Name)
            and func_node.value.id == params[0]):
        return ["the one call is not %s.kill()" % params[0]]
    if call.args or call.keywords:
        return ["kill() is called with arguments"]
    # The accepted body is exactly: [docstring] try: <param>.kill() except OSError: pass
    body = list(func.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    if len(body) != 1 or not isinstance(body[0], ast.Try):
        return ["the body is not exactly one try statement"]
    node = body[0]
    if node.orelse or node.finalbody:
        return ["the try has an else or finally part"]
    if not (len(node.body) == 1 and isinstance(node.body[0], ast.Expr) and node.body[0].value is call):
        return ["the try body is not the one kill call"]
    if len(node.handlers) != 1:
        return ["the try has %d handlers, not one" % len(node.handlers)]
    handler = node.handlers[0]
    if not (isinstance(handler.type, ast.Name) and handler.type.id == "OSError"):
        return ["the handler does not catch exactly OSError"]
    if not (len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass)):
        return ["the handler body is not exactly `pass`"]
    return []


# ===========================================================================
# Base case
# ===========================================================================
class CleanupCase(unittest.TestCase):
    world_kwargs: dict = {}

    def setUp(self) -> None:
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="cleanup_")))
        self.addCleanup(rmtree_force, self.tmp)
        self.procs: list = []
        self.addCleanup(self._reap)  # registered second: runs first, so no holder blocks the delete
        self.worlds: list = []
        self.addCleanup(self.assert_call_log_invariants)  # runs before the delete, while the logs still exist
        self.w = build_world(self.tmp, **self.world_kwargs)
        self.worlds.append(self.w)

    def assert_call_log_invariants(self) -> None:
        """INV-5 and the gh allow-list, over EVERY world this test built (reviewer F5/F6): a failure path is
        exactly where a 'retry with force' or a 'fall back to prune' would be added."""
        offenders = []
        for world in self.worlds:
            for call in git_calls(world.tools):
                why = forbidden_git_use(call["args"])
                if why:
                    offenders.append(f"git {' '.join(call['args'])}: {why}")
            for call in world.tools.gh_calls():
                why = forbidden_gh_use(call)
                if why:
                    offenders.append(f"gh {' '.join(call.get('args', []))}: {why}")
        self.assertEqual(offenders, [], msg="INV-5: no prune, no force (but the one lease form), no switch, checkout or "
                                            "rm in any git call, and gh only reads (pr list, pr view)")
        odd = [c["args"] for world in self.worlds for c in claude_calls(world.tools) if c["args"] != STOP_ARGV]
        self.assertEqual(odd, [], msg="HN-2/HN-9: `claude` is called only as `agents --json --all`, never `stop` or anything else")

    def _reap(self) -> None:
        for p in self.procs:
            try:
                p.kill()
                p.wait(timeout=10)
            except Exception:
                pass

    def rebuild(self, **kwargs) -> SimpleNamespace:
        """A second, different world in its own folder (for tests that need another shape)."""
        other = Path(os.path.realpath(tempfile.mkdtemp(prefix="cleanup_")))
        self.addCleanup(rmtree_force, other)
        self.w = build_world(other, **kwargs)
        self.worlds.append(self.w)
        return self.w

    # -- running the script --------------------------------------------------------------------------
    def cleanup(self, *flags: str, cwd=None, from_dir=None, env_extra: dict | None = None, as_json: bool = True,
                contract: str = SLUG):
        self.assertTrue(CLEANUP.is_file(), msg=MISSING)
        args = ["--contract", contract, "--from", str(from_dir or self.w.main), *flags]
        if as_json:
            args.append("--json")
        proc = run_py(CLEANUP, *args, cwd=cwd or self.w.main, env=cleanup_env(env_extra, self.w.tools))
        return proc, (proc.json() if as_json else None)

    def need_report(self, proc, report, what: str) -> dict:
        self.assertIsInstance(report, dict, msg=f"{what}: --json must print one Cleanup Report object, got {proc.describe()}")
        return report

    def run_report(self, *flags, what: str = "the cleanup", **kw):
        proc, report = self.cleanup(*flags, **kw)
        return proc, self.need_report(proc, report, what)

    def load_module(self):
        self.assertTrue(CLEANUP.is_file(), msg=MISSING)
        sys.path.insert(0, str(SCRIPTS_DIR))
        try:
            return importlib.import_module("cleanup_delivered")
        finally:
            if str(SCRIPTS_DIR) in sys.path:
                sys.path.remove(str(SCRIPTS_DIR))

    def run_in_process(self, flags: list, *, patches: dict, env_extra: dict | None = None):
        """``main(argv)`` of the script inside this process, with ``patches`` ({"os.rename": fn}) in force."""
        module = self.load_module()
        self.assertTrue(hasattr(module, "main"), msg="cleanup_delivered.py must expose main(argv) like flat_worktree.py does")
        argv = ["--contract", SLUG, "--from", str(self.w.main), *flags, "--json"]
        out = io.StringIO()
        saved_cwd = os.getcwd()
        try:
            os.chdir(str(self.w.main))
            with mock.patch.dict(os.environ, cleanup_env(env_extra, self.w.tools), clear=True), \
                    contextlib.redirect_stdout(out), contextlib.ExitStack() as stack:
                for target, fn in patches.items():
                    stack.enter_context(mock.patch(target, fn))
                try:
                    rc = module.main(argv)
                except SystemExit as exc:
                    rc = exc.code
        finally:
            os.chdir(saved_cwd)
        try:
            report = json.loads(out.getvalue())
        except ValueError:
            report = None
        return rc, out.getvalue(), report

    # -- shared assertions ---------------------------------------------------------------------------
    def deliver(self, *, delete_remote: bool = True) -> None:
        merge_records(self.w, delete_remote=delete_remote)

    def assertUntouched(self, before: dict, main_before: dict, what: str) -> None:
        self.assertEqual(state(self.w), before, msg=f"{what}: no worktree, branch, remote branch or file may change")
        self.assertEqual(snapshot(self.w.main), main_before,
                         msg=f"{what}: the main checkout's HEAD, index and files must be byte-identical")
        self.assertEqual(mutating_calls(self.w.tools), [],
                         msg=f"{what}: before delivery only a fetch, git reads, ls-remote and gh pr list may run; "
                             f"saw {mutating_calls(self.w.tools)}")

    def assertGone(self, path: Path, what: str) -> None:
        self.assertFalse(path.exists(), msg=f"{what}: the folder {path.name} must be gone")
        self.assertNotIn(real(path), worktree_paths(self.w.main), msg=f"{what}: git must no longer list {path.name}")

    def assertKept(self, path: Path, what: str) -> None:
        self.assertTrue(path.is_dir(), msg=f"{what}: the folder {path.name} must be untouched")
        self.assertIn(real(path), worktree_paths(self.w.main), msg=f"{what}: git must still list {path.name}")

    def make_link(self, parent: Path, name: str, target: Path) -> Path:
        target.mkdir(parents=True, exist_ok=True)
        (target / "pkg").mkdir(exist_ok=True)
        (target / "pkg" / "index.js").write_text("module.exports = 1;\n", encoding="utf-8")
        parent.mkdir(parents=True, exist_ok=True)
        link = parent / name
        make_directory_link(link, target)
        return link

    def assertTargetSurvived(self, target: Path, what: str) -> None:
        self.assertEqual((target / "pkg" / "index.js").read_text(encoding="utf-8"), "module.exports = 1;\n",
                         msg=f"{what}: the link's real target and its file must survive (INV-4)")


# ===========================================================================
# Fixture sanity (passes today: proves the world is what the docstring says)
# ===========================================================================
class DeliveredWorldFixtureTests(CleanupCase):
    def test_the_world_has_the_owned_set_the_contract_describes_and_origin_is_stale_in_the_main_checkout(self):
        w = self.w
        for path in (w.fw, w.tw, w.aw):
            self.assertIn(real(path), worktree_paths(w.main), msg=f"fixture: {path.name} must be a linked worktree")
        self.assertEqual(git(w.main, "rev-parse", "--abbrev-ref", "HEAD"), "main-side",
                         msg="fixture: the main checkout sits on a non-owned branch")
        for branch in OWNED_BRANCHES:
            self.assertIn(branch, local_branches(w), msg=f"fixture: owned branch {branch} must exist locally")
            self.assertIn(branch, remote_heads(w), msg=f"fixture: owned branch {branch} must exist on origin")
        self.assertNotEqual(git(w.main, "rev-parse", "origin/master"), git(w.origin, "rev-parse", "master"),
                            msg="fixture: the main checkout's origin/master is STALE, so only a fetch can find the feature")
        self.assertIn("approved", git(w.main, "show", "origin/master:" + CONTRACT_REL) + git(w.origin, "show", "master:" + CONTRACT_REL),
                      msg="fixture: stage 1 has the contract still approved on origin/master")


# ===========================================================================
# [1] Without a manual step: three calls; the skills run it on every call
# ===========================================================================
class EntryPointThreeCallsTests(CleanupCase):
    def test_records_pull_request_open_reads_not_delivered_touches_nothing_and_says_when_it_runs_again(self):
        before, main_before = state(self.w), snapshot(self.w.main)

        proc, report = self.run_report(what="stage 1, records pull request open")

        self.assertEqual(proc.rc, 5, msg=f"INV-1: not delivered is exit 5, which the skills treat as normal; got {proc.describe()}")
        self.assertEqual(report.get("outcome"), "not-delivered", msg="the outcome names why nothing happened")
        self.assertEqual(report.get("delivery", {}).get("verdict"), "not-delivered", msg="the Delivery Reading verdict")
        first = (report.get("delivery", {}).get("reasons") or [None])[0]
        self.assertEqual(first, f"records pull request {RECORDS_URL} not merged yet",
                         msg="INV-1: while the records pull request is open its url is the first reason")
        self.assertEqual(report.get("line"),
                         f"CLEANUP {SLUG}: not delivered yet ({first}); nothing removed; "
                         "runs again on the next /pr-merged or /advance",
                         msg="INV-8: the not-delivered line has this exact shape, with the rerun hint")
        self.assertTrue(any(sub_command(c["args"])[:1] == ["fetch"] for c in git_calls(self.w.tools)),
                        msg="INV-1: the delivery reading starts with `git fetch origin <default>`")
        self.assertUntouched(before, main_before, "stage 1")

    def test_the_line_alone_is_printed_without_json_and_it_is_one_line(self):
        proc, _ = self.cleanup(as_json=False)

        self.assertEqual(proc.rc, 5, msg=f"exit 5 without --json too; got {proc.describe()}")
        text = proc.out.strip()
        self.assertTrue(text.startswith(f"CLEANUP {SLUG}: not delivered yet ("), msg=f"the printed line, got {proc.describe()}")
        self.assertNotIn("\n", text, msg="INV-8: the printed report is a single line")

    def test_three_calls_not_delivered_then_cleaned_then_a_no_op(self):
        w = self.w
        main_before = snapshot(w.main)

        proc1, report1 = self.run_report(what="call 1")
        self.assertEqual(proc1.rc, 5, msg=f"call 1 (records pull request open) is exit 5; got {proc1.describe()}")
        self.assertTrue(all(p.exists() for p in (w.fw, w.tw, w.aw)), msg="call 1 removes nothing")

        self.deliver()
        w.tools.clear_git_calls()
        proc2, report2 = self.run_report(what="call 2")

        self.assertEqual(proc2.rc, 0, msg=f"call 2 (records pull request merged) cleans everything; got {proc2.describe()}")
        self.assertEqual(report2.get("outcome"), "cleaned", msg="call 2 outcome")
        self.assertEqual(report2.get("delivery", {}).get("verdict"), "delivered",
                         msg="INV-1: after the merge the stale local origin/master was fetched, so the flip is seen")
        for path, label in ((w.fw, "feature worktree"), (w.tw, "sub-task worktree"), (w.aw, "advance worktree")):
            self.assertGone(path, f"call 2, {label}")
        for branch in OWNED_BRANCHES:
            self.assertNotIn(branch, local_branches(w), msg=f"call 2: the merged local branch {branch} must be deleted")
        self.assertEqual(git(w.main, "rev-parse", "--abbrev-ref", "HEAD"), "main-side", msg="call 2: no switch in the main checkout")
        self.assertEqual(snapshot(w.main), main_before, msg="call 2: the main checkout is byte-identical")
        removed = [i for i in report2["items"] if i.get("action") == "removed"]
        self.assertGreaterEqual(len(removed), 6, msg="three worktrees and three local branches were removed")
        self.assertRegex(report2.get("line", ""), rf"^CLEANUP {re.escape(SLUG)}: removed {len(removed)} \(",
                         msg="INV-8: the delivered line starts with the count of removed items")

        after_clean = state(w)
        w.tools.clear_git_calls()
        proc3, report3 = self.run_report(what="call 3")

        self.assertEqual(proc3.rc, 0, msg=f"call 3 is a no-op, exit 0; got {proc3.describe()}")
        self.assertIn(report3.get("outcome"), ("cleaned", "nothing-owned"), msg="call 3 outcome")
        self.assertEqual([i for i in report3["items"] if i.get("action") == "removed"], [],
                         msg="call 3 removes nothing: it is idempotent")
        self.assertEqual(state(w), after_clean, msg="call 3 changes nothing")
        self.assertEqual(mutating_calls(w.tools), [], msg="call 3 runs no mutating git command")

    def test_a_full_run_never_prunes_forces_or_switches_a_tree(self):
        self.deliver()
        self.w.tools.clear_git_calls()

        self.run_report(what="a full delivered run")

        self.assertTrue(git_calls(self.w.tools), msg="positive control: the wrapper git saw the run")
        for call in git_calls(self.w.tools):
            args = call["args"]
            self.assertNotIn("prune", args, msg=f"INV-5: no `git worktree prune`, saw {args}")
            self.assertNotIn("--force", args, msg=f"INV-5: no forced removal, saw {args}")
            self.assertFalse({"switch", "checkout"} & set(args), msg=f"INV-5: no switch or checkout in any tree, saw {args}")
            if sub_command(args)[:2] == ["worktree", "remove"]:
                self.assertNotIn("-f", args, msg=f"INV-5: no `worktree remove -f`, saw {args}")


SKILLS = REPO_ROOT / "skills"


def read_skill(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def section(text: str, heading: str) -> str:
    m = re.search(rf"^## {heading}.*?(?=^## |\Z)", text, re.S | re.M)
    return m.group(0) if m else ""


def fenced_lines(text: str) -> list:
    inside, out = False, []
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            inside = not inside
        elif inside:
            out.append(line)
    return out


def fenced_blocks(text: str) -> list:
    blocks, cur, inside = [], [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            if inside:
                blocks.append(cur)
                cur = []
            inside = not inside
        elif inside:
            cur.append(line)
    return blocks


def cln_block(name: str) -> list:
    """The fenced bash block of a skill that looks up `CLN` and runs the cleanup script."""
    for block in fenced_blocks(read_skill(name)):
        joined = "\n".join(block)
        if "CLN=" in joined and "cleanup_delivered.py" in joined:
            return block
    raise AssertionError(f"skills/{name}/SKILL.md has no fenced block that resolves CLN and runs cleanup_delivered.py")


def posix_path(p) -> str:
    return str(p).replace("\\", "/")


def from_msys(value: str) -> str:
    """`/c/Users/x` (what Git Bash shows) as `C:/Users/x`, so `real()` can compare it."""
    if os.name == "nt" and re.match(r"^/[a-zA-Z]/", value):
        return value[1].upper() + ":" + value[2:]
    return value


def run_in_git_bash(script: str, *, cwd, env_extra: dict) -> subprocess.CompletedProcess:
    bash = find_git_bash()
    if bash is None:
        raise AssertionError("Git Bash next to git is needed: a skill's shell block has no meaning without a shell")
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE") and not k.startswith("GIT_")}
    env.update(env_extra)
    return subprocess.run([bash, "--noprofile", "--norc", "-c", script], cwd=str(cwd), env=env, capture_output=True,
                          text=True, timeout=180)


STUB_SCRIPT = (
    "import json, os, sys\n"
    "with open(os.environ['STUB_LOG'], 'a', encoding='utf-8') as fh:\n"
    "    fh.write(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd()}) + '\\n')\n"
    "if '--print-main-root' in sys.argv:\n"
    "    print(os.environ['STUB_MAIN_ROOT'])\n")

MANUAL_CLEANUP = re.compile(r"^\s*git\s+(worktree\s+(remove|prune)\b|branch\s+-[dD]\b)")


class SkillWiringTests(unittest.TestCase):
    """[1] 'Skill text test: Step 6 and /advance run the script on every call, no manual lines.'"""

    def test_pr_merged_step_6_runs_the_cleanup_script_automatically_and_offers_nothing(self):
        text = read_skill("pr-merged")
        step6 = section(text, "Step 6")

        self.assertTrue(step6, msg="skills/pr-merged/SKILL.md must keep a '## Step 6' section")
        self.assertNotRegex(step6.splitlines()[0], r"(?i)offer", msg="Step 6 is no longer an offer: it runs on every call")
        for needle in ("cleanup_delivered.py", "--print-main-root", "--contract", "--from", "--json", "remove-remote", "CLN"):
            self.assertIn(needle, step6, msg=f"Step 6 must carry `{needle}` (contract Extension Points)")
        self.assertRegex(step6, r"(?i)every", msg="Step 6 must say the cleanup runs on every call")
        self.assertRegex(step6, r"(?i)\b5\b", msg="Step 6 must say that exit 5 (not delivered yet) is normal")

    def test_pr_merged_has_no_manual_cleanup_lines_anywhere_in_a_code_block(self):
        offending = [l for l in fenced_lines(read_skill("pr-merged")) if MANUAL_CLEANUP.match(l)]

        self.assertEqual(offending, [], msg="the three manual lines (worktree remove, worktree prune, branch -d) are replaced by the script")

    def test_pr_merged_step_7_prints_the_script_line_verbatim_and_anti_patterns_name_the_new_rules(self):
        text = read_skill("pr-merged")

        self.assertRegex(section(text, "Step 7"), r"(?m)^- Cleanup:.*\bline\b",
                         msg="Step 7's report has a `- Cleanup:` line that carries the script's `line` verbatim")
        anti = section(text, "Anti-patterns")
        for needle in ("prune", "remove-remote"):
            self.assertIn(needle, anti, msg=f"the anti-patterns gain an entry about `{needle}` (contract Extension Points)")

    def test_advance_runs_the_cleanup_on_every_call_not_only_in_one_state(self):
        text = read_skill("advance")

        for needle in ("cleanup_delivered.py", "--contract", "--from", "remove-remote"):
            self.assertIn(needle, text, msg=f"skills/advance/SKILL.md must carry `{needle}`")
        self.assertRegex(text, r"(?is)every.{0,300}cleanup_delivered|cleanup_delivered.{0,500}every",
                         msg="advance must say the cleanup runs on EVERY call")
        spots = [m.start() for m in re.finditer("cleanup_delivered.py", text)]
        headings = [(m.start(), m.group(0)) for m in re.finditer(r"^#{2,3} .*$", text, re.M)]
        outside_move_sections = []
        for pos in spots:
            nearest = [h for p, h in headings if p < pos][-1:]
            if not nearest or not nearest[0].startswith("### `"):
                outside_move_sections.append(pos)
        self.assertTrue(outside_move_sections,
                        msg="the cleanup call must live in a step that runs whatever the move is, not inside one "
                            "move's own section (`### `complete``, `### `dispatch``, ...)")
        self.assertEqual([l for l in fenced_lines(text) if MANUAL_CLEANUP.match(l)], [], msg="no manual cleanup lines in advance")

    # -- W4: the cleanup comes before the report that prints its line ---------------------------------
    def test_in_advance_the_cleanup_heading_comes_before_the_report_heading(self):
        text = read_skill("advance")
        headings = [(m.start(), m.group(0)) for m in re.finditer(r"^## .*$", text, re.M)]
        cleanup = [pos for pos, h in headings if re.search(r"(?i)clean", h)]
        report = [pos for pos, h in headings if re.search(r"(?i)\breport\b", h)]

        self.assertTrue(cleanup and report, msg=f"advance needs a cleanup heading and a report heading, got {[h for _p, h in headings]}")
        self.assertLess(min(cleanup), min(report),
                        msg="W4: Step 3 prints `- Cleanup: <line>`, so the cleanup must run BEFORE the report, "
                            "or a model follows the order and reports before it cleans up")

    # -- W3: the current folder's copy only in a linked worktree --------------------------------------
    def lookup_value(self, lookup: str, cwd) -> str:
        script = (f"cd '{posix_path(cwd)}'\n{lookup}\n"
                  "printf '@@VALUE@@%s' \"$( [ -n \"$CLN\" ] && { cygpath -m \"$CLN\" 2>/dev/null || printf %s \"$CLN\"; } )\"\n")
        home = Path(self.world_tmp) / "home"
        (home / ".claude").mkdir(parents=True, exist_ok=True)
        out = run_in_git_bash(script, cwd=cwd, env_extra={"HOME": posix_path(home), "USERPROFILE": str(home),
                                                         "CLAUDE_CONFIG_DIR": posix_path(Path(self.world_tmp) / "cfg")})
        return out.stdout.rsplit("@@VALUE@@", 1)[-1].strip() if "@@VALUE@@" in out.stdout else f"<no value: {out.stderr[-300:]}>"

    def make_tmp(self) -> Path:
        tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="skillblock_")))
        self.addCleanup(rmtree_force, tmp)
        self.world_tmp = str(tmp)
        return tmp

    def test_the_current_folders_copy_is_taken_in_a_linked_worktree_and_never_in_the_main_checkout(self):
        tmp = self.make_tmp()
        script_rel = Path(".claude") / "scripts" / "cleanup_delivered.py"
        main, linked = tmp / "main_checkout", tmp / "linked_worktree"
        (main / ".git").mkdir(parents=True)  # the main checkout's .git is a DIRECTORY
        linked.mkdir()
        (linked / ".git").write_text("gitdir: /elsewhere/.git/worktrees/linked\n", encoding="utf-8")  # a linked one's is a FILE
        for tree in (main, linked):
            (tree / script_rel).parent.mkdir(parents=True)
            (tree / script_rel).write_text("# stub\n", encoding="utf-8")

        for name in ("pr-merged", "advance"):
            lookup = "\n".join(takewhile(lambda l: not l.startswith('cd "$('), cln_block(name)))
            with self.subTest(skill=name):
                self.assertEqual(self.lookup_value(lookup, main), "",
                                 msg="W3: in the MAIN checkout the last-resort `$PWD/<script>` is never used: that copy "
                                     "may be stale (decision 2, INV-6), so CLN stays empty")
                self.assertEqual(os.path.normcase(os.path.realpath(self.lookup_value(lookup, linked))),
                                 os.path.normcase(os.path.realpath(str(linked / script_rel))),
                                 msg="in a linked worktree the current folder's own copy is the last resort")

    # -- F4: the command block is EXECUTED, not grepped ------------------------------------------------
    def test_the_step_6_block_of_each_skill_runs_the_script_from_the_main_root_with_from_set_to_the_starting_tree(self):
        for name in ("pr-merged", "advance"):
            tmp = self.make_tmp()
            plugin, main, tree, log = tmp / "plugin", tmp / "main_root", tmp / "session_tree", tmp / "stub_calls.jsonl"
            (plugin / ".claude" / "scripts").mkdir(parents=True)
            (plugin / ".claude" / "scripts" / "cleanup_delivered.py").write_text(STUB_SCRIPT, encoding="utf-8")
            main.mkdir()
            tree.mkdir()
            (tree / ".git").write_text("gitdir: /elsewhere/.git/worktrees/session\n", encoding="utf-8")
            block = "\n".join(cln_block(name)).replace("<slug>", SLUG).replace(" [--remove-remote]", "")

            with self.subTest(skill=name):
                out = run_in_git_bash(block, cwd=tree, env_extra={
                    "CLAUDE_PLUGIN_ROOT": posix_path(plugin), "STUB_LOG": posix_path(log),
                    "STUB_MAIN_ROOT": posix_path(main), "HOME": posix_path(tmp), "USERPROFILE": str(tmp)})
                self.assertTrue(log.is_file(), msg=f"the block never reached the script: rc={out.returncode} stderr={out.stderr[-400:]!r}")
                calls = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
                self.assertEqual(len(calls), 2, msg=f"the block makes exactly two script calls, got {calls}")
                first, second = calls
                self.assertEqual(first["argv"], ["--print-main-root"], msg="the first call asks for the main root")
                self.assertEqual(real(first["cwd"]), real(tree), msg="and runs from the session's own tree")
                self.assertEqual(real(second["cwd"]), real(main), msg="INV-6: the cleanup itself runs from the MAIN root, after the cd")
                argv = second["argv"]
                self.assertEqual(real(from_msys(argv[argv.index("--from") + 1])), real(tree),
                                 msg="INV-6: `--from` is the tree the session started in, captured BEFORE the cd; "
                                     "`--from \"$PWD\"` after the cd would name the main root and let the session's own "
                                     "tree be removed under it")
                self.assertEqual(argv[argv.index("--contract") + 1], SLUG, msg="the contract slug")
                self.assertIn("--json", argv, msg="--json")
                self.assertNotIn("--remove-remote", argv, msg="off unless the skill parameter was given")

    # -- pass-2 F1: the cleanup block must not move the session shell --------------------------------
    def test_the_cleanup_block_leaves_the_session_shell_in_its_own_folder_for_the_next_step(self):
        """Pass-2 F1. Step 3 of /advance runs `py -3 "$PRM" --status` AFTER the cleanup, with a script path and a
        `.claude/concepts` that are relative to the working directory. A bare `cd <main root>` in the block leaves
        the session in the main checkout for that call (and for the rest of the session). The `cd` belongs in a
        subshell, `( cd ... && py -3 ... )`."""
        for name in ("pr-merged", "advance"):
            tmp = self.make_tmp()
            plugin, main, tree, log = tmp / "plugin", tmp / "main_root", tmp / "session_tree", tmp / "stub_calls.jsonl"
            (plugin / ".claude" / "scripts").mkdir(parents=True)
            (plugin / ".claude" / "scripts" / "cleanup_delivered.py").write_text(STUB_SCRIPT, encoding="utf-8")
            main.mkdir()
            tree.mkdir()
            (tree / ".git").write_text("gitdir: /elsewhere/.git/worktrees/session\n", encoding="utf-8")
            block = "\n".join(cln_block(name)).replace("<slug>", SLUG).replace(" [--remove-remote]", "")
            script = block + "\nprintf '@@PWD@@%s@@' \"$(pwd -W 2>/dev/null || pwd)\"\npy -3 \"$CLN\" --the-next-step\n"

            with self.subTest(skill=name):
                out = run_in_git_bash(script, cwd=tree, env_extra={
                    "CLAUDE_PLUGIN_ROOT": posix_path(plugin), "STUB_LOG": posix_path(log),
                    "STUB_MAIN_ROOT": posix_path(main), "HOME": posix_path(tmp), "USERPROFILE": str(tmp)})
                m = re.search(r"@@PWD@@(.*?)@@", out.stdout)
                self.assertIsNotNone(m, msg=f"the block must run to its end, rc={out.returncode} stderr={out.stderr[-400:]!r}")
                self.assertEqual(real(from_msys(m.group(1))), real(tree),
                                 msg="F1: after the cleanup block the shell is still in the folder it started in")
                calls = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
                self.assertEqual(calls[-1]["argv"], ["--the-next-step"], msg="the next step's call came last")
                self.assertEqual(real(calls[-1]["cwd"]), real(tree),
                                 msg="F1: the call after the block (Step 3's --status in /advance) sees the START tree, "
                                     "not the main checkout")
                self.assertEqual(real(calls[-2]["cwd"]), real(main), msg="while the cleanup itself still ran from the main root")

    def test_ship_and_task_no_longer_tell_anyone_to_prune(self):
        for name in ("ship", "task"):
            text = read_skill(name)
            self.assertEqual([l for l in fenced_lines(text) if MANUAL_CLEANUP.match(l)], [],
                             msg=f"skills/{name}/SKILL.md: the manual worktree remove + prune lines are removed")
            self.assertNotRegex(text, r"then\s+`git worktree prune`",
                                msg=f"skills/{name}/SKILL.md: INV-5 forbids prune, so no line may recommend it")

    # -- HN-11: the conditional closing paragraph --------------------------------------------------------
    HN11_PLACES = (("flow", "Step 8"), ("advance", "Step 3"), ("task", "Status lifecycle"))

    def test_the_closing_paragraph_appears_exactly_once_in_flow_step_8_advance_step_3_and_task_status_lifecycle(self):
        for name, heading in self.HN11_PLACES:
            with self.subTest(skill=name, section=heading):
                body = section(read_skill(name), heading)

                self.assertTrue(body, msg=f"skills/{name}/SKILL.md has a `## {heading}` section")
                self.assertEqual(body.count(HN11_PARAGRAPH), 1,
                                 msg=f"HN-11: the pinned paragraph appears exactly once in skills/{name}/SKILL.md `## {heading}`")

    def test_the_closing_paragraph_is_not_in_task_step_6_the_hand_off_to_design_first(self):
        body = section(read_skill("task"), "Step 6")

        self.assertTrue(body, msg="skills/task/SKILL.md has a `## Step 6` section")
        self.assertNotIn("Once the pull request is merged and the work is delivered", body,
                         msg="HN-11: Step 6 is an automatic hand-off, not a report; the paragraph lives in `## Status lifecycle`")

    def test_each_section_tells_the_model_not_to_run_stop_and_lets_the_user_keep_working(self):
        for name, heading in self.HN11_PLACES:
            with self.subTest(skill=name):
                rest = section(read_skill(name), heading).replace(HN11_PARAGRAPH, "")

                self.assertRegex(rest, r"(?is)(must not|never|do not|does not|not)[^.\n]{0,80}/stop|/stop[^.\n]{0,80}(must not|never|do not|not)",
                                 msg=f"HN-11: skills/{name}/SKILL.md says in its own words that the model must not run /stop itself")
                self.assertIn(PRECEDENCE_SENTENCE, rest,
                              msg=f"HN-11: skills/{name}/SKILL.md carries the precedence sentence verbatim")

    def test_task_says_the_status_paragraph_ends_with_it_not_that_it_may(self):
        body = section(read_skill("task"), "Status lifecycle")

        self.assertNotIn("may end with this paragraph", body, msg="HN-11: a report that names `shipped` ends with the paragraph; `may end with` lets a model skip it")
        self.assertRegex(body, r"(?i)\bends with this paragraph\b", msg="HN-11: skills/task/SKILL.md says the report `ends with` the paragraph")

    def test_advance_prints_the_paragraph_only_when_the_cleanup_line_has_the_removed_form(self):
        body = section(read_skill("advance"), "Step 3").replace(HN11_PARAGRAPH, "")

        self.assertRegex(body, r"(?is)\bparagraph\b[^.]{0,250}\bonly\b[^.]{0,250}\bremoved\b|\bonly\b[^.]{0,250}\bremoved\b[^.]{0,250}\bparagraph\b|"
                         r"\bparagraph\b[^.]{0,250}\bremoved\b[^.]{0,250}\bonly\b",
                         msg="HN-11: /advance says the paragraph is printed only when the Cleanup line is the delivered `removed` form")

    @staticmethod
    def sentences(text: str) -> list:
        """(start offset, sentence) pairs; a sentence ends at . ! ? followed by a space or at a line break."""
        flat = text.replace(HN11_PARAGRAPH, "\x00" * len(HN11_PARAGRAPH))
        return [(m.start(), m.group(0)) for m in re.finditer(r"[^\n.!?]+(?:[.!?]+(?=\s|$))?", flat) if m.group(0).strip("\x00 \t")]

    def test_d1_advance_step_3_keeps_masters_bullet_order_and_places_the_paragraph_inside_the_block_before_next_command(self):
        body = section(read_skill("advance"), "Step 3")
        fence = re.search(r"```[^\n]*\n(### ADVANCE REPORT\n.*?)```", body, re.S)
        self.assertIsNotNone(fence, msg="fixture sanity: Step 3 has the report block that starts at `### ADVANCE REPORT`")
        block = fence.group(1)
        bullets = [m.group(1) for m in re.finditer(r"^- (Next command|Cleanup|Trees):", block, re.M)]

        self.assertEqual(bullets, ["Next command", "Cleanup", "Trees"],
                         msg="D1: the report block keeps master's order: `Next command:` before `Cleanup:` before `Trees:`")
        lines = block.splitlines()
        at = next(i for i, l in enumerate(lines) if l.startswith("- Next command:"))
        before = next((l for l in reversed(lines[:at]) if l.strip()), "")
        stripped = before.strip()
        self.assertTrue(stripped.startswith("<") and stripped.endswith(">") and "closing paragraph" in stripped,
                        msg=f"W2: the line directly before `- Next command:` is a `<...>` placeholder naming the closing paragraph, in the block's own style; got {before!r}")
        prose = body.replace(HN11_PARAGRAPH, "")
        self.assertRegex(prose, r"(?is)(directly|immediately) before[^.\n]{0,120}next command",
                         msg="D1: the section says the paragraph sits directly before the `Next command:` line")
        self.assertRegex(prose, r"(?is)\binside\b[^.\n]{0,80}\bblock\b|\bwithin\b[^.\n]{0,80}\bblock\b",
                         msg="D1: the section says the paragraph is printed inside the report block")
        for phrase in ("printed last", "After the report block", "the very last line"):
            self.assertNotIn(phrase.lower(), body.lower(), msg=f"D1: the old wording `{phrase}` is gone from Step 3")

    def test_b5_flow_says_the_paragraph_belongs_to_the_final_report_not_the_push_confirmation(self):
        body = section(read_skill("flow"), "Step 8")
        self.assertIn(HN11_PARAGRAPH, body, msg="fixture sanity: the pinned paragraph is in the section")
        at = body.index(HN11_PARAGRAPH)
        found = self.sentences(body)
        hits = []
        for i, (pos, sentence) in enumerate(found):
            if not (re.search(r"(?i)final report", sentence) and re.search(r"(?i)\bnot\b|n't|\bnever\b|\bnor\b", sentence)):
                continue
            around = " ".join(s for _p, s in found[max(0, i - 1):i + 2])
            if re.search(r"(?i)confirmation|confirm\b", around) and abs(pos - at) <= 1200:
                hits.append(sentence)

        self.assertTrue(hits, msg="B5: /flow Step 8 has a sentence with `final report` and a negation, next to a mention of the confirmation, "
                                  "within 1200 characters of the closing paragraph: the paragraph belongs to the final report, not to the push confirmation prompt")

    def test_the_old_unconditional_wording_is_nowhere_in_the_three_skills(self):
        for name in ("flow", "advance", "task"):
            with self.subTest(skill=name):
                self.assertNotIn("Delivered. End this session", read_skill(name),
                                 msg="HN-11: the old unconditional opening would tell the user a draft pull request is delivered")


# ===========================================================================
# [2] Remote branches
# ===========================================================================
class RemoteBranchTests(CleanupCase):
    def setUp(self) -> None:
        super().setUp()
        self.deliver(delete_remote=False)  # GitHub merged the records pull request and has NOT deleted the branches
        self.w.tools.clear_git_calls()

    def pushes(self) -> list:
        return [c["args"] for c in git_calls(self.w.tools) if sub_command(c["args"])[:1] == ["push"]]

    def test_off_by_default_the_remote_branches_are_listed_remote_kept_and_untouched(self):
        heads = remote_heads(self.w)

        proc, report = self.run_report(what="remove-remote off")

        self.assertIs(report.get("remove_remote"), False, msg="the report records that remove-remote was off")
        for branch in OWNED_BRANCHES:
            item = pick(report, "remote-branch", branch)
            self.assertIsNotNone(item, msg=f"INV-7: owned branch {branch} is still on origin, so it needs a remote-branch item")
            self.assertEqual((item["action"], item.get("reason")), ("left", "remote-kept"),
                             msg=f"INV-7: without --remove-remote {branch} is left with reason remote-kept")
        self.assertEqual(remote_heads(self.w), heads, msg="INV-7: without --remove-remote origin is not changed")
        self.assertEqual(self.pushes(), [], msg="INV-7: without --remove-remote no `git push` runs at all")
        for branch in OWNED_BRANCHES:
            self.assertNotIn(branch, local_branches(self.w), msg="the local merged branches are still deleted")

    def test_on_present_and_in_default_remote_branches_are_deleted_after_worktrees_and_local_branches(self):
        proc, report = self.run_report("--remove-remote", what="remove-remote on")

        self.assertIs(report.get("remove_remote"), True, msg="the report records that remove-remote was given")
        for branch in OWNED_BRANCHES:
            item = pick(report, "remote-branch", branch)
            self.assertIsNotNone(item, msg=f"a remote-branch item for {branch}")
            self.assertEqual(item["action"], "removed", msg=f"INV-7: {branch} is on origin and in origin/master, so it is deleted")
        self.assertEqual(sorted(set(remote_heads(self.w)) & set(OWNED_BRANCHES)), [], msg="the three remote branches are gone from origin")
        calls = [c["args"] for c in git_calls(self.w.tools)]
        index = lambda pred: [i for i, a in enumerate(calls) if pred(a)]  # noqa: E731
        removes = index(lambda a: sub_command(a)[:2] == ["worktree", "remove"])
        branch_deletes = index(lambda a: sub_command(a)[:1] == ["branch"] and "-D" in a)
        pushes = index(lambda a: sub_command(a)[:1] == ["push"])
        self.assertTrue(removes and branch_deletes and pushes, msg=f"positive control: all three kinds of mutation ran ({len(removes)}, {len(branch_deletes)}, {len(pushes)})")
        self.assertLess(max(removes), min(branch_deletes), msg="INV-9: worktrees first, then local branches")
        self.assertLess(max(branch_deletes), min(pushes), msg="INV-9: local branches before remote branches")
        for args in self.pushes():
            self.assertIn("--delete", args, msg=f"INV-7: the only push the script may run is `git push origin --delete <b>`, saw {args}")

    def test_the_remote_delete_carries_a_lease_on_the_tip_the_ancestor_check_used(self):
        """W8: ls-remote, the ancestor check and the push are three steps; a push to the branch in between must
        make the delete fail, so the push leases exactly the tip that was checked."""
        w = self.w
        tips = {b: git(w.main, "ls-remote", "origin", f"refs/heads/{b}").split()[0] for b in OWNED_BRANCHES}

        proc, report = self.run_report("--remove-remote", what="remote delete with a lease")

        calls = [c["args"] for c in git_calls(w.tools)]
        for branch in OWNED_BRANCHES:
            lease = f"--force-with-lease=refs/heads/{branch}:{tips[branch]}"
            pushes = [i for i, a in enumerate(calls) if sub_command(a)[:1] == ["push"] and "--delete" in a and branch in a]
            self.assertEqual(len(pushes), 1, msg=f"one delete push for {branch}, got {[calls[i] for i in pushes]}")
            self.assertIn(lease, calls[pushes[0]], msg=f"W8: the delete of {branch} must lease the checked tip, saw {calls[pushes[0]]}")
            checks = [i for i, a in enumerate(calls) if "merge-base" in a and "--is-ancestor" in a and tips[branch] in a
                      and i < pushes[0]]
            self.assertTrue(checks, msg=f"W8: the sha leased for {branch} is the one the ancestor check ran on")
        self.assertEqual(sorted(set(remote_heads(w)) & set(OWNED_BRANCHES)), [], msg="and the deletes still succeed")

    def test_ls_remote_failing_keeps_every_remote_branch_unverifiable(self):
        set_git_fail(self.w.tools, ["ls-remote"])

        proc, report = self.run_report("--remove-remote", what="ls-remote fails")

        for branch in OWNED_BRANCHES:
            item = pick(report, "remote-branch", branch)
            self.assertEqual((item["action"], item.get("reason")), ("left", "unverifiable"),
                             msg=f"INV-7: when ls-remote cannot answer, {branch} is kept as unverifiable")
        self.assertEqual(self.pushes(), [], msg="no push without a fresh ls-remote")

    def test_a_branch_github_already_deleted_reads_already_gone_and_no_push_names_it(self):
        remote_delete(self.w, FEATURE)

        proc, report = self.run_report("--remove-remote", what="already deleted by GitHub")

        item = pick(report, "remote-branch", FEATURE)  # F10: INV-7 names the reading, so the item is required
        self.assertEqual(item["action"], "already-gone", msg="INV-7: a branch GitHub already deleted reads already-gone")
        self.assertEqual([a for a in self.pushes() if FEATURE in a], [],
                         msg="INV-7: no push may name a branch that a fresh ls-remote no longer lists")
        self.assertEqual(pick(report, "remote-branch", TASK_BRANCH)["action"], "removed",
                         msg="control: the other remote branches are still deleted")

    def test_a_remote_branch_whose_tip_is_not_in_origin_master_is_kept_not_in_default(self):
        w = self.w
        git(w.ghub, "switch", "-q", "-c", "late", f"origin/{FEATURE}")
        late = commit(w.ghub, {"src/late.txt": "late\n"}, "work pushed after the merge")
        git(w.ghub, "push", "-q", "origin", f"late:{FEATURE}")
        git(w.ghub, "switch", "-q", "master")

        proc, report = self.run_report("--remove-remote", what="remote not in default")

        item = pick(report, "remote-branch", FEATURE)
        self.assertEqual((item["action"], item.get("reason")), ("left", "not-in-default"),
                         msg="INV-7: a remote tip that is not an ancestor of origin/master is kept, not-in-default")
        self.assertEqual(git(w.main, "ls-remote", "origin", f"refs/heads/{FEATURE}").split()[0], late,
                         msg="INV-7: the remote branch still points at the late commit")

    def test_a_remote_branch_with_an_open_pull_request_is_kept_open_pull_request(self):
        self.w.tools.set_gh(open_prs=[{"headRefName": TASK_BRANCH, "url": "https://github.com/acme/app/pull/70",
                                       "baseRefName": "master"}])

        proc, report = self.run_report("--remove-remote", what="open pull request")

        item = pick(report, "remote-branch", TASK_BRANCH)
        self.assertEqual((item["action"], item.get("reason")), ("left", "open-pull-request"),
                         msg="INV-7: `gh pr list --head <b> --state open` reports one, so the branch is kept")
        self.assertIn(TASK_BRANCH, remote_heads(self.w), msg="the branch is still on origin")
        self.assertEqual(pick(report, "remote-branch", FEATURE)["action"], "removed", msg="control: a branch with no open pull request is deleted")

    def test_gh_unavailable_for_the_open_pull_request_check_keeps_every_remote_branch_unverifiable(self):
        self.w.tools.set_gh(fail_commands=["pr list --head", "pr list --state open --head"])

        proc, report = self.run_report("--remove-remote", what="gh unavailable")

        for branch in OWNED_BRANCHES:
            item = pick(report, "remote-branch", branch)
            self.assertEqual((item["action"], item.get("reason")), ("left", "unverifiable"),
                             msg=f"INV-7: when gh cannot answer, {branch} is kept as unverifiable, never deleted")
        self.assertEqual(sorted(set(remote_heads(self.w)) & set(OWNED_BRANCHES)), sorted(OWNED_BRANCHES),
                         msg="all three remote branches are still on origin")
        self.assertEqual(self.pushes(), [], msg="no push when the open pull request check could not be made")


# ===========================================================================
# [3] Directory links
# ===========================================================================
class DirectoryLinkTests(CleanupCase):
    def setUp(self) -> None:
        super().setUp()
        self.target = self.tmp / "shared_node_modules"
        self.deep_target = self.tmp / "shared_deep_modules"
        self.link = self.make_link(self.w.fw, "node_modules", self.target)
        self.deep = self.make_link(self.w.fw / "src" / "deep", "node_modules", self.deep_target)
        self.deliver()

    def test_fixture_sanity_the_links_are_real_links_and_the_tree_is_clean_to_git(self):
        self.assertTrue(is_link_entry(self.link) and is_link_entry(self.deep), msg="fixture: both are links")
        self.assertEqual(git(self.w.fw, "status", "--porcelain"), "", msg="fixture: ignored links leave the tree clean")

    def test_every_link_is_removed_alone_and_first_and_the_targets_survive(self):
        proc, report = self.run_report(what="worktree with links")

        item = pick(report, "worktree", FW_NAME)
        self.assertEqual(item["action"], "removed", msg="the clean, delivered worktree is removed")
        self.assertGone(self.w.fw, "link worktree")
        self.assertTargetSurvived(self.target, "top-level node_modules link")
        self.assertTargetSurvived(self.deep_target, "link deep in the tree")
        links = item.get("links") or []
        self.assertGreaterEqual(len(links), 2, msg="the report lists each Directory Link found")
        self.assertTrue(all(l.get("removed") is True for l in links), msg=f"each listed link was removed, got {links}")
        remove_calls = [c for c in git_calls(self.w.tools) if sub_command(c["args"])[:2] == ["worktree", "remove"]
                        and FW_NAME in c["args"][-1].replace("\\", "/")]
        self.assertEqual(len(remove_calls), 1, msg="one `git worktree remove` for the feature worktree")
        self.assertNotIn("node_modules", remove_calls[0].get("children") or [],
                         msg="INV-4: when `git worktree remove` ran, the node_modules link entry was already gone")
        self.assertEqual(remove_calls[0].get("links"), [],
                         msg="INV-4 (F11): a recursive scan at the moment of `git worktree remove` finds NO link "
                             "anywhere in the tree, deep ones included, so git can never follow one")

    def test_a_dirty_worktree_is_left_with_its_links_in_place(self):
        (self.w.fw / "notes.txt").write_text("unsaved\n", encoding="utf-8")

        proc, report = self.run_report(what="dirty worktree with links")

        self.assertEqual(pick(report, "worktree", FW_NAME)["action"], "left", msg="a dirty worktree is left")
        self.assertTrue(is_link_entry(self.link) and is_link_entry(self.deep),
                        msg="INV-4: links go last-moment, so a worktree that is kept still has its links")
        self.assertTargetSurvived(self.target, "kept worktree")

    def test_a_deferred_standing_tree_keeps_its_links(self):
        proc, report = self.run_report(env_extra={"CLAUDE_PROJECT_DIR": str(self.w.fw)}, what="standing tree with links")

        self.assertEqual(pick(report, "worktree", FW_NAME)["action"], "deferred", msg="the standing tree is deferred")
        self.assertTrue(is_link_entry(self.link) and is_link_entry(self.deep),
                        msg="INV-4/INV-6: a deferred tree is left entirely untouched, links included")

    def test_when_git_worktree_remove_fails_the_removed_links_are_listed_with_their_targets(self):
        set_git_fail(self.w.tools, ["worktree", "remove", FW_NAME])

        proc, report = self.run_report(what="remove fails after the links")

        item = pick(report, "worktree", FW_NAME)
        self.assertEqual((item["action"], item.get("reason")), ("left", "remove-failed"),
                         msg="INV-4: a failed `git worktree remove` is remove-failed")
        text = json.dumps(item.get("detail")).replace("\\\\", "/").replace("\\", "/").lower()
        for target in (self.target, self.deep_target):
            self.assertIn(str(target).replace("\\", "/").lower(), text,
                          msg="INV-4: detail lists each removed link with its target so it can be recreated")
        self.assertKept(self.w.fw, "remove-failed (F7)")
        self.assertEqual((self.w.fw / "src" / "feature.txt").read_text(encoding="utf-8"), "feature\n",
                         msg="F7: a failed removal must not fall back to deleting the files some other way")
        self.assertTargetSurvived(self.target, "remove-failed")

    def test_a_link_that_cannot_be_removed_leaves_the_worktree_link_not_removed(self):
        real_rmdir, real_unlink, real_remove = os.rmdir, os.unlink, os.remove

        def refusing(real_fn):
            def fn(path, *a, **k):
                if os.path.basename(str(path).rstrip("\\/")) == "node_modules":
                    raise PermissionError(13, "removing the link is refused on purpose")
                return real_fn(path, *a, **k)
            return fn

        rc, out, report = self.run_in_process([], patches={"os.rmdir": refusing(real_rmdir), "os.unlink": refusing(real_unlink),
                                                          "os.remove": refusing(real_remove)})

        self.assertIsInstance(report, dict, msg=f"the in-process run must print a report, got {out[:300]!r}")
        item = pick(report, "worktree", FW_NAME)
        self.assertEqual((item["action"], item.get("reason")), ("left", "link-not-removed"),
                         msg="INV-4: a link that cannot be removed leaves the worktree link-not-removed")
        self.assertKept(self.w.fw, "link-not-removed")
        self.assertTargetSurvived(self.target, "link-not-removed")
        self.assertEqual(pick(report, "worktree", TW_NAME)["action"], "removed",
                         msg="INV-9: one item's failure is recorded and the run goes on to the next item")

    def test_a_relative_symlink_target_is_resolved_from_the_links_own_folder(self):
        """W6: `os.readlink` returns a RELATIVE target for a relative symlink; it is relative to the link's folder,
        not to the process cwd (the main root), so a survival check on it must join the two."""
        target = self.tmp / "shared_rel_modules"
        parent = self.w.fw / "src" / "deep2"
        (target / "pkg").mkdir(parents=True)
        (target / "pkg" / "index.js").write_text("module.exports = 1;\n", encoding="utf-8")
        parent.mkdir(parents=True)
        try:
            os.symlink(os.path.relpath(str(target), str(parent)), str(parent / "node_modules"), target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"a relative symlink cannot be created on this host without a privilege: {exc}")

        proc, report = self.run_report(what="relative symlink")

        item = pick(report, "worktree", FW_NAME)
        entry = [l for l in item.get("links") or [] if l.get("path", "").endswith("src/deep2/node_modules")]
        self.assertEqual(len(entry), 1, msg=f"the relative symlink is listed among the links, got {item.get('links')}")
        self.assertIs(entry[0].get("target_survived"), True,
                      msg="W6: the target exists, resolved from the link's own folder; resolved from the main root it "
                          "would read as vanished")
        self.assertEqual(item["action"], "removed", msg="and the run goes on as usual")
        self.assertTargetSurvived(target, "relative symlink")

    def test_a_link_whose_target_vanished_is_reported_and_stops_all_further_removal(self):
        """W6: a target that is gone is reported (reason remove-failed, the target named in detail) and, like a
        halted probe, nothing else is removed afterwards."""
        gone = self.tmp / "vanished_modules"
        self.make_link(self.w.fw / "src" / "gone", "node_modules", gone)
        rmtree_force(gone)
        branches = local_branches(self.w)

        proc, report = self.run_report(what="link with a vanished target")

        item = pick(report, "worktree", FW_NAME)
        self.assertEqual((item["action"], item.get("reason")), ("left", "remove-failed"),
                         msg="W6: the feature worktree is not removed while one of its links lost its target")
        self.assertIn("vanished_modules", json.dumps(item.get("detail")),
                      msg="W6: the report names the target that is gone")
        self.assertKept(self.w.fw, "worktree with a vanished link target")
        self.assertKept(self.w.tw, "W6: nothing else is removed after it (the sub-task worktree sorts after the feature one)")
        self.assertEqual(local_branches(self.w), branches, msg="W6: and no branch is deleted either")
        self.assertEqual((proc.rc, report.get("outcome")), (3, "partial"), msg="partial, exit 3")

    def test_a_dangling_link_inside_an_ignored_folder_does_not_halt_the_run(self):
        """Pass-2 F4. Dangling links are ordinary inside `.venv/` or a real `node_modules/`; one of them was always
        dangling and is no evidence that this run took a target away. INV-9 has ONE halt rule, and this is not it:
        the rest of the work item is still cleaned (the vanished-target case of the previous test stays a halt)."""
        gone = self.tmp / "vanished_venv_target"
        self.make_link(self.w.fw / ".venv" / "lib", "dangling", gone)
        rmtree_force(gone)

        proc, report = self.run_report(what="dangling link inside .venv")

        self.assertGone(self.w.tw, "F4: the sub-task worktree (sorted after the feature one) is still removed")
        self.assertNotIn(RECORDS_BRANCH, local_branches(self.w), msg="F4: and the local branch steps still run")
        self.assertEqual(pick(report, "worktree", TW_NAME)["action"], "removed", msg="reported as removed")

    def test_dry_run_leaves_links_trees_and_branches_alone(self):
        before, main_before = state(self.w), snapshot(self.w.main)

        proc, report = self.run_report("--dry-run", what="dry run")

        self.assertIs(report.get("dry_run"), True, msg="the report records the dry run")
        self.assertTrue(report.get("items"), msg="a dry run still reports what it would do")
        self.assertEqual(state(self.w), before, msg="--dry-run changes no worktree, branch, remote branch or file")
        self.assertEqual(snapshot(self.w.main), main_before, msg="--dry-run leaves the main checkout identical")
        self.assertTrue(is_link_entry(self.link), msg="--dry-run does not remove a link")
        self.assertEqual(mutating_calls(self.w.tools), [], msg="--dry-run runs no mutating git command")


class LinkDetectionSourceTests(unittest.TestCase):
    """INV-4: detection works on every supported Python, so it must not lean on what 3.12 added or what 3.11 lacks."""

    def test_detection_uses_lstat_and_the_reparse_flag_and_never_dir_entry_follow_symlinks_false(self):
        self.assertTrue(CLEANUP.is_file(), msg=MISSING)
        tokens = code_tokens(CLEANUP.read_text(encoding="utf-8"))
        names = {v for k, v in tokens if k == "name"}  # F14: code only, so a comment cannot satisfy these
        code = " ".join(v for _k, v in tokens)
        text = CLEANUP.read_text(encoding="utf-8")

        self.assertIn("FILE_ATTRIBUTE_REPARSE_POINT", names, msg="INV-4: on Windows a link is an entry with the reparse-point attribute")
        self.assertIn("lstat", names, msg="INV-4: each entry is tested with os.lstat")
        self.assertNotIn("isjunction", code, msg="INV-4: os.path.isjunction does not exist before Python 3.12")
        self.assertIsNone(re.search(r"is_dir\s*\(\s*follow_symlinks", text),
                          msg="INV-4: before 3.12 DirEntry.is_dir(follow_symlinks=False) reports a junction as a directory")

    def test_the_control_this_scan_can_see_what_it_forbids(self):
        planted = "import os\nx = os.path.isjunction(p)\ny = entry.is_dir(follow_symlinks=False)\n"
        self.assertIn("isjunction", " ".join(v for _k, v in code_tokens(planted)), msg="control: the token stream sees isjunction")
        self.assertIsNotNone(re.search(r"is_dir\s*\(\s*follow_symlinks", planted), msg="control: the regex sees the forbidden call")


# ===========================================================================
# [4] Dirty, unpushed and nested trees
# ===========================================================================
class UnsafeTreeTests(CleanupCase):
    def setUp(self) -> None:
        super().setUp()
        self.deliver()

    def test_a_worktree_with_a_modified_tracked_file_is_left_and_the_report_names_the_file(self):
        (self.w.fw / "src" / "feature.txt").write_text("edited and not committed\n", encoding="utf-8")

        proc, report = self.run_report(what="modified tracked file")

        item = pick(report, "worktree", FW_NAME)
        self.assertEqual((item["action"], item.get("reason")), ("left", "uncommitted-changes"),
                         msg="INV-3: git status --porcelain is not empty, so the worktree is left")
        self.assertIn("src/feature.txt", [f.replace("\\", "/") for f in item.get("files") or []],
                      msg="the item names the file that keeps the worktree")
        self.assertIn("src/feature.txt", report.get("line", ""), msg="criterion 4: the PRINTED line names the file")
        self.assertEqual((self.w.fw / "src" / "feature.txt").read_text(encoding="utf-8"), "edited and not committed\n",
                         msg="the edit is intact")
        self.assertKept(self.w.fw, "dirty worktree")
        self.assertEqual((proc.rc, report.get("outcome")), (3, "partial"), msg="something was left, so the outcome is partial, exit 3")
        for path in (self.w.tw, self.w.aw):
            self.assertGone(path, "the other owned worktrees are still cleaned")

    def test_an_untracked_file_also_keeps_the_worktree_and_is_named(self):
        (self.w.tw / "scratch-notes.txt").write_text("keep me\n", encoding="utf-8")

        proc, report = self.run_report(what="untracked file")

        item = pick(report, "worktree", TW_NAME)
        self.assertEqual((item["action"], item.get("reason")), ("left", "uncommitted-changes"), msg="an untracked file is uncommitted work")
        self.assertIn("scratch-notes.txt", [f.replace("\\", "/") for f in item.get("files") or []], msg="the file is named")
        self.assertIn("scratch-notes.txt", report.get("line", ""), msg="and it appears in the printed line")

    def test_a_worktree_with_an_unpushed_commit_is_left_and_the_changed_file_is_named(self):
        commit(self.w.fw, {"src/extra.txt": "never merged\n"}, "a commit origin/master does not have")

        proc, report = self.run_report(what="unpushed commit")

        item = pick(report, "worktree", FW_NAME)
        self.assertEqual((item["action"], item.get("reason")), ("left", "unpushed-commits"),
                         msg="INV-3: HEAD is not an ancestor of origin/master")
        self.assertIn("src/extra.txt", [f.replace("\\", "/") for f in item.get("files") or []], msg="the changed file is named")
        self.assertIn("src/extra.txt", report.get("line", ""), msg="criterion 4: the printed line names it")
        self.assertKept(self.w.fw, "unpushed commit")
        self.assertTrue((self.w.fw / "src" / "extra.txt").is_file(), msg="the unpushed work is intact")

    def test_an_ignored_folder_that_is_itself_a_git_worktree_reads_nested_worktree(self):
        nested = self.w.fw / ".claude" / "worktrees" / "inner"
        add_worktree(self.w.main, nested, "-b", "inner-work", "master")
        (nested / "unsaved.txt").write_text("the nested tree's own unsaved work\n", encoding="utf-8")

        proc, report = self.run_report(what="nested worktree")

        item = pick(report, "worktree", FW_NAME)
        self.assertEqual((item["action"], item.get("reason")), ("left", "nested-worktree"),
                         msg="INV-3: an ignored folder holding a .git entry is a nested worktree; `git worktree remove` would delete it")
        self.assertTrue(any("inner" in f.replace("\\", "/") for f in item.get("files") or []), msg="its path is named")
        self.assertEqual((nested / "unsaved.txt").read_text(encoding="utf-8"), "the nested tree's own unsaved work\n",
                         msg="the nested worktree's unsaved work is intact")
        self.assertKept(self.w.fw, "nested worktree")


# ===========================================================================
# [5] and [6] Branches
# ===========================================================================
class LocalBranchTests(CleanupCase):
    def setUp(self) -> None:
        super().setUp()
        self.deliver()

    def test_a_branch_whose_tip_is_not_in_origin_master_is_kept_and_the_report_says_why(self):
        sha = commit_off_master(self.w, RECORDS_BRANCH)
        self.w.tools.clear_git_calls()

        proc, report = self.run_report(what="branch not in default")

        item = pick(report, "local-branch", RECORDS_BRANCH)
        self.assertEqual((item["action"], item.get("reason")), ("left", "not-in-default"),
                         msg="INV-3: the tip is not an ancestor of origin/master, so the branch is kept")
        self.assertEqual(local_branches(self.w).get(RECORDS_BRANCH), sha, msg="the branch is untouched")
        self.assertIn("not-in-default", report.get("line", ""), msg="criterion 5: the printed line says why")
        deletes = [c["args"] for c in git_calls(self.w.tools) if sub_command(c["args"])[:1] == ["branch"] and RECORDS_BRANCH in c["args"]
                   and any(f in c["args"] for f in ("-d", "-D", "--delete"))]
        self.assertEqual(deletes, [], msg="`git branch -D` is used only after the ancestor check passes, never otherwise")

    def test_a_merged_branch_is_deleted_with_capital_d_only_after_an_ancestor_check_while_the_main_checkout_sits_elsewhere(self):
        self.assertEqual(git(self.w.main, "rev-parse", "--abbrev-ref", "HEAD"), "main-side", msg="fixture: main is on another branch")
        tips = local_branches(self.w)
        self.w.tools.clear_git_calls()

        proc, report = self.run_report(what="merged branches")

        calls = [c["args"] for c in git_calls(self.w.tools)]
        for branch in OWNED_BRANCHES:
            tip = tips[branch]
            self.assertNotIn(branch, local_branches(self.w), msg=f"{branch} is deleted even though `git branch -d` would refuse it")
            deletes = [i for i, a in enumerate(calls) if sub_command(a)[:1] == ["branch"] and branch in a
                       and any(f in a for f in ("-d", "-D", "--delete"))]
            self.assertTrue(deletes, msg=f"positive control: a `git branch` deletion naming {branch}")
            self.assertIn("-D", calls[deletes[0]], msg=f"criterion 6: the deletion of {branch} is `git branch -D`, saw {calls[deletes[0]]}")
            checks = [i for i, a in enumerate(calls) if "merge-base" in a and "--is-ancestor" in a
                      and any("origin/master" in x for x in a) and tip in a and i < deletes[0]]
            self.assertTrue(checks, msg=f"INV-3 (F15): `git merge-base --is-ancestor {tip[:10]} origin/master` ran on THIS "
                                        f"branch's tip BEFORE the -D of {branch}, not on some other tree's head")
        self.assertEqual(git(self.w.main, "rev-parse", "--abbrev-ref", "HEAD"), "main-side", msg="no switch: the main checkout is where it was")

    def test_an_owned_branch_held_by_the_main_checkout_reads_checked_out(self):
        git(self.w.main, "switch", "-q", RECORDS_BRANCH)

        proc, report = self.run_report(what="branch held by the main checkout")

        item = pick(report, "local-branch", RECORDS_BRANCH)
        self.assertEqual((item["action"], item.get("reason")), ("left", "checked-out"), msg="INV-3/INV-5: the main checkout holds it")
        self.assertEqual(git(self.w.main, "rev-parse", "--abbrev-ref", "HEAD"), RECORDS_BRANCH,
                         msg="INV-5: the script never switches or checks out in the main checkout")

    def test_a_branch_held_by_a_kept_worktree_reads_checked_out(self):
        (self.w.tw / "wip.txt").write_text("keeps the tree\n", encoding="utf-8")

        proc, report = self.run_report(what="branch held by a kept worktree")

        self.assertEqual(pick(report, "worktree", TW_NAME)["action"], "left", msg="fixture: the dirty worktree is kept")
        item = pick(report, "local-branch", TASK_BRANCH)
        self.assertEqual((item["action"], item.get("reason")), ("left", "checked-out"),
                         msg="the branch a kept worktree holds cannot be deleted: checked-out")
        self.assertIn(TASK_BRANCH, local_branches(self.w), msg="the branch is still there")


class ProtectedNameTests(CleanupCase):
    def test_a_brief_naming_the_default_branch_does_not_get_it_deleted_protected_name(self):
        self.rebuild(brief_branch="master")
        merge_records(self.w)
        sha = local_branches(self.w)["master"]

        proc, report = self.run_report(what="brief branch is master")

        item = pick(report, "local-branch", "master")
        self.assertIsNotNone(item, msg="INV-2: the brief's branch is in the Owned set, so it has an item")
        self.assertEqual((item["action"], item.get("reason")), ("left", "protected-name"),
                         msg="INV-2: never the default branch, master or main")
        self.assertEqual(local_branches(self.w).get("master"), sha, msg="master is untouched")

    def test_a_linked_worktree_that_holds_a_protected_branch_is_not_removed_either(self):
        """W7: INV-2 says never the default branch, also at the worktree stage, not only for the branch itself."""
        self.rebuild(brief_branch="master")
        merge_records(self.w)
        holder = self.w.main / WT_DIR / "20261015-holds-master"
        add_worktree(self.w.main, holder, "master")  # clean, at an ancestor of origin/master: removable if it were owned

        proc, report = self.run_report(what="worktree holding master")

        self.assertKept(holder, "a worktree holding master")
        self.assertNotEqual((pick(report, "worktree", holder.name, required=False) or {}).get("action"), "removed",
                            msg="W7: a brief that names master must not get a linked worktree holding it removed")
        self.assertIn("master", local_branches(self.w), msg="and master itself stays")

    def test_a_linked_worktree_that_holds_main_is_not_removed_either(self):
        self.rebuild(brief_branch="main")
        merge_records(self.w)
        holder = self.w.main / WT_DIR / "20261015-holds-main"
        add_worktree(self.w.main, holder, "main")

        proc, report = self.run_report(what="worktree holding main")

        self.assertKept(holder, "a worktree holding main")
        self.assertIn("main", local_branches(self.w), msg="the branch `main` stays")

    def test_a_brief_naming_main_is_protected_too(self):
        self.rebuild(brief_branch="main")
        merge_records(self.w)

        proc, report = self.run_report(what="brief branch is main")

        item = pick(report, "local-branch", "main")
        self.assertIsNotNone(item, msg="the brief's branch has an item")
        self.assertEqual((item["action"], item.get("reason")), ("left", "protected-name"), msg="INV-2: `main` is protected as well")
        self.assertIn("main", local_branches(self.w), msg="the branch `main` still exists")


# ===========================================================================
# [7] Ownership
# ===========================================================================
class OwnershipTests(CleanupCase):
    def setUp(self) -> None:
        super().setUp()
        self.deliver()

    def test_a_sibling_items_worktrees_and_branches_survive_even_when_they_look_removable(self):
        w = self.w
        sibling_task = w.main / WT_DIR / "20261015-task-t1-cleanup-2"
        sibling_adv = w.main / WT_DIR / f"20261015-advance-{OTHER_SLUG}"
        add_worktree(w.main, sibling_task, "-b", "task/2026-10-15-sibling/t1-cleanup", "master")
        add_worktree(w.main, sibling_adv, "--detach", "master")
        git(w.main, "branch", "feature/other-item", "master")
        git(w.main, "branch", f"docs/{OTHER_SLUG}-records", "master")

        proc, report = self.run_report(what="sibling item present")

        self.assertKept(sibling_task, "sibling's task worktree (clean, in origin/master, task-id-like folder name)")
        self.assertKept(sibling_adv, "sibling contract's advance worktree")
        for branch in ("task/2026-10-15-sibling/t1-cleanup", "feature/other-item", f"docs/{OTHER_SLUG}-records"):
            self.assertIn(branch, local_branches(w), msg=f"INV-2: {branch} is outside the Owned set and is never touched")
        examined = [item_id(i) for i in report.get("items", [])]
        foreign = {"20261015-task-t1-cleanup-2", f"20261015-advance-{OTHER_SLUG}", "task/2026-10-15-sibling/t1-cleanup",
                   "feature/other-item", f"docs/{OTHER_SLUG}-records"}
        self.assertEqual([i for i in examined if i.rstrip("/").rsplit("/", 1)[-1] in foreign or i in foreign], [],
                         msg=f"INV-2: anything outside the Owned set is never examined; the report lists {examined}")
        self.assertGone(w.tw, "control: this item's own sub-task worktree IS removed")

    def test_a_shorter_advance_name_that_fits_two_contracts_is_never_removed(self):
        """Was 'reads ambiguous-name'. Lead decision (W2): a name matches a slug by prefix ONLY when the folder name
        was cut at the 60-character limit, and this one (32 characters) was not, so it is simply not ours: the run
        keeps it. Either no item or a non-removed item is acceptable; `ambiguous-name` stays in the reason set for
        names that really were cut."""
        w = self.w
        shared = w.main / WT_DIR / "20261015-advance-2026-10-15-demo"
        add_worktree(w.main, shared, "--detach", "master")

        proc, report = self.run_report(what="short advance name that fits two slugs")

        item = pick(report, "worktree", "20261015-advance-2026-10-15-demo", required=False)
        self.assertNotEqual((item or {}).get("action"), "removed", msg="INV-2: a name that is not provably ours is never removed")
        self.assertKept(shared, "short advance worktree")
        self.assertGone(w.aw, "control: the advance worktree named with the full slug is removed")

    def test_an_in_flight_sibling_whose_slug_is_a_prefix_of_ours_keeps_its_advance_worktree(self):
        """W2/F2: sibling contract `2026-10-15-demo` exists only on its own branch, NOT at origin/master, so the
        ambiguity guard cannot see it. Its advance worktree is detached, clean and merged, so only the exact-match
        rule protects it."""
        self.rebuild(other_contract=False)
        merge_records(self.w)
        w = self.w
        git(w.ghub, "switch", "-q", "-c", "feature/demo-sibling")
        commit(w.ghub, {".claude/concepts/2026-10-15-demo.md": "# Contract: sibling\n\n**Status:** approved\n"}, "sibling contract")
        git(w.ghub, "push", "-q", "origin", "feature/demo-sibling")
        git(w.ghub, "switch", "-q", "master")
        sibling_adv = w.main / WT_DIR / "20261015-advance-2026-10-15-demo"
        add_worktree(w.main, sibling_adv, "--detach", "master")
        self.assertNotIn("2026-10-15-demo.md", git(w.main, "ls-tree", "--name-only", "origin/master:.claude/concepts/"),
                         msg="fixture sanity: the sibling contract is NOT on origin/master")

        proc, report = self.run_report(what="in-flight prefix sibling")

        self.assertKept(sibling_adv, "the in-flight sibling's advance worktree (slug is a prefix of ours)")
        self.assertNotEqual((pick(report, "worktree", sibling_adv.name, required=False) or {}).get("action"), "removed",
                            msg="W2: `foo-bar` must not claim `...-advance-foo` when the name was not cut at the limit")
        self.assertGone(w.aw, "control: the advance worktree named with the full slug is still removed")

    def test_a_cut_advance_name_that_equals_an_in_flight_siblings_full_name_is_kept_as_ambiguous(self):
        """Pass-2 F3. This slug is longer than 43 characters, so its advance folder name is cut at the 60-character
        limit, and the cut equals the FULL name of the shorter sibling slug (whose contract is only on its branch)."""
        long_slug = "2026-10-15-auto-cleanup-delivered-worktrees-v2"
        sibling_slug = "2026-10-15-auto-cleanup-delivered-worktrees"
        patcher = mock.patch.multiple(
            sys.modules[__name__], SLUG=long_slug, CONTRACT_REL=f".claude/concepts/{long_slug}.md",
            RESULTS_REL=f".claude/orchestrator/results/{long_slug}", TASK_BRANCH=f"task/{long_slug}/t1-cleanup",
            RECORDS_BRANCH=f"docs/{long_slug}-records", AW_NAME=f"20261015-advance-{sibling_slug}",
            OWNED_BRANCHES=(FEATURE, f"task/{long_slug}/t1-cleanup", f"docs/{long_slug}-records"))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.rebuild()
        merge_records(self.w)
        w = self.w
        git(w.ghub, "switch", "-q", "-c", "feature/sibling-v1")
        commit(w.ghub, {f".claude/concepts/{sibling_slug}.md": "# Contract: sibling\n\n**Status:** approved\n"}, "sibling contract")
        git(w.ghub, "push", "-q", "origin", "feature/sibling-v1")
        git(w.ghub, "switch", "-q", "master")
        self.assertEqual(len(w.aw.name), 60, msg="fixture sanity: the folder name is exactly at the 60-character limit")

        proc, report = self.run_report(contract=long_slug, what="cut advance name")

        item = pick(report, "worktree", w.aw.name)
        self.assertEqual((item["action"], item.get("reason")), ("left", "ambiguous-name"),
                         msg="F3: a name at the 60-character limit may be a cut of a longer slug OR a whole shorter one; "
                             "it is never provably ours, so it is kept")
        self.assertKept(w.aw, "the cut-name advance worktree")
        self.assertGone(w.fw, "control: the feature worktree is still removed")

    def test_when_the_other_contracts_cannot_be_listed_every_advance_name_is_kept(self):
        """Pass-2 F3: `other_slugs` returning [] on a git failure turns the ambiguity check off (fail open)."""
        set_git_fail(self.w.tools, ["ls-tree", "concepts"])  # only the listing of .claude/concepts; the records read is untouched

        proc, report = self.run_report(what="other contracts unreadable")

        item = pick(report, "worktree", AW_NAME)
        self.assertEqual(item["action"], "left", msg="F3: the advance worktree is kept when the siblings cannot be read")
        self.assertIn(item.get("reason"), ("unverifiable", "ambiguous-name"),
                      msg="with a reason from the closed set that says it could not be checked")
        self.assertKept(self.w.aw, "advance worktree with unreadable siblings")

    def test_a_worktree_outside_the_worktrees_folder_that_holds_an_owned_branch_is_kept(self):
        """W11: removal is limited to worktrees directly inside <main root>/.claude/worktrees/ (flat_worktree.is_flat)."""
        outside = self.tmp / "outside_wt"
        add_worktree(self.w.main, outside, RECORDS_BRANCH)  # clean, merged, unlocked: only its PLACE can keep it

        proc, report = self.run_report(what="worktree outside the worktrees folder")

        item = pick(report, "worktree", "outside_wt")
        self.assertEqual((item["action"], item.get("reason")), ("left", "outside-worktrees-folder"),
                         msg="W11: a registered worktree anywhere else is kept with the new reason")
        self.assertKept(outside, "outside worktree")
        self.assertIn(RECORDS_BRANCH, local_branches(self.w), msg="the branch it holds stays (it is checked out)")
        self.assertTrue((outside / "README.md").is_file(), msg="its files are intact")

    def test_a_worktree_nested_one_level_deeper_inside_the_worktrees_folder_is_kept_too(self):
        deeper = self.w.main / WT_DIR / "group" / "inner_wt"
        add_worktree(self.w.main, deeper, RECORDS_BRANCH)

        proc, report = self.run_report(what="worktree not directly inside the worktrees folder")

        item = pick(report, "worktree", "inner_wt")
        self.assertEqual((item["action"], item.get("reason")), ("left", "outside-worktrees-folder"),
                         msg="W11: only a DIRECT child of .claude/worktrees is flat; a deeper one is kept")
        self.assertKept(deeper, "deeper worktree")

    def test_a_brief_named_worktree_that_holds_a_foreign_branch_is_left(self):
        self.rebuild(fw_branch="foreign/work")
        merge_records(self.w)

        proc, report = self.run_report(what="brief worktree holds a foreign branch")

        item = pick(report, "worktree", FW_NAME)
        self.assertEqual((item["action"], item.get("reason")), ("left", "holds-foreign-branch"),
                         msg="INV-2: the brief's worktree path now holds a branch outside the Owned set")
        self.assertKept(self.w.fw, "foreign branch worktree")
        self.assertIn("foreign/work", local_branches(self.w), msg="the foreign branch is never touched")

    def test_a_locked_worktree_is_left_locked(self):
        git(self.w.main, "worktree", "lock", "--reason", "another session", str(self.w.tw))

        proc, report = self.run_report(what="locked worktree")

        item = pick(report, "worktree", TW_NAME)
        self.assertEqual((item["action"], item.get("reason")), ("left", "locked"), msg="INV-3: a locked worktree is never removed")
        self.assertKept(self.w.tw, "locked worktree")

    def test_the_main_checkout_and_a_landing_worktree_are_never_touched(self):
        w = self.w
        landing = w.main / WT_DIR / "20261015-land-50"
        add_worktree(w.main, landing, RECORDS_BRANCH)  # it holds an OWNED branch, so only the landing guard protects it
        main_before = snapshot(w.main)

        proc, report = self.run_report(what="landing worktree present")

        self.assertKept(landing, "landing worktree (land_contract.is_landing_worktree)")
        self.assertIn(RECORDS_BRANCH, local_branches(w), msg="the branch a landing worktree holds is not deleted")
        self.assertNotEqual((pick(report, "worktree", "20261015-land-50", required=False) or {}).get("action"), "removed",
                            msg="INV-2: a landing worktree is never removed")
        self.assertEqual(snapshot(w.main), main_before, msg="INV-2: the main checkout is byte-identical")
        self.assertTrue(w.main.is_dir(), msg="and it is of course still there")


# ===========================================================================
# Brief lookup (INV-2)
# ===========================================================================
class BriefLookupTests(CleanupCase):
    def test_a_brief_with_contract_none_is_found_through_the_contract_header(self):
        self.deliver()

        proc, report = self.run_report(what="brief found by the header")

        self.assertEqual(pick(report, "worktree", FW_NAME)["action"], "removed",
                         msg="INV-2 step 1: the `**Work Item Brief:**` header finds a brief whose `contract:` is none")
        self.assertEqual(pick(report, "local-branch", FEATURE)["action"], "removed", msg="and so its `branch:` is owned")

    def test_without_the_header_and_without_a_head_branch_the_brief_is_not_found_and_its_work_is_not_owned(self):
        self.rebuild(header=False)
        merge_records(self.w)

        proc, report = self.run_report(what="no header, started from the main checkout")

        self.assertIsNone(pick(report, "local-branch", FEATURE, required=False), msg="control: with no header and no head branch the brief's branch is not owned")
        self.assertIsNone(pick(report, "worktree", FW_NAME, required=False), msg="control: nor is its worktree")
        self.assertKept(self.w.fw, "unowned brief worktree")
        self.assertEqual(pick(report, "worktree", TW_NAME)["action"], "removed",
                         msg="the sub-task worktree is owned through the contract handoff (task/<slug>/<id>) alone")

    def test_the_branch_fallback_finds_the_brief_through_the_starting_trees_branch(self):
        # Pass-2 F2: the starting branch's brief is adopted only when it positively names THIS contract.
        self.rebuild(header=False, brief_contract=CONTRACT_REL)
        merge_records(self.w)

        proc, report = self.run_report(from_dir=self.w.fw, what="no header, started from the feature worktree")

        self.assertIsNotNone(pick(report, "worktree", FW_NAME),
                             msg="INV-2 step 2: `brief_for_branch(<starting branch>, origin/master)` finds the brief by its `branch:`")
        self.assertIsNotNone(pick(report, "local-branch", FEATURE), msg="so the brief's branch is in the Owned set")

    # -- F3: the recorded pull request heads (INV-2 step 2) -------------------------------------------
    PR_URL = "https://github.com/acme/app/pull/41"  # what record_text(1) stores as `pull_request:`

    def seed_recorded_head(self, head: str) -> None:
        self.w.tools.set_gh(pr_view={"41": {"number": 41, "headRefName": head, "state": "MERGED", "baseRefName": "master",
                                            "mergedAt": "2026-10-14T00:00:00Z", "url": self.PR_URL}})

    def test_positive_control_the_fake_gh_answers_pr_view_by_url(self):
        self.seed_recorded_head(FEATURE)
        exe = self.w.tools.bin / ("gh.exe" if os.name == "nt" else "gh")

        proc = run_cmd([str(exe), "pr", "view", self.PR_URL, "--json", "headRefName"], cwd=self.w.main,
                           env=clean_env(tools=self.w.tools))

        self.assertEqual(proc.rc, 0, msg=f"F3: the fake must answer the URL form pr_merged.gh_pr passes; got {proc.describe()}")
        self.assertEqual((proc.json() or {}).get("headRefName"), FEATURE, msg="and with the seeded head branch, not its failure branch")

    def test_the_recorded_head_branch_finds_the_brief_when_the_session_starts_in_the_main_checkout(self):
        self.rebuild(header=False)
        merge_records(self.w)
        self.seed_recorded_head(FEATURE)

        proc, report = self.run_report(what="no header, recorded head, started from the main checkout")

        self.assertEqual(pick(report, "worktree", FW_NAME)["action"], "removed",
                         msg="INV-2 step 2: `gh pr view <recorded url>` names the head branch, `brief_for_branch` finds the brief, "
                             "so the feature worktree is owned even though the header and the starting branch say nothing")
        self.assertEqual(pick(report, "local-branch", FEATURE)["action"], "removed", msg="and so is its branch")
        self.assertTrue([c for c in self.w.tools.gh_calls() if c.get("args", [])[:2] == ["pr", "view"] and self.PR_URL in c["args"]],
                        msg="positive control: the script really asked gh about the recorded url")

    def test_a_starting_tree_of_another_work_item_is_not_adopted_by_the_branch_fallback(self):
        """W1: without a header the fallback tries the starting tree's branch. A sibling item's brief names ANOTHER
        contract, so it must be rejected, or this run would own (and remove) the sibling's branch and worktree."""
        self.rebuild(header=False)
        merge_records(self.w)
        sibling = add_sibling_item(self.w, f".claude/concepts/{OTHER_SLUG}.md")

        proc, report = self.run_report(from_dir=sibling, what="started from a sibling item's tree")

        self.assertIsNone(pick(report, "worktree", SIBLING_WT, required=False), msg="W1: the sibling's worktree is not in the Owned set")
        self.assertIsNone(pick(report, "local-branch", SIBLING_BRANCH, required=False), msg="W1: nor is its branch")
        self.assertKept(sibling, "the sibling item's tree")
        self.assertIn(SIBLING_BRANCH, local_branches(self.w), msg="W1: the sibling's branch is never touched")
        self.assertKept(self.w.fw, "this item's own brief was not found, so its worktree is not owned either")

    def test_a_recorded_head_is_tried_before_the_starting_trees_branch(self):
        """W1: the starting branch is tried LAST. The sibling's brief says `contract: none`, which no contract check
        can reject, so only the ORDER keeps the run on this item's own brief."""
        self.rebuild(header=False)
        merge_records(self.w)
        self.seed_recorded_head(FEATURE)
        sibling = add_sibling_item(self.w, "none")

        proc, report = self.run_report(from_dir=sibling, what="sibling start tree, recorded head")

        self.assertEqual(pick(report, "worktree", FW_NAME)["action"], "removed",
                         msg="the recorded head's brief (this item's) is the one adopted")
        self.assertIsNone(pick(report, "worktree", SIBLING_WT, required=False), msg="the starting tree's brief is not used")
        self.assertIsNone(pick(report, "local-branch", SIBLING_BRANCH, required=False), msg="nor its branch")
        self.assertKept(sibling, "the sibling item's tree")

    def test_a_starting_trees_brief_is_adopted_only_when_it_positively_names_this_contract(self):
        """Pass-2 F2. `contract: none` is the common unset value (this very item's brief carries it), so it proves
        nothing about the sibling. With no header and no recorded head the starting branch is the last resort and
        must be refused for a brief that does not name THIS slug, remote branch included under --remove-remote."""
        self.rebuild(header=False)
        merge_records(self.w)
        sibling = add_sibling_item(self.w, "none")
        git(self.w.main, "push", "-q", "origin", SIBLING_BRANCH)  # a freshly pushed branch: in origin/master, no open PR

        proc, report = self.run_report("--remove-remote", from_dir=sibling, what="unset-contract sibling start tree")

        self.assertEqual([i for i in report.get("items", []) if SIBLING_BRANCH in item_id(i) or SIBLING_WT in item_id(i)], [],
                         msg="F2: nothing of the sibling appears in the report")
        self.assertIn(SIBLING_BRANCH, remote_heads(self.w), msg="F2: the sibling's REMOTE branch is untouched")
        self.assertIn(SIBLING_BRANCH, local_branches(self.w), msg="and so is its local branch")
        self.assertKept(sibling, "the sibling item's tree")
        self.assertFalse(report.get("finish_command"), msg="and no finish line is printed for a tree that is not this item's")

    # -- pass-2 F6: the header path is resolved from the tree's root, and read at the ref ---------------
    def test_a_brief_that_exists_only_at_origin_is_found_through_the_contract_header(self):
        """The brief reached origin/master with the records commit, so no working tree has it on disk. The header
        path is checked on disk only today; INV-2 says it is read at the ref."""
        self.rebuild(brief_in_base=False)
        merge_records(self.w)
        self.assertFalse((self.w.main / BRIEF_REL).exists(), msg="fixture sanity: the main checkout has no brief on disk")

        proc, report = self.run_report(what="brief only at the ref")

        self.assertEqual(pick(report, "worktree", FW_NAME)["action"], "removed",
                         msg="F6: the header names the brief, which is read at origin/master, so its worktree is owned")
        self.assertEqual(pick(report, "local-branch", FEATURE)["action"], "removed", msg="and so is its branch")

    def test_started_in_a_sub_folder_of_the_feature_worktree_the_brief_is_still_found(self):
        """F6 guard. `--from <tree>/src` is not the tree's root, so a header path relative to it does not exist;
        the root must be used (once the starting-branch fallback stops adopting unset briefs, F2, this is the only
        way left to the brief)."""
        self.deliver()
        sub = self.w.fw / "src"

        proc, report = self.run_report(from_dir=sub, what="started in src/ of the feature worktree")

        self.assertIsNotNone(pick(report, "worktree", FW_NAME), msg="F6: the feature worktree is in the Owned set")
        self.assertIsNotNone(pick(report, "local-branch", FEATURE), msg="and so is its branch")


# ===========================================================================
# [8] The one-line report
# ===========================================================================
class ReportLineTests(CleanupCase):
    def setUp(self) -> None:
        super().setUp()
        self.deliver()

    def test_every_item_left_carries_exactly_one_reason_from_the_closed_set_and_the_line_shows_it(self):
        (self.w.fw / "wip.txt").write_text("keeps the tree\n", encoding="utf-8")
        commit_off_master(self.w, RECORDS_BRANCH)

        proc, report = self.run_report(what="mixed run")

        left = [i for i in report["items"] if i.get("action") in ("left", "deferred")]
        self.assertGreaterEqual(len(left), 3, msg="fixture: the dirty worktree and two branches are left")
        for it in report["items"]:
            self.assertIn(it.get("action"), ACTIONS, msg=f"closed set of actions, got {it}")
        for it in left:
            self.assertIn(it.get("reason"), REASONS, msg=f"INV-8: a left item carries one reason of the closed set, got {it}")
            self.assertIn(it["reason"], report["line"], msg=f"INV-8: the line shows the reason of {item_id(it)}")
        self.assertRegex(report["line"], rf"^CLEANUP {re.escape(SLUG)}: removed \d+ \(.*\); left {len(left)} \(", msg="INV-8: exact line shape")
        self.assertNotIn("\n", report["line"], msg="INV-8: one line")

    def test_files_are_cut_to_three_per_item_with_a_plus_k_more_tail(self):
        names = [f"f{i}.txt" for i in range(1, 6)]
        for n in names:
            (self.w.fw / n).write_text("x\n", encoding="utf-8")

        proc, report = self.run_report(what="five untracked files")

        m = re.search(r"uncommitted-changes \[([^\]]*)\]", report["line"])
        self.assertIsNotNone(m, msg=f"INV-8: the line carries `<reason> [<file>, <file>, <file>, +k more]`, got {report['line']!r}")
        parts = m.group(1).split(", ")
        self.assertEqual(len(parts), 4, msg=f"three files and the tail, got {parts}")
        self.assertEqual(parts[3], "+2 more", msg="five files, three shown, so +2 more")
        self.assertTrue(set(parts[:3]) <= set(names), msg="the shown files are real ones")
        item = pick(report, "worktree", FW_NAME)
        self.assertEqual(sorted(f.replace("\\", "/") for f in item["files"]), names, msg="the JSON keeps the full list")

    def test_a_long_report_is_capped_at_600_characters_with_a_plus_k_more_tail(self):
        w = self.rebuild(n_tasks=12)
        merge_records(w)
        for i in range(2, 13):
            commit_off_master(w, f"task/{SLUG}/{task_id(i)}")

        proc, report = self.run_report(what="twelve sub-tasks")

        line = report["line"]
        left = [i for i in report["items"] if i.get("action") == "left"]
        self.assertGreaterEqual(len(left), 11, msg="the JSON keeps every item: the eleven unmerged branches are all there")
        self.assertLessEqual(len(line), 600, msg=f"INV-8: the line is never longer than 600 characters, got {len(line)}")
        self.assertRegex(line, r"\+\d+ more", msg="INV-8: what does not fit is summarised as `+k more`")
        self.assertLessEqual(line.count("not-in-default"), 8, msg="INV-8: a list names at most 8 items")
        self.assertNotIn("\n", line, msg="one line")
        proc2, _ = self.cleanup(as_json=False)
        self.assertNotIn("\n", proc2.out.strip(), msg="and the printed form is one line too")

    @unittest.skipIf(IS_WINDOWS, "a file name with a control character cannot exist on Windows")
    def test_control_characters_in_names_are_removed_from_the_line(self):
        bad = "evil\x1b[31mred\x07.txt"
        (self.w.fw / bad).write_text("x\n", encoding="utf-8")

        proc, report = self.run_report(what="control character in a file name")

        self.assertNotRegex(report["line"], r"[\x00-\x1f\x7f]", msg="INV-8: names have control characters removed")
        self.assertIn("evilred", report["line"].replace("[31m", ""), msg="control: the rest of the name is still shown")


# ===========================================================================
# [9] Standing trees
# ===========================================================================
def quote(path: str) -> str:
    return "'" + str(path).replace("'", "'\\''") + "'"


class StandingTreeTests(CleanupCase):
    def setUp(self) -> None:
        super().setUp()
        self.deliver()

    def assertDeferredWithOneFinishLine(self, report: dict, path: Path, reason: str, what: str) -> None:
        item = pick(report, "worktree", path.name)
        self.assertEqual((item["action"], item.get("reason")), ("deferred", reason), msg=f"{what}: the tree is deferred as {reason}")
        self.assertKept(path, what)
        fc = report.get("finish_command")
        self.assertIsInstance(fc, str, msg=f"{what}: a deferred item brings a finish_command")
        self.assertRegex(fc, r"^py -3 '.*' --contract '.*' --from '.*'$", msg="INV-6: every path is single-quoted")
        words = shell_words(fc)
        self.assertEqual(words[:2], ["py", "-3"], msg="the finish command is `py -3 '<script>' ...`")
        self.assertEqual(real(words[2]), real(CLEANUP), msg="INV-6: <script> is the absolute path of the running copy")
        self.assertEqual(words[3:5], ["--contract", SLUG], msg="the contract slug")
        self.assertEqual(words[5], "--from", msg="the --from flag")
        self.assertEqual(real(words[6]), real(self.w.main), msg="INV-6: it runs from the main root")
        self.assertEqual(len(words), 7, msg="exactly one script line")
        line = report["line"]
        self.assertIn("; finish: " + fc, line, msg="INV-8: the line carries `; finish: <finish_command>`")
        self.assertEqual(line.count("finish:"), 1, msg="INV-6: exactly one finish line, never several")
        self.assertIn("holders", item, msg=f"HN-1 ({what}): a deferred standing-tree or in-use item carries the Holder reading "
                                          f"in a `holders` field; the item has only {sorted(item)}")
        finish_at = line.index("; finish: ")
        stops = [m.start() for m in re.finditer(r"; stop: ", line)]
        self.assertTrue(all(s < finish_at for s in stops), msg=f"HN-8 ({what}): every `; stop:` part comes before `; finish:`")

    def holder_item(self, report: dict, path: Path | None = None) -> dict:
        item = pick(report, "worktree", (path or self.w.fw).name)
        self.assertIn("holders", item, msg=f"HN-1: the deferred item carries a `holders` field; it has only {sorted(item)}")
        return item["holders"]

    def held_run(self, sessions, *, env: dict | None = None, flags: tuple = (), what: str = "a held tree", **kw):
        """The feature worktree is the standing tree; the fake `claude` lists ``sessions``."""
        set_claude(self.w.tools, sessions)
        extra = {"CLAUDE_PROJECT_DIR": str(self.w.fw)}
        extra.update(env or {})
        return self.run_report(*flags, env_extra=extra, what=what, **kw)

    def stop_parts(self, line: str) -> list:
        return re.findall(r"; stop: (claude stop [^;]*)", line)

    def test_claude_project_dir_inside_a_target_defers_it_with_exactly_one_finish_line(self):
        proc, report = self.run_report(env_extra={"CLAUDE_PROJECT_DIR": str(self.w.fw)}, what="CLAUDE_PROJECT_DIR in the feature worktree")

        self.assertDeferredWithOneFinishLine(report, self.w.fw, "standing-tree", "CLAUDE_PROJECT_DIR")
        self.assertGone(self.w.tw, "the other owned worktrees are still cleaned")
        self.assertGone(self.w.aw, "the other owned worktrees are still cleaned")

    def test_claude_project_dir_in_a_sub_folder_of_a_target_defers_it_too(self):
        proc, report = self.run_report(env_extra={"CLAUDE_PROJECT_DIR": str(self.w.fw / "src")}, what="CLAUDE_PROJECT_DIR in src/")

        self.assertDeferredWithOneFinishLine(report, self.w.fw, "standing-tree", "CLAUDE_PROJECT_DIR in a sub-folder")

    def test_the_scripts_own_working_directory_inside_a_target_defers_it(self):
        proc, report = self.run_report(cwd=self.w.fw, what="script started inside the feature worktree")

        self.assertDeferredWithOneFinishLine(report, self.w.fw, "standing-tree", "script cwd")
        self.assertEqual(proc.rc, 3, msg=f"a deferred item makes the run partial; got {proc.describe()}")

    def test_the_starting_tree_given_by_from_is_a_standing_tree(self):
        """INTERPRETATION (see HANDOFF): the skills pass `--from "$PWD"`, the tree the session stands in."""
        proc, report = self.run_report(from_dir=self.w.fw, what="--from the feature worktree")

        self.assertDeferredWithOneFinishLine(report, self.w.fw, "standing-tree", "--from")

    def test_a_deferred_run_prints_one_line_without_json(self):
        proc, _ = self.cleanup(env_extra={"CLAUDE_PROJECT_DIR": str(self.w.fw)}, as_json=False)

        text = proc.out.strip()
        self.assertEqual(text.count("\n"), 0, msg=f"one line, got {proc.describe()}")
        self.assertIn("; finish: py -3 '", text, msg="the single finish line is inside it")

    def test_a_later_call_from_outside_clears_the_deferred_tree(self):
        self.run_report(env_extra={"CLAUDE_PROJECT_DIR": str(self.w.fw)}, what="first call, standing")
        self.assertKept(self.w.fw, "after the first call")

        proc, report = self.run_report(what="second call, from outside")

        self.assertEqual(pick(report, "worktree", FW_NAME)["action"], "removed", msg="INV-6: the next call from outside removes it")
        self.assertGone(self.w.fw, "second call")
        self.assertFalse(report.get("finish_command"), msg="nothing is deferred any more, so no finish line")
        self.assertNotIn("finish:", report["line"], msg="and the line carries none")

    def test_a_path_with_an_apostrophe_is_written_with_the_quote_escape(self):
        quoted_root = Path(os.path.realpath(tempfile.mkdtemp(prefix="cleanup_"))) / "it's here"
        self.addCleanup(rmtree_force, quoted_root.parent)
        self.w = build_world(quoted_root)
        merge_records(self.w)

        proc, report = self.run_report(env_extra={"CLAUDE_PROJECT_DIR": str(self.w.fw)}, what="main root with an apostrophe")

        fc = report.get("finish_command") or ""
        self.assertIn("'\\''", fc, msg=f"INV-6: a `'` inside a path is written `'\\''`, got {fc!r}")
        self.assertEqual(real(shell_words(fc)[6]), real(self.w.main), msg="and the quoted words read back as the real main root")

    @unittest.skipUnless(IS_WINDOWS, "in-use is the Windows probe; on POSIX a rename always succeeds and only the standing-tree rule applies")
    def test_a_tree_another_process_holds_reads_in_use_with_its_files_intact_and_a_later_call_clears_it(self):
        import subprocess
        holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], cwd=str(self.w.fw),
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        self.procs.append(holder)
        time.sleep(1.0)
        target = self.tmp / "shared_node_modules"
        link = self.make_link(self.w.fw, "node_modules", target)
        listing = tree_listing(self.w.fw)

        proc, report = self.run_report(what="a held worktree")

        self.assertDeferredWithOneFinishLine(report, self.w.fw, "in-use", "held cwd")
        self.assertEqual(self.holder_item(report)["verdict"], "none-found",
                         msg="HN-1: the in-use deferral also gets a Holder reading; the default list is empty, so none-found")
        self.assertIn(NOTE_TEXT, report["line"], msg="HN-8: the fixed note is in the line whenever any item carries holders")
        self.assertEqual(self.stop_parts(report["line"]), [], msg="no holder, so no stop command")
        self.assertEqual(tree_listing(self.w.fw), listing, msg="INV-6: the held tree's files are intact after the probe")
        self.assertTrue(is_link_entry(link), msg="INV-4/INV-6: a deferred tree keeps its links")
        self.assertTargetSurvived(target, "held tree")

        holder.kill()
        holder.wait(timeout=10)
        time.sleep(0.5)
        proc2, report2 = self.run_report(what="after the holder left")
        self.assertEqual(pick(report2, "worktree", FW_NAME)["action"], "removed", msg="INV-6: a later call clears it")
        self.assertTargetSurvived(target, "after the later call")

    @unittest.skipUnless(IS_WINDOWS, "the rename probe runs on Windows only")
    def test_the_printed_line_itself_carries_the_repair_instruction_when_a_folder_cannot_be_renamed_back(self):
        """W5: the skills print `line` and nothing else, so an instruction that lives only in the JSON never
        reaches the person whose folder now sits at a sibling name with broken git metadata."""
        real_rename = os.rename
        owned = {os.path.normcase(os.path.abspath(str(p))) for p in (self.w.fw, self.w.tw, self.w.aw)}
        failed: list = []

        def rename(src, dst, *a, **k):
            if os.path.normcase(os.path.abspath(str(dst))) in owned:
                failed.append((str(src), str(dst)))
                raise PermissionError(13, "renaming back is refused on purpose")
            return real_rename(src, dst, *a, **k)

        rc, out, report = self.run_in_process([], patches={"os.rename": rename, "os.replace": rename})
        try:
            self.assertTrue(failed, msg="positive control: the probe tried to rename a folder back")
            self.assertIsInstance(report, dict, msg=f"the run must print a report, got {out[:300]!r}")
            line = report.get("line", "")
            m = re.search(r"git worktree repair '([^']+)'", line)
            self.assertIsNotNone(m, msg=f"W5: the printed line carries `git worktree repair '<path>'`; the line is {line!r}")
            self.assertEqual(real(m.group(1)), real(failed[0][1]), msg="and names the folder whose rename-back failed")
            self.assertLessEqual(len(line), 600, msg="INV-8: the line is still one bounded line")
            self.assertNotIn("\n", line, msg="one line")
        finally:
            for src, dst in failed:
                if os.path.isdir(src) and not os.path.exists(dst):
                    real_rename(src, dst)

    def test_two_deferred_trees_still_give_exactly_one_finish_line_and_it_runs_for_real(self):
        """F12: the finish line is executed once through Git Bash (not parsed by this test's own mirror of the
        quoting), after the holder is gone, and clears BOTH deferred trees; with two deferred trees there is
        still exactly one `finish:`."""
        bash = find_git_bash()
        self.assertIsNotNone(bash, msg="Git Bash next to git is needed to run the finish line the way a person would")

        proc, report = self.run_report(cwd=self.w.tw, env_extra={"CLAUDE_PROJECT_DIR": str(self.w.fw)},
                                       what="two standing trees")

        for path in (self.w.fw, self.w.tw):
            self.assertEqual(pick(report, "worktree", path.name)["action"], "deferred", msg=f"{path.name} is deferred")
        self.assertEqual(report["line"].count("finish:"), 1, msg="INV-6: two deferred trees, one finish line")
        fc = report["finish_command"]
        self.assertEqual(fc.count("--contract"), 1, msg="and the finish command is one script line")

        real_run = run_cmd([bash, "--noprofile", "--norc", "-c", fc], cwd=self.tmp, env=clean_env(tools=self.w.tools), timeout=300)

        self.assertEqual(real_run.rc, 0, msg=f"AC9: the one line finishes the cleanup from outside; got {real_run.describe()}")
        self.assertGone(self.w.fw, "the finish line, feature worktree")
        self.assertGone(self.w.tw, "the finish line, sub-task worktree")

    def test_a_long_main_root_keeps_the_whole_printed_line_with_the_finish_command_within_600_characters(self):
        """F8/INV-8 end to end: a 60-character folder in the main root's path makes the finish command long."""
        long_root = Path(os.path.realpath(tempfile.mkdtemp(prefix="cleanup_"))) / ("L" * 60)
        self.addCleanup(rmtree_force, long_root.parent)
        self.w = build_world(long_root)
        self.worlds.append(self.w)
        merge_records(self.w)
        commit_off_master(self.w, RECORDS_BRANCH)  # one more left item beside the deferred tree

        proc, report = self.run_report(env_extra={"CLAUDE_PROJECT_DIR": str(self.w.fw)}, what="long main root")

        self.assertTrue(report.get("finish_command"), msg="fixture sanity: a tree is deferred, so the finish command is in the line")
        self.assertLessEqual(len(report["line"]), 600, msg=f"INV-8: the whole line, finish command included; got {len(report['line'])}")
        self.assertTrue(report["line"].endswith("; finish: " + report["finish_command"]), msg="and the finish command is whole")

    @unittest.skipUnless(IS_WINDOWS, "the rename probe runs on Windows only")
    def test_a_probe_that_cannot_rename_back_halts_all_further_mutation_and_names_the_repair_line(self):
        real_rename = os.rename
        owned = {os.path.normcase(os.path.abspath(str(p))) for p in (self.w.fw, self.w.tw, self.w.aw)}
        failed: list = []

        def rename(src, dst, *a, **k):
            if os.path.normcase(os.path.abspath(str(dst))) in owned:  # the probe renaming back to the original name
                failed.append((str(src), str(dst)))
                raise PermissionError(13, "renaming back is refused on purpose")
            return real_rename(src, dst, *a, **k)

        before_branches = local_branches(self.w)
        self.w.tools.clear_git_calls()

        rc, out, report = self.run_in_process([], patches={"os.rename": rename, "os.replace": rename})

        self.assertTrue(failed, msg="positive control: the probe did rename a folder and tried to rename it back")
        try:
            self.assertIsInstance(report, dict, msg=f"the run must still print a report, got {out[:300]!r}")
            self.assertNotEqual(rc, 0, msg="a halted run is not a clean run")
            repair = [m for s in collect_strings(report) for m in re.findall(r"git worktree repair '([^']+)'", s)]
            self.assertTrue(repair, msg="INV-9: the report carries the repair line `git worktree repair '<path>'`")
            self.assertIn(real(failed[0][1]), [real(p) for p in repair],
                          msg="INV-9: the repair line names the folder whose rename-back failed")
            self.assertEqual(mutating_calls(self.w.tools), [],
                             msg="INV-9: after a failed rename-back NO further mutation runs: no worktree remove, no branch -D, no push")
            self.assertEqual(local_branches(self.w), before_branches, msg="INV-9: every local branch is still there")
        finally:
            for src, dst in failed:  # put the folder back so the fixture can be deleted
                if os.path.isdir(src) and not os.path.exists(dst):
                    real_rename(src, dst)

    # -----------------------------------------------------------------------------------------------
    # Holder reading, end to end (contract 2026-10-18-cleanup-names-worktree-holder.md, HN-1 to HN-9).
    # Six tests in all (with the in-use test above and the halted run), every one but the halted run a --dry-run.
    # The reading's detail (session variable, cwd forms, forging, twenty holders) lives in the fast unit classes
    # HolderReadingUnitTests and HolderRunnerFakeTests, which need no git world.
    # -----------------------------------------------------------------------------------------------
    @staticmethod
    def without_holders(report: dict) -> list:
        return [{k: v for k, v in it.items() if k != "holders"} for it in report["items"]]

    def short_line(self, item: dict) -> str:
        """The bracket is checked on a short synthetic line: the real line sheds a bracket when the checkout path is long."""
        return self.load_module().build_line(SLUG, [item], "py -3 'x'")

    def test_a_session_inside_the_deferred_tree_is_named_with_its_stop_command_and_the_decision_is_unchanged(self):
        env = {"CLAUDE_PROJECT_DIR": str(self.w.fw)}
        base_proc, base = self.run_report("--dry-run", env_extra=env, what="dry run, default empty list")
        self.assertEqual(pick(base, "worktree", FW_NAME)["action"], "deferred", msg="fixture sanity: the tree is deferred")
        before, main_before = state(self.w), snapshot(self.w.main)

        proc, report = self.held_run([sess("bbfa6fec", self.w.fw / "src", name="worker", state="done")], flags=("--dry-run",),
                                     what="one holder")

        holders = self.holder_item(report)
        self.assertEqual(holders.get("verdict"), "found", msg=f"HN-1: one session inside the tree reads `found`; got {holders}")
        self.assertEqual(len(holders.get("sessions") or []), 1, msg="exactly the one session")
        h = holders["sessions"][0]
        self.assertEqual((h.get("id"), h.get("name"), h.get("state"), h.get("kind"), h.get("stop_command")),
                         ("bbfa6fec", "worker", "done", "background", "claude stop bbfa6fec"), msg=f"Holder fields; got {h}")
        self.assertFalse(h.get("this_session"), msg="CLAUDE_CODE_SESSION_ID is not set, so nobody is this session")
        self.assertTrue(h.get("cwd"), msg="HN-6: the working folder is kept in the JSON")
        self.assertNotIn(str(self.w.fw / "src"), report["line"], msg="HN-6: the working folder is never in the line")
        self.assertIn('[held by bbfa6fec "worker" done]', self.short_line(pick(report, "worktree", FW_NAME)),
                      msg="HN-8: the bracket (checked on a short line, the real one may shed it)")
        self.assertIn(NOTE_TEXT, report["line"], msg="HN-8: the uncut note is in the real line")
        self.assertIn("; stop: claude stop bbfa6fec", report["line"], msg="HN-8: the stop command is printed")
        self.assertEqual(report.get("stop_commands"), ["claude stop bbfa6fec"], msg="HN-8: --json lists exactly what the line prints")
        self.assertEqual((report.get("holder_lookup") or {}).get("verdict"), "read", msg="the report records that a lookup ran")
        self.assertEqual((proc.rc, report["outcome"], report.get("finish_command")),
                         (base_proc.rc, base["outcome"], base.get("finish_command")),
                         msg="HN-1: exit code, outcome and finish command are the same with and without holders")
        self.assertEqual(self.without_holders(report), self.without_holders(base),
                         msg="HN-1/HN-10: action, reason, files, detail and every other field are byte-identical; only `holders` is new")
        others = [it for it in report["items"] if not (it["action"] == "deferred" and it.get("reason") in ("standing-tree", "in-use"))]
        self.assertTrue(others, msg="fixture sanity: items that are not deferred exist")
        self.assertTrue(all("holders" not in it for it in others), msg="HN-10: only deferred items gain `holders`")
        self.assertEqual(state(self.w), before, msg="a dry run with a holder: nothing on disk changes")
        self.assertEqual(snapshot(self.w.main), main_before, msg="and the main checkout is byte-identical")

    def test_two_deferred_trees_each_list_only_their_own_holder_and_get_one_stop_command_each(self):
        x = sess("bbfa6fec", self.w.fw / "src", name="session-x", state="working")
        y = sess("cc00dd11", self.w.tw, name="session-y", state="blocked")

        proc, report = self.held_run([x, y], flags=("--dry-run",), cwd=self.w.tw, what="session X in tree A, session Y in tree B")

        for path in (self.w.fw, self.w.tw):
            self.assertEqual(pick(report, "worktree", path.name)["action"], "deferred", msg=f"fixture sanity: {path.name} is deferred")
        a, b = pick(report, "worktree", self.w.fw.name), pick(report, "worktree", self.w.tw.name)
        self.assertEqual([s.get("id") for s in a["holders"]["sessions"]], ["bbfa6fec"], msg="HN-5: tree A lists only X")
        self.assertEqual([s.get("id") for s in b["holders"]["sessions"]], ["cc00dd11"], msg="HN-5: tree B lists only Y")
        bracket_a, bracket_b = self.short_line(a), self.short_line(b)
        self.assertIn('[held by bbfa6fec "session-x" working]', bracket_a, msg="HN-8: A's bracket names X")
        self.assertNotIn("cc00dd11", bracket_a, msg="and does not name Y")
        self.assertIn('[held by cc00dd11 "session-y" blocked]', bracket_b, msg="HN-8: B's bracket names Y")
        self.assertNotIn("bbfa6fec", bracket_b, msg="and does not name X")
        line = report["line"]
        self.assertEqual(sorted(self.stop_parts(line)), ["claude stop bbfa6fec", "claude stop cc00dd11"],
                         msg="HN-8: exactly one stop command for each session")
        self.assertEqual(sorted(report.get("stop_commands") or []), ["claude stop bbfa6fec", "claude stop cc00dd11"])
        self.assertEqual(line.count("finish:"), 1, msg="INV-6: two deferred trees, still one finish line")
        self.assertTrue(line.endswith("; finish: " + report["finish_command"]), msg="and it is last and whole")
        self.assertEqual(len(claude_calls(self.w.tools)), 1, msg="HN-2: one Session List Reading serves both trees")

    def test_a_halted_run_still_reports_the_holders_of_a_tree_deferred_before_the_halt(self):
        gone = self.tmp / "vanished_modules"
        self.make_link(self.w.fw / "src" / "gone", "node_modules", gone)
        rmtree_force(gone)
        env = {"CLAUDE_PROJECT_DIR": str(self.w.aw)}
        base_proc, base = self.run_report(env_extra=env, what="halted run, default list")
        self.assertEqual((pick(base, "worktree", AW_NAME)["action"], pick(base, "worktree", AW_NAME).get("reason")),
                         ("deferred", "standing-tree"), msg="fixture sanity: the advance tree is deferred first")
        self.assertEqual(pick(base, "worktree", FW_NAME).get("reason"), "remove-failed", msg="fixture sanity: the next tree halts the run")
        self.assertEqual((base_proc.rc, base["outcome"]), (3, "partial"))

        set_claude(self.w.tools, [sess("bbfa6fec", self.w.aw)])
        proc, report = self.run_report(env_extra=env, what="halted run, one holder")

        holders = self.holder_item(report, self.w.aw)
        self.assertEqual(holders.get("verdict"), "found", msg="HN-1: the lookup runs after the halt too, over the items already there")
        self.assertIn("; stop: claude stop bbfa6fec", report["line"], msg="and its stop command is printed")
        self.assertEqual((proc.rc, report["outcome"], report.get("finish_command")), (base_proc.rc, base["outcome"], base.get("finish_command")),
                         msg="HN-1: outcome, exit code and finish command are the same as without the lookup")
        self.assertEqual(self.without_holders(report), self.without_holders(base), msg="and so is every item")

    def test_a_run_with_nothing_deferred_never_starts_claude_and_adds_no_holder_fields(self):
        set_claude(self.w.tools, [sess("bbfa6fec", self.w.fw)])

        proc, report = self.run_report("--dry-run", what="nothing deferred")

        self.assertEqual(pick(report, "worktree", FW_NAME)["action"], "removed", msg="fixture sanity: nothing is deferred")
        self.assertEqual(claude_calls(self.w.tools), [], msg="HN-10: a run with nothing deferred never starts claude")
        for key in ("stop_commands", "holder_lookup"):
            self.assertNotIn(key, report, msg=f"HN-1: no lookup ran, so no `{key}`")
        self.assertTrue(all("holders" not in it for it in report["items"]), msg="no item gains `holders`")
        self.assertNotIn("note:", report["line"], msg="and the line has no note")
        self.assertNotIn("[held by", report["line"])

    def test_a_session_whose_folder_reaches_the_tree_through_a_link_holds_it_like_the_deferral_says(self):
        link = self.tmp / "via_link"
        try:
            make_directory_link(link, self.w.fw)
        except (OSError, NotImplementedError, ImportError) as exc:
            self.skipTest(f"a directory link cannot be made on this host: {exc}")
        self.addCleanup(drop_link, link)

        proc, report = self.held_run([sess("bbfa6fec", link / "src")], flags=("--dry-run",), what="folder reached through a link")

        self.assertEqual(self.holder_item(report).get("verdict"), "found",
                         msg="HN-5: the holder match is the deferral's own _inside, so a link into the tree is inside it")


def drop_link(link: Path) -> None:
    for remove in (os.rmdir, os.unlink):
        try:
            remove(str(link))
            return
        except OSError:
            continue



# ===========================================================================
# Isolation, gate and flags
# ===========================================================================
class FailClosedTests(CleanupCase):
    """Pass-2 F5 and F7: a git read that fails never turns a safety check off, and the orphan report never crashes
    the run or tells anyone to delete what git never checked. The wrapper `git` injects each failure."""

    def setUp(self) -> None:
        super().setUp()
        self.deliver()

    def test_an_ignored_folder_listing_that_fails_keeps_the_tree_unverifiable(self):
        set_git_fail(self.w.tools, ["ls-files", "--others"])

        proc, report = self.run_report(what="ls-files --others fails")

        for path in (self.w.fw, self.w.tw, self.w.aw):
            item = pick(report, "worktree", path.name)
            self.assertEqual((item["action"], item.get("reason")), ("left", "unverifiable"),
                             msg=f"F5: without the ignored-folder list a nested worktree cannot be ruled out, so {path.name} is kept")
            self.assertKept(path, "unverifiable tree")

    def test_a_tracked_file_listing_that_fails_removes_no_link_and_keeps_the_tree_unverifiable(self):
        target = self.tmp / "shared_node_modules"
        link = self.make_link(self.w.fw, "node_modules", target)
        set_git_fail(self.w.tools, ["ls-files", "-z"], unless=["--others"])  # only the tracked-files listing

        proc, report = self.run_report(what="ls-files (tracked) fails")

        item = pick(report, "worktree", FW_NAME)
        self.assertEqual((item["action"], item.get("reason")), ("left", "unverifiable"),
                         msg="F5: with no tracked list every tracked link would look untracked and be removed; the tree is kept")
        self.assertTrue(is_link_entry(link), msg="F5: and no link was removed")
        self.assertTargetSurvived(target, "tracked listing failed")
        self.assertKept(self.w.fw, "tree with an unknown tracked set")

    def test_a_trees_head_is_read_from_the_tree_itself_never_from_the_main_checkout(self):
        """If the HEAD of a tree cannot be read, the cleanup used to test the MAIN checkout's HEAD instead (the cwd
        is the main root). Here the porcelain listing loses its HEAD lines, and the feature tree holds a commit
        origin/master does not have; that commit must not be waved through on the main checkout's account."""
        commit(self.w.fw, {"src/extra.txt": "never merged\n"}, "a commit origin/master does not have")
        set_git_fail(self.w.tools, ["worktree", "list"], mode="strip-head")

        proc, report = self.run_report(what="worktree list without HEAD lines")

        item = pick(report, "worktree", FW_NAME)
        self.assertEqual(item["action"], "left", msg="F5: a tree whose own HEAD is not known to be in origin/master is kept")
        self.assertIn(item.get("reason"), ("unpushed-commits", "unverifiable"), msg="with a reason that says why")
        self.assertKept(self.w.fw, "tree with an unreadable HEAD")
        self.assertEqual(git(self.w.main, "show", f"{FEATURE}:src/extra.txt"), "never merged", msg="and the commit is intact")

    def make_orphan(self) -> Path:
        orphan = self.w.main / WT_DIR / (AW_NAME + "-2")  # a second advance folder of this slug that git does not list
        orphan.mkdir()
        (orphan / "unsaved.txt").write_text("the only copy\n", encoding="utf-8")
        return orphan

    def test_the_orphan_report_never_tells_anyone_to_delete_the_folder_by_hand(self):
        orphan = self.make_orphan()

        proc, report = self.run_report(what="orphan folder")

        item = pick(report, "worktree", orphan.name)
        self.assertEqual(item["action"], "left", msg="the orphan folder is reported")
        self.assertNotIn("by hand", json.dumps(item.get("detail")).lower(),
                         msg="F7: git never ran its clean, ancestor or nested checks on this folder, which may hold the only "
                             "copy of someone's work; the detail says to inspect it, not to delete it")
        self.assertTrue((orphan / "unsaved.txt").is_file(), msg="and it is of course untouched")

    def test_an_os_error_in_the_orphan_pass_does_not_crash_the_run_after_worktrees_were_removed(self):
        orphan = self.make_orphan()
        real_listdir = os.listdir

        def listdir(path="."):
            if str(path).replace("\\", "/").endswith(orphan.name):
                raise PermissionError(13, "listing the orphan folder is refused on purpose")
            return real_listdir(path)

        try:
            rc, out, report = self.run_in_process([], patches={"os.listdir": listdir})
        except OSError as exc:
            self.fail(f"F7: the orphan pass crashed the run with {exc!r}; worktrees were already removed, so the branch "
                      "steps and the report line must still follow")

        self.assertIsInstance(report, dict, msg=f"the run still prints a report, got {out[:300]!r}")
        self.assertTrue(report.get("line", "").startswith("CLEANUP "), msg="and a line")
        for branch in OWNED_BRANCHES:
            self.assertNotIn(branch, local_branches(self.w), msg=f"F7: the branch step still ran ({branch})")
        self.assertGone(self.w.fw, "the worktrees removed before the orphan pass stay removed")


class IsolationTests(CleanupCase):
    def test_one_items_failure_is_recorded_and_the_run_goes_on_to_the_next_item(self):
        self.deliver()
        set_git_fail(self.w.tools, ["worktree", "remove", FW_NAME], ["worktree", "remove", TW_NAME])

        proc, report = self.run_report(what="two removals fail")

        for name in (FW_NAME, TW_NAME):
            item = pick(report, "worktree", name)
            self.assertEqual((item["action"], item.get("reason")), ("left", "remove-failed"), msg=f"INV-9: {name} is recorded remove-failed")
            self.assertTrue(item.get("detail"), msg=f"{name}: the git message is kept in detail")
        self.assertGone(self.w.aw, "the next worktree is still removed")
        self.assertNotIn(RECORDS_BRANCH, local_branches(self.w), msg="INV-9: and the local branches that can go are still deleted")
        self.assertEqual((proc.rc, report.get("outcome")), (3, "partial"), msg="partial, exit 3")
        self.assertKept(self.w.fw, "remove-failed feature worktree (F7)")
        self.assertKept(self.w.tw, "remove-failed task worktree (F7)")
        self.assertTrue((self.w.fw / "src" / "feature.txt").is_file() and (self.w.tw / "src" / "task.txt").is_file(),
                        msg="F7: nothing falls back to a recursive delete; the files are intact")

    def test_a_removal_that_fails_the_way_trial_t1_recorded_is_reported_now_and_the_orphan_folder_next_time(self):
        """F1. T1 on this host: the failed remove had already deleted every file and DEREGISTERED the worktree,
        leaving an empty folder. A clean exit-1 injection hides that: after it, git no longer lists the folder
        and a later call would never mention it (contract Failure Modes: 'the report names the leftover folder')."""
        self.deliver()
        set_git_fail(self.w.tools, ["worktree", "remove", FW_NAME], mode="t1")

        proc, report = self.run_report(what="host-shaped remove failure")

        item = pick(report, "worktree", FW_NAME)
        self.assertEqual((item["action"], item.get("reason")), ("left", "remove-failed"),
                         msg="the failure is recorded as remove-failed, whatever the host left behind")
        self.assertIn(FW_NAME, json.dumps(report), msg="the report names the leftover folder")
        self.assertTrue(self.w.fw.is_dir() and os.listdir(str(self.w.fw)) == [],
                        msg="fixture sanity: the host-shaped failure left an EMPTY folder")
        self.assertNotIn(real(self.w.fw), worktree_paths(self.w.main), msg="fixture sanity: git deregistered it")

        set_git_fail(self.w.tools)  # the holder has left; nothing fails any more
        proc2, report2 = self.run_report(what="the next call after an orphaned folder")

        self.assertIn(FW_NAME, report2.get("line", ""),
                      msg="the next call must still report the orphan empty folder (git no longer lists it, so only "
                          "a look at the folder itself can find it); silence here loses it for good")
        leftovers = [i for i in report2.get("items", []) if FW_NAME in item_id(i)]
        self.assertTrue(leftovers and all(i.get("action") in ("left", "deferred") and i.get("reason") in REASONS
                                          for i in leftovers),
                        msg=f"and an item with a reason from the closed set carries it, got {leftovers}")


class GateTests(CleanupCase):
    def test_nothing_is_touched_when_the_contract_is_not_implemented_and_no_records_pull_request_is_open(self):
        self.w.tools.set_gh(open_prs=[])
        before, main_before = state(self.w), snapshot(self.w.main)

        proc, report = self.run_report(what="approved contract, nothing open")

        self.assertEqual((proc.rc, report.get("outcome")), (5, "not-delivered"), msg=f"INV-1; got {proc.describe()}")
        self.assertUntouched(before, main_before, "approved contract")

    def test_a_flip_that_exists_only_in_the_working_tree_does_not_count(self):
        main = self.w.main
        (main / CONTRACT_REL).write_text(contract_text("implemented"), encoding="utf-8")
        (main / RESULTS_REL).mkdir(parents=True, exist_ok=True)
        (main / RESULTS_REL / f"{task_id(1)}.yaml").write_text(record_text(1), encoding="utf-8")
        self.w.tools.set_gh(open_prs=[])
        before, main_before = state(self.w), snapshot(main)

        proc, report = self.run_report(what="local flip only")

        self.assertEqual((proc.rc, report.get("outcome")), (5, "not-delivered"),
                         msg="INV-1: the contract and the records are read AT origin/master, never from the working tree")
        self.assertUntouched(before, main_before, "local flip")

    def test_implemented_at_origin_without_a_completion_record_is_not_delivered(self):
        git(self.w.ghub, "switch", "-q", "master")
        commit(self.w.ghub, {CONTRACT_REL: contract_text("implemented")}, "flip without records")
        git(self.w.ghub, "push", "-q", "origin", "master")
        self.w.tools.set_gh(open_prs=[])
        before, main_before = state(self.w), snapshot(self.w.main)

        proc, report = self.run_report(what="implemented but unrecorded")

        self.assertEqual((proc.rc, report.get("outcome")), (5, "not-delivered"),
                         msg="INV-1: `Status: implemented` is not enough; every sub-task needs a GitHub-verified record at origin/master")
        self.assertUntouched(before, main_before, "unrecorded sub-task")

    def test_a_failed_fetch_is_unverifiable_exit_10_and_nothing_is_touched(self):
        before, main_before = state(self.w), snapshot(self.w.main)  # read BEFORE origin is broken: ls-remote needs it
        git(self.w.main, "remote", "set-url", "origin", str(self.tmp / "no-such-origin.git"))

        proc, report = self.run_report(what="fetch fails")

        self.assertEqual(proc.rc, 10, msg=f"INV-1: when origin cannot be fetched the reading is unverifiable, exit 10; got {proc.describe()}")
        self.assertEqual(report.get("outcome"), "unverifiable", msg="outcome")
        self.assertEqual(report.get("delivery", {}).get("verdict"), "unverifiable", msg="verdict")
        reasons = report.get("delivery", {}).get("reasons") or [""]
        self.assertTrue(reasons[0].startswith("git fetch origin master failed"),
                        msg=f"F13: it is the failed fetch that made the reading unverifiable, not another path; got {reasons[0]!r}")
        # state() runs ls-remote, which needs the origin this test broke on purpose: put the URL back first (F13),
        # then compare EVERYTHING (branches and folder listings too), not the worktree list alone.
        git(self.w.main, "remote", "set-url", "origin", str(self.w.origin))
        self.assertUntouched(before, main_before, "failed fetch")

    def test_dry_run_on_a_delivered_item_changes_nothing(self):
        merge_records(self.w)
        before, main_before = state(self.w), snapshot(self.w.main)

        proc, report = self.run_report("--dry-run", what="dry run, delivered")

        self.assertIs(report.get("dry_run"), True, msg="the report says it was a dry run")
        self.assertEqual(report.get("delivery", {}).get("verdict"), "delivered", msg="the gate is still evaluated")
        self.assertTrue(report.get("items"), msg="a dry run lists what it would do")
        self.assertUntouched(before, main_before, "dry run")


class CommandLineTests(CleanupCase):
    def test_no_arguments_is_a_usage_error_exit_2(self):
        self.assertTrue(CLEANUP.is_file(), msg=MISSING)
        proc = run_py(CLEANUP, cwd=self.w.main, env=clean_env(tools=self.w.tools))

        self.assertEqual(proc.rc, 2, msg=f"usage errors are exit 2; got {proc.describe()}")
        self.assertNotIn("Traceback", proc.err, msg="a usage error is a message, not a crash")

    def test_print_main_root_prints_the_main_checkout_from_inside_a_linked_worktree(self):
        self.assertTrue(CLEANUP.is_file(), msg=MISSING)
        proc = run_py(CLEANUP, "--print-main-root", cwd=self.w.fw, env=clean_env(tools=self.w.tools))

        self.assertEqual(proc.rc, 0, msg=f"--print-main-root exits 0; got {proc.describe()}")
        self.assertEqual(real(proc.out.strip()), real(self.w.main),
                         msg="--print-main-root prints flat_worktree.describe()['main_root'], the MAIN checkout, even from a worktree")
        self.assertEqual(len(proc.out.strip().splitlines()), 1, msg="and nothing else: the skills use it in `cd $(...)`")


# ===========================================================================
# Landed untracked files (contract 2026-10-17-worktree-removal-untracked-identical, CL-1 to CL-8)
# ===========================================================================
LANDED_REL = "src/landed.txt"
LANDED_BYTES = b"landed on master\nsecond line\n"
REF = "origin/master"


class LandedUntrackedTests(CleanupCase):
    """An untracked file that git would store as exactly the blob ``origin/<default>`` holds at the same path no
    longer keeps a delivered worktree: cleanup proves it identical (git's own filtered ``hash-object``), deletes
    it last and file by file, then removes the tree without force. Anything it cannot prove keeps today's
    behaviour. Every test starts from the delivered world (stage 2) with ``core.autocrlf`` pinned to false in the
    main repository (shared by its worktrees), so a host-wide autocrlf setting cannot change a verdict."""

    def setUp(self) -> None:
        super().setUp()
        git(self.w.main, "config", "core.autocrlf", "false")
        self.deliver()

    # -- helpers ---------------------------------------------------------------------------------
    def land(self, files: dict | None = None) -> dict:
        return land_on_master(self.w, files if files is not None else {LANDED_REL: LANDED_BYTES})

    def untracked_copy(self, rel: str, data: bytes | None = None, tree: Path | None = None) -> Path:
        """Write the untracked copy. By default the exact bytes ``git cat-file blob origin/master:<rel>`` holds."""
        if data is None:
            done = subprocess.run([REAL_GIT, "cat-file", "blob", f"{REF}:{rel}"], cwd=str(self.w.main),
                                  capture_output=True)
            self.assertEqual(done.returncode, 0, msg=f"fixture: the blob {REF}:{rel} must exist: {done.stderr!r}")
            data = done.stdout
        path = (tree or self.w.fw) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def porcelain(self, tree: Path | None = None) -> str:
        return git(tree or self.w.fw, "status", "--porcelain", "--untracked-files=all")

    def fw_item(self, report: dict) -> dict:
        return pick(report, "worktree", FW_NAME)

    def calls_for(self, tree_name: str, *heads: str) -> list:
        return [c["args"] for c in git_calls(self.w.tools)
                if sub_command(c["args"])[:1] and sub_command(c["args"])[0] in heads
                and any(tree_name in a for a in c["args"])]

    def worktree_remove_calls(self) -> list:
        return [c["args"] for c in git_calls(self.w.tools)
                if sub_command(c["args"])[:2] == ["worktree", "remove"] and FW_NAME in c["args"][-1].replace("\\", "/")]

    # -- 1 fixture control -----------------------------------------------------------------------
    def test_fixture_control_land_on_master_leaves_the_tree_behind_origin_with_only_the_copy_untracked(self):
        self.land()
        copy = self.untracked_copy(LANDED_REL)

        self.assertEqual(git_rc_code(self.w.fw, "merge-base", "--is-ancestor", "HEAD", REF), 0,
                         msg="fixture: the tree's HEAD is still an ancestor of origin/master after the landing")
        self.assertEqual(self.porcelain(), f"?? {LANDED_REL}",
                         msg="fixture: git status lists only the copy, as untracked")
        self.assertEqual(copy.read_bytes(), LANDED_BYTES, msg="fixture: the copy holds exactly the landed bytes")

    # -- 2 and 3 the removal ---------------------------------------------------------------------
    def test_the_only_untracked_file_being_identical_the_tree_is_removed_and_the_report_says_why(self):
        self.land()
        self.untracked_copy(LANDED_REL)

        proc, report = self.run_report(what="one identical untracked file")

        item = self.fw_item(report)
        self.assertEqual((item["action"], item.get("reason")), ("removed", None),
                         msg="CL-1/CL-5: an untracked file identical to the blob on origin/master loses nothing, so the "
                             f"tree is removed; got {item.get('action')}/{item.get('reason')} files={item.get('files')}")
        self.assertGone(self.w.fw, "identical untracked file")
        self.assertNotIn(FEATURE, local_branches(self.w), msg="its branch is removed as for a clean tree")
        self.assertEqual(item.get("identical"), [LANDED_REL], msg="CL-7: the item names the file it proved identical")
        self.assertIn(f"[identical to {REF}: {LANDED_REL}]", report.get("line", ""),
                      msg="CL-7: the printed line explains the removal with the identical bracket")
        self.assertEqual((proc.rc, report.get("outcome")), (0, "cleaned"), msg="everything was cleaned: exit 0")

    def test_an_identical_file_in_a_subfolder_head_does_not_have_still_lets_the_tree_go(self):
        rel = "docs/deep/landed.txt"
        self.land({rel: LANDED_BYTES})
        self.assertFalse((self.w.fw / "docs").exists(), msg="fixture: HEAD has no docs folder, the copy creates it")
        self.untracked_copy(rel)

        proc, report = self.run_report(what="identical file in a new subfolder")

        item = self.fw_item(report)
        self.assertEqual((item["action"], item.get("reason")), ("removed", None),
                         msg="CL-6: the empty folders the delete leaves are not a reason to keep the tree "
                             "(a non-forced `git worktree remove` takes them)")
        self.assertGone(self.w.fw, "identical file in a new subfolder")
        self.assertEqual(item.get("identical"), [rel], msg="CL-7: the item names the file")

    # -- 4 and 5 differing -----------------------------------------------------------------------
    def test_untracked_file_with_different_content_at_a_landed_path_keeps_the_tree(self):
        self.land()
        copy = self.untracked_copy(LANDED_REL, b"my own unsaved edit\n")

        proc, report = self.run_report(what="different content at a landed path")

        item = self.fw_item(report)
        self.assertEqual((item["action"], item.get("reason")), ("left", "uncommitted-changes"),
                         msg="CL-4: content that differs from the blob is unsaved work")
        self.assertEqual([f.replace("\\", "/") for f in item.get("files") or []], [LANDED_REL], msg="files names it")
        self.assertEqual(item.get("identical"), [], msg="CL-4: the item carries an empty identical list, not a missing key")
        self.assertEqual(copy.read_bytes(), b"my own unsaved edit\n", msg="the file is intact")
        self.assertKept(self.w.fw, "different content")

    def test_a_file_origin_lacks_next_to_an_identical_one_keeps_the_tree_and_deletes_neither(self):
        self.land()
        same = self.untracked_copy(LANDED_REL)
        absent = self.w.fw / "src" / "not_on_master.txt"
        absent.write_bytes(b"only here\n")

        proc, report = self.run_report(what="identical file next to an absent one")

        item = self.fw_item(report)
        self.assertEqual((item["action"], item.get("reason")), ("left", "uncommitted-changes"),
                         msg="CL-4: one untracked file that is not on origin/master keeps the tree")
        self.assertEqual([f.replace("\\", "/") for f in item.get("files") or []], ["src/not_on_master.txt"],
                         msg="CL-4: files lists only the file that differs (here: absent at the ref)")
        self.assertEqual(item.get("identical"), [LANDED_REL], msg="CL-4: identical lists the proven one")
        self.assertTrue(same.is_file() and absent.is_file(), msg="CL-4: nothing is deleted, not even the identical file")
        self.assertKept(self.w.fw, "identical next to absent")

    # -- 6 line endings --------------------------------------------------------------------------
    def test_6a_with_autocrlf_true_a_crlf_copy_of_landed_lf_text_is_identical(self):
        text = b"line one\nline two\n"
        self.land({LANDED_REL: text})
        git(self.w.main, "config", "core.autocrlf", "true")
        self.untracked_copy(LANDED_REL, b"line one\r\nline two\r\n")

        proc, report = self.run_report(what="CRLF copy under core.autocrlf=true")

        item = self.fw_item(report)
        self.assertEqual((item["action"], item.get("reason")), ("removed", None),
                         msg="CL-1/Q1: hash-object with filters folds CRLF to LF under autocrlf=true, exactly as git "
                             "stages the file, so the copy is identical to the blob")
        self.assertGone(self.w.fw, "CRLF copy under autocrlf")
        self.assertEqual(item.get("identical"), [LANDED_REL], msg="the file is reported as identical")

    def test_6b_with_autocrlf_false_the_same_crlf_copy_differs(self):
        self.land({LANDED_REL: b"line one\nline two\n"})
        git(self.w.main, "config", "core.autocrlf", "false")
        copy = self.untracked_copy(LANDED_REL, b"line one\r\nline two\r\n")
        self.assertFalse((self.w.fw / ".gitattributes").exists(), msg="fixture: no .gitattributes in the tree")

        proc, report = self.run_report(what="CRLF copy under core.autocrlf=false")

        item = self.fw_item(report)
        self.assertEqual((item["action"], item.get("reason")), ("left", "uncommitted-changes"),
                         msg="CL-1: when git applies no conversion, CRLF versus LF is a real difference")
        self.assertEqual(item.get("identical"), [],
                         msg="CL-1: git's view decides, not a line-ending fold of our own; nothing is identical")
        self.assertEqual(copy.read_bytes(), b"line one\r\nline two\r\n", msg="the file is intact")
        self.assertKept(self.w.fw, "CRLF copy without conversion")

    def test_6c_with_autocrlf_true_a_crlf_copy_with_one_word_changed_still_differs(self):
        self.land({LANDED_REL: b"line one\nline two\n"})
        git(self.w.main, "config", "core.autocrlf", "true")
        copy = self.untracked_copy(LANDED_REL, b"line one\r\nline TWO\r\n")

        proc, report = self.run_report(what="changed CRLF copy under core.autocrlf=true")

        item = self.fw_item(report)
        self.assertEqual((item["action"], item.get("reason")), ("left", "uncommitted-changes"),
                         msg="CL-1: a real content change still differs even where line endings are folded")
        self.assertEqual(item.get("identical"), [], msg="and nothing is reported identical")
        self.assertEqual(copy.read_bytes(), b"line one\r\nline TWO\r\n", msg="the edit is intact")
        self.assertKept(self.w.fw, "changed CRLF copy")

    # -- 7 any other change ----------------------------------------------------------------------
    def _assert_other_change_keeps_today_exactly(self, tree_change: str) -> None:
        self.land()
        self.untracked_copy(LANDED_REL)
        (self.w.fw / "src" / "feature.txt").write_text("edited and not committed\n", encoding="utf-8")
        if tree_change == "staged":
            git(self.w.fw, "add", "src/feature.txt")
        self.w.tools.clear_git_calls()

        proc, report = self.run_report(what=f"identical untracked file plus a {tree_change} change")

        item = self.fw_item(report)
        self.assertEqual((item["action"], item.get("reason")), ("left", "uncommitted-changes"),
                         msg=f"CL-2: a {tree_change} tracked change keeps the tree")
        self.assertEqual(sorted(f.replace("\\", "/") for f in item.get("files") or []), ["src/feature.txt", LANDED_REL],
                         msg="CL-2: `files` lists both paths exactly as today")
        self.assertEqual(item.get("identical"), [], msg="CL-2: no comparison ran, so the list is empty")
        compared = [a for a in git_calls_args(self.w.tools)
                    if sub_command(a)[:1] == ["hash-object"]
                    or (sub_command(a)[:1] == ["ls-tree"] and "--name-only" not in a)]
        self.assertEqual(compared, [], msg="CL-2: no ls-tree of the ref and no hash-object runs when anything else changed")
        self.assertTrue((self.w.fw / LANDED_REL).is_file(), msg="the untracked file is still there")
        self.assertKept(self.w.fw, f"identical untracked plus {tree_change}")

    def test_7_an_identical_file_plus_a_modified_tracked_file_is_left_exactly_as_today(self):
        self._assert_other_change_keeps_today_exactly("modified")

    def test_7_an_identical_file_plus_a_staged_change_is_left_exactly_as_today(self):
        self._assert_other_change_keeps_today_exactly("staged")

    # -- 8 fail closed ---------------------------------------------------------------------------
    def _assert_unverifiable(self, token: str) -> None:
        self.land()
        copy = self.untracked_copy(LANDED_REL)
        if token == "ls-tree":  # not the contract-folder read that runs from the main checkout
            set_git_fail(self.w.tools, ["ls-tree"], unless=["--name-only"])
        else:
            set_git_fail(self.w.tools, [token])

        proc, report = self.run_report(what=f"{token} fails")

        item = self.fw_item(report)
        self.assertEqual((item["action"], item.get("reason")), ("left", "unverifiable"),
                         msg=f"CL-3: when git {token} fails the tree is unverifiable, never treated as identical")
        self.assertTrue(item.get("detail"), msg="CL-3: detail names the cause")
        self.assertEqual(copy.read_bytes(), LANDED_BYTES, msg="the file is intact")
        self.assertEqual(self.worktree_remove_calls(), [], msg="CL-3: no `git worktree remove` for this tree")
        self.assertKept(self.w.fw, f"{token} fails")

    def test_8_a_failing_ls_tree_of_the_ref_leaves_the_tree_unverifiable(self):
        self._assert_unverifiable("ls-tree")

    def test_8_a_failing_hash_object_leaves_the_tree_unverifiable(self):
        self._assert_unverifiable("hash-object")

    # -- 9 ordering ------------------------------------------------------------------------------
    def test_9_with_an_unpushed_commit_the_identical_file_is_still_on_disk(self):
        self.land()
        copy = self.untracked_copy(LANDED_REL)
        # Stage only the extra file: the shared `commit` helper runs `git add -A`, which would also commit the
        # untracked copy and leave no untracked file for the comparison to prove identical.
        (self.w.fw / "src" / "extra.txt").write_text("never merged\n", encoding="utf-8")
        git(self.w.fw, "add", "--", "src/extra.txt")
        git(self.w.fw, "commit", "-q", "-m", "a commit origin/master does not have")

        proc, report = self.run_report(what="identical file and an unpushed commit")

        item = self.fw_item(report)
        self.assertEqual((item["action"], item.get("reason")), ("left", "unpushed-commits"),
                         msg="CL-5: the HEAD check still comes before any delete")
        self.assertEqual(copy.read_bytes(), LANDED_BYTES, msg="CL-5: the identical file is NOT deleted from a tree that is kept")
        self.assertEqual(item.get("identical"), [LANDED_REL],
                         msg="Q3: a comparison ran at the status step, so --json reports what it proved")

    def test_9_in_a_standing_tree_the_identical_file_is_still_on_disk(self):
        self.land()
        copy = self.untracked_copy(LANDED_REL)

        proc, report = self.run_report(from_dir=self.w.fw, what="identical file in the standing tree")

        item = self.fw_item(report)
        self.assertEqual((item["action"], item.get("reason")), ("deferred", "standing-tree"),
                         msg="CL-5: an identical untracked file must not turn the standing-tree deferral into "
                             f"uncommitted-changes; got {item.get('action')}/{item.get('reason')}")
        self.assertEqual(copy.read_bytes(), LANDED_BYTES, msg="CL-5: a deferred tree is left entirely untouched")

    def test_9_in_a_locked_tree_the_identical_file_is_still_on_disk(self):
        self.land()
        copy = self.untracked_copy(LANDED_REL)
        git(self.w.main, "worktree", "lock", "--reason", "another session", str(self.w.fw))

        proc, report = self.run_report(what="identical file in a locked tree")

        item = self.fw_item(report)
        self.assertEqual((item["action"], item.get("reason")), ("left", "locked"), msg="CL-5: the lock check still comes first")
        self.assertEqual(copy.read_bytes(), LANDED_BYTES, msg="CL-5: nothing is deleted from a locked tree")
        self.assertEqual(item.get("identical"), [], msg="the lock check precedes the comparison: no identical list")

    def test_9_a_dry_run_reports_the_identical_file_and_deletes_nothing(self):
        self.land()
        copy = self.untracked_copy(LANDED_REL)
        before = mutating_calls(self.w.tools)

        proc, report = self.run_report("--dry-run", what="dry run with an identical file")

        item = self.fw_item(report)
        self.assertEqual(item["action"], "removed", msg="CL-5/AC4: a dry run says the tree would be removed")
        self.assertEqual(item.get("identical"), [LANDED_REL], msg="CL-5: and reports the identical file")
        self.assertIn(f"[identical to {REF}: {LANDED_REL}]", report.get("line", ""), msg="CL-7: the dry-run line carries the bracket")
        self.assertEqual(copy.read_bytes(), LANDED_BYTES, msg="CL-5: a dry run deletes no file")
        self.assertEqual(mutating_calls(self.w.tools), before, msg="a dry run runs no mutating git command")
        self.assertKept(self.w.fw, "dry run")

    # -- 10 order of calls -----------------------------------------------------------------------
    def test_10_the_file_is_rehashed_after_the_status_reread_and_before_its_delete_and_removal_is_not_forced(self):
        self.land()
        self.untracked_copy(LANDED_REL)
        real_remove, real_unlink = os.remove, os.unlink
        deletes: list = []

        def spy(real_fn):
            def fn(path, *a, **k):
                if os.path.basename(str(path)) == "landed.txt":
                    deletes.append((str(path), len(git_calls(self.w.tools))))
                return real_fn(path, *a, **k)
            return fn

        rc, out, report = self.run_in_process([], patches={"os.remove": spy(real_remove), "os.unlink": spy(real_unlink)})

        self.assertIsInstance(report, dict, msg=f"the in-process run must print a report, got {out[:300]!r}")
        item = pick(report, "worktree", FW_NAME)
        self.assertEqual(item["action"], "removed", msg="the identical file does not keep the tree")
        self.assertEqual(len(deletes), 1, msg=f"CL-6: the file is deleted by one single-file delete, saw {deletes}")
        at = deletes[0][1]
        calls = git_calls(self.w.tools)
        status_idx = [i for i, c in enumerate(calls[:at]) if sub_command(c["args"])[:1] == ["status"]
                      and any(FW_NAME in a for a in c["args"])]
        hash_idx = [i for i, c in enumerate(calls[:at]) if sub_command(c["args"])[:1] == ["hash-object"]
                    and any(FW_NAME in a for a in c["args"])]
        self.assertGreaterEqual(len(status_idx), 2, msg="CL-5 step 5: status is read again before the first delete")
        self.assertTrue(hash_idx and hash_idx[-1] > status_idx[-1],
                        msg=f"CL-5 step 6: a hash-object of the file comes after the status re-read (status {status_idx}, "
                            f"hash-object {hash_idx}) and before its delete")
        removes = [(i, c["args"]) for i, c in enumerate(calls) if sub_command(c["args"])[:2] == ["worktree", "remove"]
                   and FW_NAME in c["args"][-1].replace("\\", "/")]
        self.assertEqual(len(removes), 1, msg="one `git worktree remove` for the tree")
        self.assertGreaterEqual(removes[0][0], at, msg="CL-5 step 8: the removal comes after the delete")
        self.assertFalse([a for a in removes[0][1] if a in ("-f", "--force", "-ff")],
                         msg="CL-8: the removal is never forced")

    # -- 11 per-file re-check --------------------------------------------------------------------
    def test_11_a_second_file_rewritten_after_the_first_delete_stops_the_loop_and_is_kept(self):
        a_rel, b_rel = "src/landed_a.txt", "src/landed_b.txt"
        self.land({a_rel: b"file a\n", b_rel: b"file b\n"})
        self.untracked_copy(a_rel)
        self.untracked_copy(b_rel)
        fw = self.w.fw
        real_remove, real_unlink = os.remove, os.unlink
        order: list = []
        new_bytes = b"written by someone after the first delete\n"

        def rewriting(real_fn):
            def fn(path, *a, **k):
                result = real_fn(path, *a, **k)
                name = os.path.basename(str(path))
                if name in ("landed_a.txt", "landed_b.txt") and not order:
                    order.append(name)
                    other = "landed_b.txt" if name == "landed_a.txt" else "landed_a.txt"
                    (fw / "src" / other).write_bytes(new_bytes)
                elif name in ("landed_a.txt", "landed_b.txt"):
                    order.append(name)
                return result
            return fn

        rc, out, report = self.run_in_process([], patches={"os.remove": rewriting(real_remove),
                                                           "os.unlink": rewriting(real_unlink)})

        self.assertIsInstance(report, dict, msg=f"the in-process run must print a report, got {out[:300]!r}")
        item = pick(report, "worktree", FW_NAME)
        self.assertTrue(order, msg="CL-5: the first identical file was deleted before the second was checked again")
        first = order[0]
        second = "landed_b.txt" if first == "landed_a.txt" else "landed_a.txt"
        self.assertEqual((item["action"], item.get("reason")), ("left", "uncommitted-changes"),
                         msg="CL-5 step 6: a file that changed since the comparison stops the loop")
        self.assertEqual([f.replace("\\", "/") for f in item.get("files") or []], ["src/" + second],
                         msg="CL-5 step 6: files names the changed file only")
        self.assertEqual(order, [first], msg=f"nothing is deleted after the mismatch, saw deletes {order}")
        self.assertEqual((fw / "src" / second).read_bytes(), new_bytes, msg="the new bytes of the changed file are intact")
        self.assertIn("src/" + first, str(item.get("detail")).replace("\\", "/"),
                      msg="CL-5 step 6: detail lists the file that was already deleted")
        self.assertEqual(self.worktree_remove_calls(), [], msg="no `git worktree remove` after a mismatch")
        self.assertKept(fw, "second file changed")

    # -- 12 links --------------------------------------------------------------------------------
    def test_12a_an_untracked_symlink_at_a_landed_path_is_never_identical(self):
        rel = "src/landed_link.txt"
        self.land({rel: LANDED_BYTES})
        outside = self.tmp / "outside_target.txt"
        outside.write_bytes(LANDED_BYTES)
        link = self.w.fw / rel
        try:
            os.symlink(str(outside), str(link))
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"a file symlink cannot be created on this host without a privilege: {exc}")

        proc, report = self.run_report(what="symlink at a landed path")

        item = self.fw_item(report)
        self.assertEqual((item["action"], item.get("reason")), ("left", "uncommitted-changes"),
                         msg="CL-1: lstat shows a link, not a regular file, so the path differs and the tree is left")
        self.assertEqual(item.get("identical"), [], msg="CL-1: a link is never identical")
        self.assertTrue(os.path.islink(str(link)), msg="the link is still there")
        self.assertEqual(outside.read_bytes(), LANDED_BYTES, msg="the link's target is intact")
        self.assertKept(self.w.fw, "symlink at a landed path")

    def test_12b_a_landed_file_reached_through_an_untracked_linked_folder_is_never_deleted(self):
        rel = "src/shared/landed.txt"
        self.land({rel: LANDED_BYTES})
        outside = self.tmp / "outside_shared"
        outside.mkdir()
        (outside / "landed.txt").write_bytes(LANDED_BYTES)
        link = self.w.fw / "src" / "shared"
        try:
            make_directory_link(link, outside)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"a directory link cannot be created on this host: {exc}")
        listed = self.porcelain()  # records whether git lists the file through the link at all (the ASSUMED line)

        proc, report = self.run_report(what="landed file behind an untracked linked folder")

        item = self.fw_item(report)
        self.assertEqual((item["action"], item.get("reason")), ("left", "uncommitted-changes"),
                         msg="CL-1: a path behind a linked folder fails the parent-link check and counts as differing, "
                             f"so the tree is left. git status listed: {listed!r}")
        self.assertEqual(item.get("identical"), [],
                         msg=f"CL-1: nothing behind a link is identical. git status listed: {listed!r}")
        self.assertEqual((outside / "landed.txt").read_bytes(), LANDED_BYTES,
                         msg=f"the file in the folder outside the tree is intact. git status listed: {listed!r}")
        self.assertTrue(is_link_entry(link), msg="the link is still there")
        self.assertKept(self.w.fw, "landed file behind a linked folder")


# ===========================================================================
# Holder reading: failure paths, the read-only proof and the real wrapper (HN-2, HN-3, HN-9)
# ===========================================================================
def pid_is_alive(pid: int, scratch: Path) -> bool:
    """True while the process ``pid`` exists (tasklist on Windows, signal 0 elsewhere)."""
    if IS_WINDOWS:
        return str(pid) in run_cmd(["tasklist", "/FI", "PID eq %d" % pid, "/NH"], cwd=scratch).out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _norm_text(path) -> str:
    return os.path.normcase(os.path.realpath(str(path)))


def is_holder_call(args) -> bool:
    return isinstance(args, (list, tuple)) and "agents" in list(args) and "--all" in list(args)


class HolderInProcessCase(CleanupCase):
    """The cleanup runs inside this process (``run_in_process``) so a test can patch ``shutil.which`` and
    ``subprocess.Popen``. The fake ``claude`` is still the only program a lookup can reach."""

    def setUp(self) -> None:
        super().setUp()
        self.deliver()

    def module_with(self, *names: str):
        module = self.load_module()
        need_names(self, module, *names)
        return module

    def track_fake(self, pidfile: Path) -> None:
        """Registered after setUp's cleanups, so it runs before the folder is deleted: a fake `claude` that a timeout
        left running is ended by the pid it wrote, and awaited by polling (never a fixed sleep)."""
        self.addCleanup(end_fake_claude, pidfile)

    def held_in_process(self, sessions=None, *, stdout: str | None = None, code: int = 0, sleep: float = 0,
                        patches: dict | None = None, env: dict | None = None, flags: tuple = ("--dry-run",), pidfile=None):
        set_claude(self.w.tools, sessions, stdout=stdout, code=code, sleep=sleep, pidfile=pidfile)
        extra = {"CLAUDE_PROJECT_DIR": str(self.w.fw)}
        extra.update(env or {})
        rc, out, report = self.run_in_process(list(flags), patches=patches or {}, env_extra=extra)
        self.assertIsInstance(report, dict, msg=f"the run must print one report, got {out[:300]!r}")
        return rc, report

    def assertCannotTell(self, rc: int, report: dict, reason: str, what: str) -> dict:
        item = pick(report, "worktree", FW_NAME)
        self.assertIn("holders", item, msg=f"HN-3 ({what}): a failed read still puts a Holder reading on the deferred item; it has only {sorted(item)}")
        holders = item["holders"]
        self.assertEqual(holders.get("verdict"), "cannot-tell", msg=f"HN-3 ({what}): a failed read is cannot-tell; got {holders}")
        self.assertEqual(holders.get("reason"), reason, msg=f"HN-3 ({what}): the fixed reason")
        # The bracket is checked through build_line with a short synthetic finish command, never through the real
        # line: the real finish command carries the checkout path, and a long path makes the line shed the bracket.
        short_line = self.load_module().build_line(SLUG, [item], "py -3 'x'")
        self.assertIn(f"[cannot tell which session holds it: {reason}]", short_line, msg=f"HN-8 ({what}): the bracket carries the reason")
        self.assertEqual((report.get("holder_lookup") or {}).get("verdict"), "cannot-tell", msg="the report records the failed lookup")
        self.assertEqual((item["action"], item.get("reason")), ("deferred", "standing-tree"), msg=f"HN-1 ({what}): the deferral is unchanged")
        self.assertEqual((rc, report["outcome"]), (3, "partial"), msg=f"HN-1 ({what}): exit code and outcome are unchanged")
        self.assertIsInstance(report.get("finish_command"), str, msg="and the finish command is still there")
        self.assertTrue(report["line"].endswith("; finish: " + report["finish_command"]))
        self.assertKept(self.w.fw, what)
        self.assertNotIn("stop_commands", report, msg="a failed read prints no stop command")
        self.assertNotIn("; stop: ", report["line"])
        return holders


class HolderFailurePathTests(HolderInProcessCase):
    """The timeout case lives in HolderReadOnlyTests (one merged test); the rest of the failure paths are here."""

    def test_a_missing_claude_command_reads_cannot_tell_with_its_fixed_reason(self):
        real_which = shutil.which

        def which(name, *a, **k):
            return None if os.path.splitext(os.path.basename(str(name)))[0].lower() == "claude" else real_which(name, *a, **k)

        rc, report = self.held_in_process([sess("bbfa6fec", self.w.fw)], patches={"shutil.which": which})

        self.assertCannotTell(rc, report, REASON_NOT_FOUND, "claude not found")
        self.assertEqual(claude_calls(self.w.tools), [], msg="HN-2: nothing was started")

    def test_a_program_that_cannot_be_started_reads_cannot_tell_with_its_fixed_reason(self):
        real_popen = subprocess.Popen

        def popen(args, *a, **k):
            if is_holder_call(args):
                raise OSError(2, "the fake launch failure")
            return real_popen(args, *a, **k)

        rc, report = self.held_in_process([sess("bbfa6fec", self.w.fw)], patches={"subprocess.Popen": popen})

        self.assertCannotTell(rc, report, REASON_NOT_STARTED, "OSError on start")

    def test_a_non_zero_exit_reads_cannot_tell_with_the_code_and_is_never_called_a_timeout(self):
        rc, report = self.held_in_process(stdout="", code=3)

        holders = self.assertCannotTell(rc, report, "claude agents exited with code 3", "exit code 3")
        self.assertNotIn("no answer within", holders.get("reason", ""), msg="HN-3: an exit is never confused with a timeout")

    def test_output_that_is_not_a_list_of_objects_reads_cannot_tell_with_the_form_reason(self):
        for label, text in (("not json", "not json"), ("an object", "{}"), ("a list of numbers", "[1]"),
                            ("an object and a number", '[{"cwd": "x"}, 3]'), ("nothing", "")):
            with self.subTest(output=label):
                rc, report = self.held_in_process(stdout=text)

                self.assertCannotTell(rc, report, REASON_FORM, label)

    def test_any_exception_in_the_lookup_reads_cannot_tell_with_the_exception_type(self):
        real_loads = json.loads

        def loads(text, *a, **k):
            if isinstance(text, (str, bytes)) and "RAISE-ME" in str(text):
                raise RuntimeError("the reader blew up")
            return real_loads(text, *a, **k)

        rc, report = self.held_in_process(stdout='[{"marker": "RAISE-ME"}]', patches={"json.loads": loads})

        self.assertCannotTell(rc, report, "the session list could not be read (RuntimeError)", "reader raises")


class HolderReadOnlyTests(HolderInProcessCase):
    """HN-9 (a), decision A1: the cleanup ends nothing except its own timed-out `claude agents` child, and that with
    ``proc.kill()`` alone: no taskkill, no killpg, no new session or process group, no tree step."""

    def recorders(self, module):
        rec = SimpleNamespace(kills=[], argvs=[], children=[], ended=[], holder_kwargs=[])
        real_popen = subprocess.Popen
        orig_kill, orig_term, orig_sig = real_popen.kill, real_popen.terminate, real_popen.send_signal
        orig_os_kill, orig_end = os.kill, module._end_own_child

        def popen_kill(self_, *a, **k):
            rec.kills.append(("Popen.kill", self_.pid))
            return orig_kill(self_, *a, **k)

        def popen_term(self_, *a, **k):
            rec.kills.append(("Popen.terminate", self_.pid))
            return orig_term(self_, *a, **k)

        def popen_sig(self_, *a, **k):
            rec.kills.append(("Popen.send_signal", self_.pid))
            return orig_sig(self_, *a, **k)

        def os_kill(pid, *a, **k):
            rec.kills.append(("os.kill", pid))
            return orig_os_kill(pid, *a, **k)

        def end(proc, *a, **k):
            rec.ended.append(proc)
            return orig_end(proc, *a, **k)

        class Recording(real_popen):
            def __init__(self, args, *a, **k):
                rec.argvs.append(list(args) if isinstance(args, (list, tuple)) else [str(args)])
                super().__init__(args, *a, **k)
                if is_holder_call(args):
                    rec.children.append(self)
                    rec.holder_kwargs.append(dict(k))

        patches = {"subprocess.Popen.kill": popen_kill, "subprocess.Popen.terminate": popen_term,
                   "subprocess.Popen.send_signal": popen_sig, "os.kill": os_kill,
                   "cleanup_delivered._end_own_child": end}
        if hasattr(os, "killpg"):
            orig_killpg = os.killpg

            def os_killpg(pgid, *a, **k):
                rec.kills.append(("os.killpg", pgid))
                return orig_killpg(pgid, *a, **k)

            patches["os.killpg"] = os_killpg
        patches["subprocess.Popen"] = Recording  # last: the method patches above are put on the real class first
        return rec, patches

    def assertNothingEnded(self, rec, what: str) -> None:
        self.assertEqual(rec.kills, [], msg=f"HN-9 ({what}): no kill, killpg, terminate or send_signal is called; saw {rec.kills}")
        self.assertEqual(rec.ended, [], msg=f"HN-9 ({what}): _end_own_child is not called")
        self.assertEqual([a for a in rec.argvs if any("taskkill" in str(x).lower() for x in a[:1])], [], msg=f"HN-9 ({what}): no taskkill")
        self.assertEqual([a for a in rec.argvs if any("stop" == str(x) for x in a)], [], msg=f"HN-9 ({what}): no `stop` argument anywhere")

    def test_a_found_a_none_found_and_a_failed_lookup_end_nothing(self):
        module = self.module_with("_end_own_child", "_run_holder_list")
        for label, sessions, kwargs, verdict in (("found", [sess("bbfa6fec", self.w.fw)], {}, "found"),
                                                   ("none-found", [], {}, "none-found"),
                                                   ("exit code", None, {"stdout": "", "code": 3}, "cannot-tell")):
            with self.subTest(run=label):
                rec, patches = self.recorders(module)

                rc, report = self.held_in_process(sessions, patches=patches, **kwargs)

                item = pick(report, "worktree", FW_NAME)
                self.assertEqual((item.get("holders") or {}).get("verdict"), verdict, msg=f"HN-1 ({label}): the lookup was made and read {verdict}")
                self.assertEqual(len(rec.children), 1, msg=f"HN-2 ({label}): exactly one `claude agents` child was started")
                self.assertNothingEnded(rec, label)

    def test_the_child_is_started_with_no_input_no_error_pipe_a_file_for_output_no_shell_and_the_folder_of_claude(self):
        """B7(2): the keyword arguments of the one Popen call, as recorded."""
        module = self.module_with("_end_own_child", "_run_holder_list")
        rec, patches = self.recorders(module)

        rc, report = self.held_in_process([sess("bbfa6fec", self.w.fw)], patches=patches)

        self.assertEqual(len(rec.children), 1, msg="fixture sanity: exactly one `claude agents` child was started")
        kwargs = rec.holder_kwargs[0]
        argv = next(a for a in rec.argvs if is_holder_call(a))
        self.assertEqual(kwargs.get("stdin"), subprocess.DEVNULL, msg=f"HN-2: stdin is DEVNULL; kwargs were {sorted(kwargs)}")
        self.assertEqual(kwargs.get("stderr"), subprocess.DEVNULL, msg="HN-2: stderr is DEVNULL")
        out = kwargs.get("stdout")
        self.assertNotIn(out, (None, subprocess.PIPE, subprocess.DEVNULL, subprocess.STDOUT), msg="HN-2: stdout is not a pipe")
        self.assertTrue(hasattr(out, "fileno") and hasattr(out, "read"), msg=f"HN-2: stdout is a file object, so nothing waits on a pipe; got {type(out).__name__}")
        self.assertFalse(kwargs.get("shell"), msg="HN-2: no shell")
        self.assertEqual(argv[1:], STOP_ARGV, msg="and the arguments are exactly `agents --json --all`")
        self.assertIn("cwd", kwargs, msg="B1: the start names a working folder")
        self.assertEqual(_norm_text(kwargs.get("cwd")), _norm_text(os.path.dirname(argv[0])),
                         msg="B1: the working folder is the folder that holds the resolved claude program, not the main checkout")
        logged = claude_calls(self.w.tools)
        self.assertEqual(len(logged), 1, msg="the fake was called once")
        self.assertEqual(_norm_text(logged[0]["cwd"]), _norm_text(os.path.dirname(argv[0])),
                         msg="B1: and the fake itself saw that folder as its working folder")

    def test_a_timeout_reads_cannot_tell_and_ends_only_the_runners_own_child_with_proc_kill_exactly_once(self):
        """The one timeout test (the failure-path timeout test is merged into it). No sleep after the timeout: the
        fake sleeps 60 s and is ended by its pid in the cleanup."""
        module = self.module_with("_end_own_child", "_run_holder_list", "HOLDER_TIMEOUT_SECONDS", "HOLDER_END_GRACE_SECONDS")
        rec, patches = self.recorders(module)
        patches["cleanup_delivered.HOLDER_TIMEOUT_SECONDS"] = 1
        patches["cleanup_delivered.HOLDER_END_GRACE_SECONDS"] = 2
        pidfile = self.w.tools.bin / "claude_pid.txt"
        self.track_fake(pidfile)

        rc, report = self.held_in_process([sess("bbfa6fec", self.w.fw)], sleep=60, patches=patches, pidfile=pidfile)

        holders = self.assertCannotTell(rc, report, "claude agents gave no answer within 1 seconds", "timeout")
        self.assertNotIn("exited with code", holders["reason"], msg="HN-3: a timeout is never an exit code")
        self.assertEqual(len(rec.children), 1, msg="exactly one `claude agents` child was started")
        child = rec.children[0]
        self.assertEqual(len(rec.ended), 1, msg="HN-9: _end_own_child is called exactly once")
        self.assertIs(rec.ended[0], child, msg="HN-9: and with the Popen that _run_holder_list created")
        self.assertIn(("Popen.kill", child.pid), rec.kills, msg=f"A1: the child was ended through proc.kill(); saw {rec.kills}")
        self.assertTrue(all(pid == child.pid for _how, pid in rec.kills),
                        msg=f"A1: every kill target is the child's own pid {child.pid}; saw {rec.kills}")
        self.assertFalse([how for how, _pid in rec.kills if how in ("os.killpg", "Popen.terminate")],
                         msg=f"A1: no killpg and no terminate; saw {rec.kills}")
        self.assertEqual([a for a in rec.argvs if a and "taskkill" in str(a[0]).lower()], [], msg="A1: no taskkill, on any platform")
        for kwargs in rec.holder_kwargs:
            self.assertFalse(kwargs.get("start_new_session") or kwargs.get("process_group") or kwargs.get("creationflags"),
                             msg=f"A1: the child is not started in a new session or process group; kwargs were {kwargs}")
        self.assertIsNotNone(child.poll(), msg="A1: the child really ended (on Windows too, through proc.kill())")


class HolderRealWrapperTests(HolderInProcessCase):
    """HN-2 and A1 against the real thing (journal 2026-10-04): `claude` is a `.cmd` wrapper (Windows) or an sh
    script (POSIX) that runs the fake as a CHILD and does not exec it. The runner ends its own child (the wrapper)
    with proc.kill() and nothing else, so the grandchild may live on: the lookup must not wait for it (its output goes
    to a file, not a pipe), and the test ends it by its pid. About 10 seconds by design."""

    def make_wrapper(self) -> Path:
        folder = self.tmp / "wrapbin"
        folder.mkdir()
        fake = self.w.tools.bin / ("claude.exe" if IS_WINDOWS else "claude")
        if IS_WINDOWS:
            (folder / "claude.cmd").write_bytes(f'@echo off\r\n"{fake}" %*\r\n'.encode("utf-8"))
        else:
            wrapper = folder / "claude"
            wrapper.write_text(f'#!/bin/sh\n"{fake}" "$@"; status=$?; exit $status\n', encoding="utf-8")  # sh cannot exec it
            wrapper.chmod(0o755)
        return folder

    def test_a_wrapper_whose_child_outlives_the_ceiling_is_ended_and_the_lookup_returns_in_time(self):
        self.module_with("HOLDER_TIMEOUT_SECONDS", "HOLDER_END_GRACE_SECONDS", "_run_holder_list", "_end_own_child")
        wrapdir = self.make_wrapper()
        path = str(wrapdir) + os.pathsep + self.w.tools.bin_dir_text + os.pathsep + os.environ.get("PATH", "")
        found = shutil.which("claude", path=path)
        self.assertIsNotNone(found, msg="fixture sanity: the wrapper is found as `claude`")
        self.assertEqual(os.path.dirname(os.path.realpath(found)).lower(), os.path.realpath(str(wrapdir)).lower(),
                         msg="fixture sanity: shutil.which picks the wrapper, not the fake beside it")
        pidfile = self.w.tools.bin / "claude_pid.txt"
        self.track_fake(pidfile)

        t0 = time.time()
        self.held_in_process([], env={"PATH": path})
        baseline = time.time() - t0
        set_claude(self.w.tools, [sess("bbfa6fec", self.w.fw)], sleep=60, pidfile=pidfile)
        t1 = time.time()
        started: list = []
        real_popen = subprocess.Popen

        class Recording(real_popen):
            def __init__(self, args, *a, **k):
                if is_holder_call(args):
                    started.append(list(args))
                super().__init__(args, *a, **k)

        rc, out, report = self.run_in_process(
            ["--dry-run"], env_extra={"CLAUDE_PROJECT_DIR": str(self.w.fw), "PATH": path},
            patches={"cleanup_delivered.HOLDER_TIMEOUT_SECONDS": 2, "cleanup_delivered.HOLDER_END_GRACE_SECONDS": 2,
                     "subprocess.Popen": Recording})
        elapsed = time.time() - t1

        # B7(3): prove the scenario ran. The grandchild wrote its pid and is STILL alive after the lookup returned.
        try:
            grandchild = int(pidfile.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            self.fail("scenario not exercised: the grandchild never wrote its pidfile, so the wrapper did not start the fake")
        if not pid_is_alive(grandchild, self.tmp):
            self.fail("scenario not exercised: the grandchild is not alive, so the lookup did not return while it lived on")
        self.assertEqual(len(started), 1, msg="exactly one `claude agents` child was started")
        self.assertEqual(_norm_text(started[0][0]), _norm_text(found),
                         msg="HN-2: the program started is the wrapper that production resolved (not the fake beside it)")
        self.assertIsInstance(report, dict, msg=f"the run must print a report, got {out[:300]!r}")
        item = pick(report, "worktree", FW_NAME)
        holders = item.get("holders") or {}
        self.assertEqual(holders.get("verdict"), "cannot-tell", msg=f"HN-3: a timed-out wrapper reads cannot-tell; item has {sorted(item)}")
        self.assertIn("claude agents gave no answer within", holders.get("reason", ""), msg="HN-3: with the timeout reason")
        self.assertLessEqual(elapsed - baseline, 2 + 2 + 3,
                             msg=f"HN-2: the lookup ends within ceiling + grace (+3 s) although the grandchild lives on; "
                                 f"the run took {elapsed:.1f}s, an ordinary run {baseline:.1f}s")


# ===========================================================================
# Holder reading, fast unit classes: no git world, real temp folders (A9)
# ===========================================================================
AGENTS_LIST_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "claude_agents_list.json"
OUTPUT_LIMIT = 4 * 1024 * 1024
UNREADABLE_REASON = "1 session records had no readable working folder"


class HolderUnitBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="holder_unit_")))
        self.addCleanup(rmtree_force, self.tmp)
        self.module = load_cleanup_module()
        need_names(self, self.module, "_read_session_list", "_holders_for", "_run_holder_list", "build_line", "_norm")
        self.main = self.tmp / "main_root"
        self.main.mkdir()
        self.tree = self.tmp / "trees" / FW_NAME
        (self.tree / "src").mkdir(parents=True)
        self.fake_exe = str(self.tmp / "fakebin" / ("claude.exe" if IS_WINDOWS else "claude"))

    def clean_session_env(self, extra: dict | None = None) -> None:
        for key in HOLDER_ENV_STRIPPED:
            os.environ.pop(key, None)
        os.environ.update(extra or {})

    def read(self, payload, *, env: dict | None = None, exe: str | None = None):
        """``_read_session_list`` with the runner patched to answer ``payload``; ``exe`` is what ``which`` finds."""
        text = payload if isinstance(payload, str) else json.dumps(payload)
        found = exe if exe is not None else self.fake_exe
        with mock.patch.dict(os.environ), mock.patch.object(self.module, "_run_holder_list", lambda e, c: ("answer", text)), \
                mock.patch("shutil.which", lambda name, *a, **k: found):
            self.clean_session_env(env)
            return self.module._read_session_list(str(self.main))

    def holders(self, payload, *, env: dict | None = None, tree: Path | None = None) -> dict:
        return self.module._holders_for(self.read(payload, env=env), str(tree or self.tree))

    def item(self, holders: dict, tree: Path | None = None) -> dict:
        return {"kind": "worktree", "path": str(tree or self.tree), "action": "deferred", "reason": "standing-tree",
                "files": [], "detail": None, "links": [], "identical": [], "holders": holders}

    def line(self, holders: dict, finish: str = "py -3 'x'") -> str:
        """Brackets and the rest are asserted through build_line with a short finish command, never a real long one."""
        return self.module.build_line(SLUG, [self.item(holders)], finish)

    @staticmethod
    def stops(line: str) -> list:
        return re.findall(r"; stop: (claude stop [^;]*)", line)


class HolderReadingUnitTests(HolderUnitBase):
    """The session variable (HN-7), the working-folder forms (A3), unreadable records (HN-4), forging (HN-6) and the
    stop list (HN-8), moved here from the end-to-end class. Fast: the runner is patched to return ("answer", payload)."""

    # -- the shape -------------------------------------------------------------------------------------
    def test_sess_builds_the_real_shape_and_every_real_state_reads_back(self):
        self.assertEqual(set(sess("0a1b2c3d", "x")), set(REAL_RECORD_KEYS), msg="A8: sess() writes exactly the real keys")
        for state in REAL_STATES:
            with self.subTest(state=state):
                holders = self.holders([sess("bbfa6fec", self.tree / "src", state=state, status="some status")])

                self.assertEqual(holders["sessions"][0]["state"], state, msg=f"A8: the state `{state}` is kept")
                self.assertIn(f'[held by bbfa6fec "worker" {state}]', self.line(holders))

    # -- HN-5: inside means the deferral's own comparison ---------------------------------------------
    def test_sessions_beside_the_tree_do_not_hold_it_and_the_reading_says_none_found_with_the_note(self):
        holders = self.holders([sess("bbfa6fec", str(self.tree) + "-2"), sess("cc00dd11", self.main)])

        self.assertEqual(holders.get("verdict"), "none-found", msg=f"HN-5: <tree>-2 and the main root are not inside; got {holders}")
        line = self.line(holders)
        self.assertIn(NONE_FOUND_BRACKET, line, msg="HN-8: the none-found bracket")
        self.assertIn(NOTE_TEXT, line, msg="HN-8: the fixed note")
        self.assertEqual(self.stops(line), [], msg="no holder, no stop command")

    # -- HN-7: the session variable --------------------------------------------------------------------
    def test_the_running_session_is_recognised_by_an_exact_session_id_and_gets_no_stop_command(self):
        holders = self.holders([sess("bbfa6fec", self.tree)], env={"CLAUDE_CODE_SESSION_ID": full_id("bbfa6fec")})

        self.assertEqual(holders.get("verdict"), "found")
        self.assertTrue(holders["sessions"][0].get("this_session"), msg="HN-7: sessionId equals CLAUDE_CODE_SESSION_ID exactly")
        self.assertTrue(holders.get("this_session_recognised"))
        line = self.line(holders)
        self.assertIn("[held by bbfa6fec (this session)]", line, msg="HN-8: written `<id> (this session)`")
        self.assertEqual(self.stops(line), [], msg="HN-7: the finish command covers it, so no stop for it")
        self.assertNotIn(WARNING_TEXT, line, msg="no stop is printed, so no warning")

    def test_with_a_second_holder_there_is_exactly_one_stop_and_no_warning_when_the_session_is_recognised(self):
        holders = self.holders([sess("bbfa6fec", self.tree), sess("cc00dd11", self.tree / "src", name="other")],
                               env={"CLAUDE_CODE_SESSION_ID": full_id("bbfa6fec")})

        line = self.line(holders)
        self.assertEqual(self.stops(line), ["claude stop cc00dd11"], msg="HN-7/HN-8: one stop, for the other session")
        self.assertNotIn(WARNING_TEXT, line, msg="HN-8: the session was recognised, so no warning")

    def test_two_holders_with_no_recognised_session_print_two_stops_and_the_fixed_warning_in_order(self):
        holders = self.holders([sess("bbfa6fec", self.tree), sess("cc00dd11", self.tree / "src", name="other")])

        line = self.line(holders)
        self.assertEqual(self.stops(line), ["claude stop bbfa6fec", "claude stop cc00dd11"],
                         msg="HN-8: one stop per distinct session, in first-seen order")
        self.assertIn(WARNING_TEXT, line, msg="HN-8: the fixed warning when the session was not recognised")
        self.assertIn(NOTE_TEXT, line, msg="HN-8: the fixed note is in the line")
        self.assertTrue(line.index(NOTE_TEXT) < line.index(WARNING_TEXT) < line.index("; stop: ") < line.index("; finish: "),
                        msg=f"HN-8 order: note, warning, stops, finish; the line is {line!r}")

    def test_an_unset_or_empty_session_variable_recognises_nobody_and_warns(self):
        for label, env in (("unset", {}), ("empty", {"CLAUDE_CODE_SESSION_ID": ""})):
            with self.subTest(variable=label):
                holders = self.holders([sess("bbfa6fec", self.tree)], env=env)

                line = self.line(holders)
                self.assertEqual(self.stops(line), ["claude stop bbfa6fec"], msg="HN-7: nobody is recognised, so the stop is printed")
                self.assertIn(WARNING_TEXT, line, msg="HN-7/HN-8: and the fixed warning follows")
                self.assertFalse(holders.get("this_session_recognised"), msg="not recognised")

    def test_only_claude_code_session_id_is_read_and_it_must_match_exactly(self):
        full = full_id("bbfa6fec")
        cases = {"CLAUDE_SESSION_ID": {"CLAUDE_SESSION_ID": full},
                 "CLAUDE_JOB_DIR": {"CLAUDE_JOB_DIR": str(self.tmp / "jobs" / "bbfa6fec")},
                 "CLAUDE_CODE_AGENT": {"CLAUDE_CODE_AGENT": "bbfa6fec"},
                 "upper-case CLAUDE_CODE_SESSION_ID": {"CLAUDE_CODE_SESSION_ID": full.upper()},
                 "padded CLAUDE_CODE_SESSION_ID": {"CLAUDE_CODE_SESSION_ID": " " + full}}
        for label, env in cases.items():
            with self.subTest(variable=label):
                holders = self.holders([sess("bbfa6fec", self.tree)], env=env)

                line = self.line(holders)
                self.assertFalse(holders["sessions"][0].get("this_session"), msg=f"HN-7: {label} does not make a session `this session`")
                self.assertEqual(self.stops(line), ["claude stop bbfa6fec"], msg="so its stop command is printed")
                self.assertIn(WARNING_TEXT, line, msg="and the warning with it")

    def test_two_records_with_the_running_session_id_recognise_nobody(self):
        holders = self.holders([sess("bbfa6fec", self.tree), sess("cc00dd11", self.tree, full=full_id("bbfa6fec"))],
                               env={"CLAUDE_CODE_SESSION_ID": full_id("bbfa6fec")})

        line = self.line(holders)
        self.assertFalse(holders.get("this_session_recognised"), msg="HN-7: the match counts only when exactly one record matches")
        self.assertEqual(sorted(self.stops(line)), ["claude stop bbfa6fec", "claude stop cc00dd11"], msg="both get a stop command")
        self.assertIn(WARNING_TEXT, line)

    # -- HN-6 and A6: an invalid id ---------------------------------------------------------------------
    def test_an_upper_case_id_fails_the_format_check_is_null_in_the_json_and_gets_no_stop_command(self):
        holders = self.holders([sess("BBFA6FEC", self.tree), sess("cc00dd11", self.tree, full="CC00DD11-0000-4000-8000-000000000000")],
                               env={"CLAUDE_CODE_SESSION_ID": "CC00DD11-0000-4000-8000-000000000000"})

        line = self.line(holders)
        self.assertEqual(holders.get("verdict"), "found", msg="HN-6: a holder with a bad id is still a holder")
        self.assertIn("a session with an unreadable id", line, msg="HN-6: shown as `a session with an unreadable id`")
        self.assertNotIn("BBFA6FEC", line, msg="HN-6: the bad id is not echoed")
        bad = [s for s in holders["sessions"] if s.get("id") is None]
        self.assertEqual(len(bad), 1, msg="A6: an invalid id is null in --json")
        self.assertEqual((bad[0].get("session_id"), bad[0].get("stop_command")), (None, None), msg="A6: and so are its session id and stop")
        self.assertNotIn("BBFA6FEC", json.dumps(holders), msg="A6: the invalid id is nowhere in the JSON")
        self.assertNotIn("claude stop BBFA6FEC", line, msg="HN-6: no stop command for it")
        second = [s for s in holders["sessions"] if s.get("id") == "cc00dd11"]
        self.assertEqual(len(second), 1, msg="the lower-case id is kept")
        self.assertFalse(second[0].get("this_session"), msg="HN-7: an upper-case sessionId fails its format check, so it is never matched")

    def test_every_stop_command_of_twenty_holders_is_printed_and_the_finish_command_stays_last_and_whole(self):
        ids = many_ids(20)

        holders = self.holders([sess(i, self.tree / "src", name="s" + i) for i in ids])

        finish = "py -3 'x' --contract 's'"
        line = self.line(holders, finish)
        self.assertEqual(self.stops(line), ["claude stop " + i for i in ids], msg="HN-8: all twenty stops, in order, never cut")
        self.assertEqual(line.count("; finish: "), 1, msg="exactly one finish part")
        self.assertTrue(line.endswith("; finish: " + finish), msg="the finish command is last and whole")
        self.assertNotIn("\n", line, msg="one line")

    # -- HN-5 / A3: the working-folder forms -----------------------------------------------------------
    def test_a_session_whose_folder_reaches_the_tree_through_a_link_holds_it_like_the_deferral_says(self):
        link = self.tmp / "via_link"
        try:
            make_directory_link(link, self.tree)
        except (OSError, NotImplementedError, ImportError) as exc:
            self.skipTest(f"a directory link cannot be made on this host: {exc}")
        self.addCleanup(drop_link, link)

        holders = self.holders([sess("bbfa6fec", link / "src")])

        self.assertEqual(holders.get("verdict"), "found", msg="HN-5: the holder match is the deferral's own _inside")

    @unittest.skipUnless(IS_WINDOWS, "case folding is Windows behaviour")
    def test_a_changed_case_still_reaches_the_tree(self):
        for label, cwd in (("upper case", str(self.tree).upper() + "\\src"), ("lower case", str(self.tree).lower())):
            with self.subTest(form=label):
                self.assertEqual(self.holders([sess("bbfa6fec", cwd)]).get("verdict"), "found",
                                 msg=f"HN-5: {label} compares like the deferral does")

    @unittest.skipUnless(IS_WINDOWS, "short (8.3) names are Windows behaviour")
    def test_a_short_8_3_name_still_reaches_the_tree(self):
        import ctypes
        buf = ctypes.create_unicode_buffer(1024)
        n = ctypes.windll.kernel32.GetShortPathNameW(str(self.tree), buf, 1024)
        short = buf.value if n else ""
        if not short or short.lower() == str(self.tree).lower():
            self.skipTest("this volume gave no 8.3 short form for the test folder (GetShortPathNameW): the case is not exercised here")

        self.assertEqual(self.holders([sess("bbfa6fec", short + "\\src")]).get("verdict"), "found",
                         msg="HN-5: the short name compares like the deferral does")

    @unittest.skipUnless(IS_WINDOWS, "the Git Bash drive form is a Windows form")
    def test_the_git_bash_drive_form_is_accepted_on_windows(self):
        fw = str(self.tree)
        git_bash = "/" + fw[0].lower() + fw[2:].replace("\\", "/") + "/src"

        self.assertEqual(self.holders([sess("bbfa6fec", git_bash)]).get("verdict"), "found", msg="A3: /x/... is rewritten, then compared")

    @unittest.skipUnless(IS_WINDOWS, "/tmp and /cygdrive are unaccepted on Windows; on POSIX they are ordinary absolute paths")
    def test_unaccepted_windows_path_forms_make_the_record_unreadable_and_the_answer_cannot_tell(self):
        for cwd in ("/tmp/x", "/cygdrive/c/x"):
            with self.subTest(cwd=cwd):
                holders = self.holders([sess("bbfa6fec", cwd)])

                self.assertEqual(holders.get("verdict"), "cannot-tell", msg="HN-4: an unreadable record is not proof of absence")
                self.assertEqual(holders.get("reason"), UNREADABLE_REASON)

    @unittest.skipUnless(IS_WINDOWS, "UNC and device forms are Windows forms")
    def test_unc_and_device_forms_are_unreadable_and_never_reach_realpath(self):
        fw = str(self.tree)
        forms = {"UNC": "\\\\host\\share\\x", "extended UNC": "\\\\?\\UNC\\host\\share\\x", "device": "\\\\.\\C:\\x",
                 "extended drive": "\\\\?\\" + fw + "\\src", "forward-slash UNC": "//host/share/x", "forward-slash extended": "//?/UNC/host/share/x"}
        real_rp = os.path.realpath
        for label, cwd in forms.items():
            with self.subTest(form=label):
                seen: list = []

                def realpath(path, *a, **k):
                    text = os.fspath(path)
                    if text.replace("/", "\\").startswith("\\\\"):
                        seen.append(text)  # never ask the system: a network path may hang or leak a credential
                        return text
                    return real_rp(path, *a, **k)

                with mock.patch("os.path.realpath", realpath):
                    holders = self.holders([sess("bbfa6fec", cwd)])

                self.assertEqual(seen, [], msg=f"A3 ({label}): os.path.realpath is never called with such text; saw {seen}")
                self.assertEqual((holders.get("verdict"), holders.get("reason")), ("cannot-tell", UNREADABLE_REASON),
                                 msg=f"A3 ({label}): an unreadable record and no match reads cannot-tell")

    def test_records_without_a_readable_working_folder_never_read_as_none_found(self):
        variants = {"relative path": {"cwd": "relative/dir"}, "empty": {"cwd": ""}, "a number": {"cwd": 5}, "missing": {"drop": ("cwd",)}}
        for label, spec in variants.items():
            with self.subTest(record=label):
                record = sess("bbfa6fec", "placeholder", drop=spec.get("drop", ()))
                if "cwd" in spec:
                    record["cwd"] = spec["cwd"]  # set after sess(), which would turn a number into text

                holders = self.holders([record])

                self.assertEqual(holders.get("verdict"), "cannot-tell", msg=f"HN-4 ({label}): no match and one unreadable record is cannot-tell, never none-found")
                self.assertEqual(holders.get("reason"), UNREADABLE_REASON)
                self.assertIn(f"[cannot tell which session holds it: {UNREADABLE_REASON}]", self.line(holders))

    def test_a_working_folder_with_a_nul_a_control_character_or_the_replacement_character_is_unreadable_on_every_platform(self):
        base = str(self.tree / "src")
        for label, bad in (("NUL", "\x00"), ("start of heading", "\x01"), ("line feed", "\n"), ("escape", "\x1b"), ("delete", "\x7f"),
                           ("C1 next line", "\x85"), ("replacement character", "\ufffd")):
            with self.subTest(character=label):
                holders = self.holders([sess("bbfa6fec", base + bad + "x")])

                self.assertEqual((holders.get("verdict"), holders.get("reason")), ("cannot-tell", UNREADABLE_REASON),
                                 msg=f"A3 ({label}): the record is unreadable (even inside the tree), no match, so cannot-tell; got {holders}")

    def test_an_unreadable_record_beside_a_matching_one_still_names_the_holder(self):
        for label, bad in (("relative", "relative/dir"), ("NUL", str(self.tree) + "\x00x")):
            with self.subTest(unreadable=label):
                holders = self.holders([sess("cc00dd11", bad), sess("bbfa6fec", self.tree)])

                self.assertEqual(holders.get("verdict"), "found", msg="HN-4: the holders it can match are named")
                self.assertEqual(self.stops(self.line(holders)), ["claude stop bbfa6fec"])

    def test_a_byte_order_mark_or_a_banner_line_before_the_list_reads_cannot_tell_with_the_form_reason(self):
        banner_record = "note: x\n" + json.dumps([sess("bbfa6fec", self.tree)])
        for label, text in (("byte order mark", "\ufeff[]"), ("banner line", "Welcome to claude\n[]"), ("banner, then a record", banner_record)):
            with self.subTest(before_the_list=label):
                reading = self.read(text)

                self.assertEqual((reading["verdict"], reading.get("reason")), ("cannot-tell", REASON_FORM),
                                 msg=f"A8: anything before the list is `not in the expected form`, never a guess; got {reading}")

    @unittest.skipUnless(IS_WINDOWS, "a drive path written with forward slashes is a Windows form")
    def test_a_drive_path_written_with_forward_slashes_is_accepted_on_windows(self):
        cwd = str(self.tree / "src").replace("\\", "/")
        self.assertRegex(cwd, r"^[A-Za-z]:/", msg="fixture sanity: C:/x form")

        holders = self.holders([sess("bbfa6fec", cwd)])

        self.assertEqual(holders.get("verdict"), "found", msg=f"A3: `C:/x` is an accepted form on Windows; got {holders}")

    def test_pid_and_status_are_ignored_a_holder_carries_neither(self):
        reading = self.read([sess("bbfa6fec", self.tree, pid=987654, status="Idle SECRETSTATUS")])

        holders = self.module._holders_for(reading, str(self.tree))

        self.assertEqual(holders.get("verdict"), "found")
        for holder in holders["sessions"]:
            self.assertFalse({"pid", "status"} & set(holder), msg=f"a Holder carries neither pid nor status; keys are {sorted(holder)}")
        text = json.dumps(holders) + self.line(holders)
        self.assertNotIn("987654", text, msg="the pid is nowhere in the reading or the line")
        self.assertNotIn("SECRETSTATUS", text, msg="the status text is nowhere in the reading or the line")

    def test_started_at_is_kept_only_for_a_real_integer_and_is_null_otherwise(self):
        cases = {"integer": (1760000000000, 1760000000000), "text": ("1760000000000", None), "float": (1.5, None),
                 "boolean true": (True, None), "boolean false": (False, None), "null": (None, None), "list": ([1], None)}
        for label, (value, expected) in cases.items():
            with self.subTest(startedAt=label):
                record = sess("bbfa6fec", self.tree)
                record["startedAt"] = value

                holders = self.holders([record])

                self.assertEqual(holders["sessions"][0]["started_at"], expected, msg=f"B2: startedAt as {label} reads {expected!r}")
        missing = self.holders([sess("bbfa6fec", self.tree, drop=("startedAt",))])
        self.assertIsNone(missing["sessions"][0]["started_at"], msg="B2: a missing startedAt is null")

    def test_fields_that_fail_their_check_are_null_in_the_json_and_text_fields_are_empty_text(self):
        record = sess("bbfa6fec", self.tree, drop=("name", "state", "kind"))
        record["id"], record["sessionId"], record["startedAt"] = "BBFA6FEC", "not-a-session-id", "soon"

        holders = self.holders([record])

        one = holders["sessions"][0]
        self.assertEqual((one["id"], one["session_id"], one["started_at"]), (None, None, None),
                         msg="B2: id, session_id and started_at are null in --json when their check fails")
        self.assertEqual((one["name"], one["state"], one["kind"]), ("", "", ""),
                         msg="B2: name, state and kind are empty text (never null) when missing")
        self.assertIsNone(one["stop_command"], msg="and there is no stop command for it")

        non_text = {"true": True, "false": False, "number": 5, "list": ["x"], "object": {"a": 1}, "null": None}
        for field in ("name", "state", "kind"):
            for label, value in non_text.items():
                with self.subTest(field=field, non_text=label):
                    record = sess("bbfa6fec", self.tree)
                    record[field] = value  # set after sess(): the value must stay what it is

                    one = self.holders([record])["sessions"][0]

                    self.assertEqual(one[field], "",
                                     msg=f"D3: `{field}` that is not a string ({label}) reads as empty text, never as its printed form; got {one[field]!r}")
                    holders = self.holders([record])
                    line = self.line(holders)
                    self.assertIn("[held by bbfa6fec", line, msg="D3: the holder is still named")
                    self.assertNotIn("True", line, msg=f"D3: a {label} {field} never turns into text in the line")
                    self.assertNotIn("{'a'", line, msg=f"D3: a {label} {field} never turns into text in the line")
                    self.assertNotIn("['x']", line, msg=f"D3: a {label} {field} never turns into text in the line")
                    self.assertNotIn("False", line, msg=f"D3: a {label} {field} never turns into text in the line")
                    expected = {"name": "[held by bbfa6fec done]", "state": '[held by bbfa6fec "worker"]',
                                "kind": '[held by bbfa6fec "worker" done]'}[field]
                    self.assertIn(expected, line, msg=f"D3: an empty {field} adds nothing to the holder's words; line {line!r}")

    def test_invisible_and_direction_marks_are_removed_from_name_state_and_kind(self):
        marks = {"U+200E": "\u200e", "U+200F": "\u200f", "U+061C": "\u061c", "U+200B": "\u200b", "U+FEFF": "\ufeff"}
        for label, mark in marks.items():
            with self.subTest(mark=label):
                holders = self.holders([sess("bbfa6fec", self.tree, name="wo" + mark + "rk", state="do" + mark + "ne", kind="back" + mark + "ground")])

                one = holders["sessions"][0]
                self.assertEqual((one["name"], one["state"], one["kind"]), ("work", "done", "background"),
                                 msg=f"B4: {label} is removed from name, state and kind; got {ascii((one['name'], one['state'], one['kind']))}")
                self.assertIn('[held by bbfa6fec "work" done]', self.line(holders), msg=f"B4: and from the line ({label})")
                self.assertNotIn(mark, json.dumps(holders, ensure_ascii=False), msg=f"B4: and from the JSON text ({label})")

    def test_all_five_marks_in_one_name_leave_only_the_letters(self):
        name = "a\u200eb\u200fc\u061cd\u200be\ufeffg"

        holders = self.holders([sess("bbfa6fec", self.tree, name=name, state=name, kind=name)])

        one = holders["sessions"][0]
        self.assertEqual((one["name"], one["state"], one["kind"]), ("abcdeg",) * 3, msg=f"B4: got {ascii((one['name'], one['state'], one['kind']))}")

    # -- D2: cleaning by category (NFKC, then Cc Cf Zl Zp dropped, then ; " [ ] replaced, then cut to 60) -------
    FORMAT_CHARS = {"tag character U+E0041": "\U000e0041", "zero width non-joiner U+200C": "‌",
                    "zero width joiner U+200D": "‍", "word joiner U+2060": "⁠", "soft hyphen U+00AD": "­",
                    "mongolian vowel separator U+180E": "᠎", "interlinear anchor U+FFF9": "￹"}

    def test_d2_every_format_character_is_removed_from_name_state_and_kind_wherever_it_sits(self):
        for label, mark in self.FORMAT_CHARS.items():
            with self.subTest(character=label):
                holders = self.holders([sess("bbfa6fec", self.tree, name="wo" + mark + "rk", state="do" + mark + "ne",
                                             kind="back" + mark + "ground")])

                one = holders["sessions"][0]
                self.assertEqual((one["name"], one["state"], one["kind"]), ("work", "done", "background"),
                                 msg=f"D2: {label} is a Cf character and is dropped; got {ascii((one['name'], one['state'], one['kind']))}")
                self.assertIn('[held by bbfa6fec "work" done]', self.line(holders), msg=f"D2: and from the line ({label})")
                self.assertNotIn(mark, json.dumps(holders, ensure_ascii=False), msg=f"D2: and from the JSON text ({label})")

    def test_d2_all_format_characters_in_one_name_leave_only_the_letters(self):
        name = "a\U000e0041b‌c‍d⁠e­f᠎g￹h"

        one = self.holders([sess("bbfa6fec", self.tree, name=name, state=name, kind=name)])["sessions"][0]

        self.assertEqual((one["name"], one["state"], one["kind"]), ("abcdefgh",) * 3, msg=f"D2: got {ascii((one['name'], one['state'], one['kind']))}")

    def test_d2_a_lookalike_separator_cannot_forge_a_stop_part(self):
        for label, mark in (("Greek question mark U+037E", ";"), ("fullwidth semicolon U+FF1B", "；")):
            with self.subTest(lookalike=label):
                name = "x" + mark + " stop: claude stop deadbeef"

                holders = self.holders([sess("bbfa6fec", self.tree, name=name)])

                line = self.line(holders)
                self.assertEqual(self.stops(line), ["claude stop bbfa6fec"], msg=f"D2: only the real stop command is a stop part; line {line!r}")
                self.assertEqual(line.count("; stop: "), 1, msg=f"D2: no second `; stop:` part appears; line {line!r}")
                self.assertNotIn(mark, line, msg="D2: NFKC turns the lookalike into `;` first, so it is replaced like one")
                self.assertEqual(holders["sessions"][0]["name"], "x, stop: claude stop deadbeef",
                                 msg=f"D2: NFKC, then `;` becomes `,`; got {holders['sessions'][0]['name']!r}")

    def test_d2_compatibility_forms_of_the_replaced_characters_are_replaced_too(self):
        name = "a＂b［c］ﬁ"

        one = self.holders([sess("bbfa6fec", self.tree, name=name)])["sessions"][0]

        self.assertEqual(one["name"], "a'b(c)fi", msg=f"D2: NFKC maps fullwidth quote and brackets and the fi ligature before the replacement; got {one['name']!r}")

    def test_d2_the_cut_to_60_comes_after_the_removal(self):
        name = "‌" * 80 + "z" * 70

        one = self.holders([sess("bbfa6fec", self.tree, name=name)])["sessions"][0]

        self.assertEqual(one["name"], "z" * 60, msg=f"D2: format characters are dropped before the cut, so 60 letters remain; got {len(one['name'])} characters")

    # -- HN-6: forging -----------------------------------------------------------------------------------
    def test_text_from_the_list_is_cleaned_before_it_is_shown_and_cannot_forge_a_part_of_the_line(self):
        name = 'x; finish: rm -rf ~"]\n\u2028\x1b[31m\u202e' + "y" * 200
        state = 'run;ning[x]"\u0085\x07'

        holders = self.holders([sess("bbfa6fec", self.tree, name=name, state=state, kind="k;[i]\"nd")])

        finish = "py -3 'x'"
        line = self.line(holders, finish)
        self.assertEqual(line.count("; finish: "), 1, msg="HN-6: the name cannot add a finish part")
        self.assertTrue(line.endswith("; finish: " + finish), msg="the real finish command is last")
        self.assertIsNone(re.search("[\x00-\x1f\x7f-\x9f\u2028\u2029\u202a-\u202e\u2066-\u2069]", line), msg=f"HN-6: no control or separator character in {line!r}")
        self.assertEqual(self.stops(line), ["claude stop bbfa6fec"], msg="and no extra stop part")
        h = holders["sessions"][0]
        for field in ("name", "state", "kind"):
            self.assertIsNone(re.search(r"[;\"\[\]\x00-\x1f\x7f-\x9f\u2028\u2029\u202a-\u202e\u2066-\u2069]", h.get(field) or ""),
                              msg=f"HN-6: `{field}` has `;` `\"` `[` `]` and control characters replaced or removed; got {h.get(field)!r}")
        self.assertTrue(0 < len(h.get("name") or "") <= 60, msg=f"HN-6: the name is cut to 60 characters; got {len(h.get('name') or '')}")
        self.assertIn("rm -rf ~'", h["name"], msg="the readable part survives, with `\"` turned into `'`")


class HolderRunnerFakeTests(HolderUnitBase):
    """The real runner against the fake `claude` (a real executable, no git world): raw bytes, the output limit, the
    safe resolution of the command and the committed real-shape fixture."""

    def setUp(self) -> None:
        super().setUp()
        self.tools = Tools(self.tmp)
        install_fake_claude(self.tools)
        self.fake_exe = str(self.tools.bin / ("claude.exe" if IS_WINDOWS else "claude"))

    def read_real(self, *, raw: bytes | None = None, sessions=None, pad_to: int = 0, env: dict | None = None):
        set_claude(self.tools, sessions, raw=raw, pad_to=pad_to)
        with mock.patch.dict(os.environ), mock.patch("shutil.which", lambda name, *a, **k: self.fake_exe):
            self.clean_session_env(env)
            return self.module._read_session_list(str(self.main))

    @staticmethod
    def raw_list(records: list) -> bytes:
        return json.dumps(records, ensure_ascii=False).encode("utf-8")

    # -- A8: raw UTF-8 -----------------------------------------------------------------------------------
    def test_a_non_ascii_worktree_path_sent_as_raw_utf_8_reads_found(self):
        tree = self.tmp / "w\u00f6rk-\u00fc-\u65e5\u672c" / FW_NAME
        (tree / "src").mkdir(parents=True)
        raw = self.raw_list([sess("bbfa6fec", tree / "src", name="\u00dcberpr\u00fcfung \u2713")])
        self.assertIsNone(re.search(rb"\\u[0-9a-fA-F]{4}", raw), msg="fixture sanity: the bytes are raw UTF-8, not ASCII-escaped")

        reading = self.read_real(raw=raw)

        holders = self.module._holders_for(reading, str(tree))
        self.assertEqual(reading["verdict"], "read", msg=f"A8: raw UTF-8 is a readable answer; got {reading}")
        self.assertEqual(holders.get("verdict"), "found", msg=f"A8: a non-ASCII worktree path sent raw reads found; got {holders}")
        self.assertEqual(holders["sessions"][0]["name"], "\u00dcberpr\u00fcfung \u2713", msg="and the non-ASCII name arrives intact")

    def test_invalid_utf_8_inside_a_working_folder_reads_cannot_tell(self):
        prefix = json.dumps(str(self.tmp / "elsewhere"))[1:-1].encode("utf-8")
        raw = (b'[{"cwd": "' + prefix + b'\xff\xfe", "id": "bbfa6fec", "sessionId": "' + full_id("bbfa6fec").encode()
               + b'", "kind": "background", "name": "w", "pid": 1, "startedAt": 1, "state": "done", "status": "x"}]')

        reading = self.read_real(raw=raw)

        holders = self.module._holders_for(reading, str(self.tree))
        self.assertEqual(holders.get("verdict"), "cannot-tell",
                         msg=f"A8: bytes that are not UTF-8 in a working folder are never read as `none-found`; got {holders}")

    def test_the_unpatched_ceiling_constants_and_the_real_timeout_reason(self):
        """B7(1): nothing patched but the runner, which answers `timeout`: the reason text carries the REAL ceiling."""
        self.assertEqual(self.module.HOLDER_TIMEOUT_SECONDS, 15, msg="HN-2: the ceiling is 15 seconds")
        self.assertEqual(self.module.HOLDER_END_GRACE_SECONDS, 5, msg="HN-2: the grace after the kill is 5 seconds")
        with mock.patch.dict(os.environ), mock.patch.object(self.module, "_run_holder_list", lambda e, c: ("timeout", "")), \
                mock.patch("shutil.which", lambda name, *a, **k: self.fake_exe):
            self.clean_session_env()
            reading = self.module._read_session_list(str(self.main))

        self.assertEqual((reading["verdict"], reading.get("reason")), ("cannot-tell", "claude agents gave no answer within 15 seconds"),
                         msg="HN-3: the real reason text, with the real number")

    def test_a_byte_order_mark_in_front_of_the_list_bytes_reads_cannot_tell_with_the_form_reason(self):
        reading = self.read_real(raw=b"\xef\xbb\xbf[]")

        self.assertEqual((reading["verdict"], reading.get("reason")), ("cannot-tell", REASON_FORM),
                         msg="A8: a UTF-8 byte order mark before the list is `not in the expected form`")

    def recorded_start(self, *, env: dict | None = None):
        """``_read_session_list`` with the real runner and the real fake, ``subprocess.Popen`` recording the holder call."""
        seen: list = []
        real_popen = subprocess.Popen

        class Recording(real_popen):
            def __init__(self, args, *a, **k):
                seen.append((list(args) if isinstance(args, (list, tuple)) else [str(args)], dict(k)))
                super().__init__(args, *a, **k)

        set_claude(self.tools, [])
        with mock.patch.dict(os.environ), mock.patch("shutil.which", lambda name, *a, **k: self.fake_exe), \
                mock.patch("subprocess.Popen", Recording):
            self.clean_session_env(env)
            reading = self.module._read_session_list(str(self.main))
        return reading, seen

    def test_claude_is_started_in_the_folder_that_holds_it_not_in_the_main_checkout(self):
        reading, seen = self.recorded_start()

        self.assertEqual(reading["verdict"], "read", msg=f"fixture sanity: the lookup ran; got {reading}")
        self.assertEqual(len(seen), 1, msg="exactly one start")
        argv, kwargs = seen[0]
        self.assertEqual(argv[0], self.fake_exe, msg="fixture sanity: the program started is the one resolved")
        self.assertIn("cwd", kwargs, msg="B1: the start names a working folder")
        self.assertEqual(_norm_text(kwargs.get("cwd")), _norm_text(os.path.dirname(self.fake_exe)),
                         msg="B1: the working folder is the folder that holds the resolved claude program")
        self.assertNotEqual(_norm_text(kwargs.get("cwd")), _norm_text(str(self.main)), msg="B1: and never the main checkout")

    def test_the_start_passes_no_environment_argument_at_all(self):
        """Design decision: no environment variable is a mechanism. The child inherits the unchanged environment,
        so the start must not hand `env` to Popen (an invented variable would need one)."""
        reading, seen = self.recorded_start()

        self.assertEqual(reading["verdict"], "read", msg=f"fixture sanity: the lookup ran; got {reading}")
        self.assertEqual(len(seen), 1, msg="exactly one start")
        kwargs = seen[0][1]
        self.assertNotIn("env", kwargs, msg="B1: the start passes no `env` argument; the child inherits the unchanged environment")

    @unittest.skipUnless(IS_WINDOWS, "a .cmd wrapper that runs a bare `node` is the Windows shape of the install")
    def test_a_cmd_wrapper_that_runs_a_bare_node_never_runs_a_node_planted_in_the_main_checkout(self):
        """B1 against the real thing: `claude.cmd` calls `node`; cmd.exe looks in the current folder first, so the
        current folder of the child must be the wrapper's own folder, never the main checkout."""
        wrapdir = self.tmp / "wrapbin"
        wrapdir.mkdir()
        write_exe(wrapdir, "node", FAKE_CLAUDE_CODE)  # the real interpreter the wrapper means
        (wrapdir / "claude.cmd").write_bytes(b'@echo off\r\nnode %*\r\n')
        set_claude(SimpleNamespace(bin=wrapdir), [])
        marker = self.tmp / "planted_node_ran.txt"
        planted = f"import sys\nopen({str(marker)!r}, 'w').write('ran')\nsys.stdout.write('[]')\n"
        write_exe(self.main, "node", planted)
        (self.main / "node.cmd").write_bytes(f'@echo off\r\necho ran>"{marker}"\r\necho []\r\n'.encode("utf-8"))
        elsewhere = self.tmp / "other_cwd"
        elsewhere.mkdir()
        path = str(wrapdir) + os.pathsep + os.environ.get("PATH", "")
        with mock.patch.dict(os.environ):
            # Test setup, not product behaviour: model a normal user shell, where the variable is unset.
            os.environ.pop("NoDefaultCurrentDirectoryInExePath", None)
            self.clean_session_env({"PATH": path})
            found = shutil.which("claude")
            self.assertEqual(os.path.normcase(os.path.dirname(found or "")), os.path.normcase(str(wrapdir)), msg="fixture sanity: the wrapper is found as `claude`")
            saved = os.getcwd()
            os.chdir(str(elsewhere))
            try:
                reading = self.module._read_session_list(str(self.main))
            finally:
                os.chdir(saved)

        self.assertFalse(marker.exists(), msg="B1: a node planted in the main checkout must never run")
        self.assertEqual(reading["verdict"], "read", msg=f"B1: the node beside the wrapper answered; got {reading}")
        logged = wrapdir / "claude_calls.jsonl"
        calls = [json.loads(l) for l in logged.read_text(encoding="utf-8").splitlines() if l.strip()] if logged.exists() else []
        self.assertEqual([c["args"] for c in calls], [STOP_ARGV], msg="B1: the interpreter in the wrapper's folder ran once, as `agents --json --all`")

    # -- A4: the output limit ---------------------------------------------------------------------------
    def test_the_output_limit_constant_is_four_mebibytes(self):
        need_names(self, self.module, "HOLDER_OUTPUT_LIMIT_BYTES")
        self.assertEqual(self.module.HOLDER_OUTPUT_LIMIT_BYTES, OUTPUT_LIMIT, msg="A4: the runner reads at most 4 MiB")

    def test_an_answer_of_more_than_four_mebibytes_is_not_in_the_expected_form(self):
        reading = self.read_real(sessions=[], pad_to=OUTPUT_LIMIT + 1)

        self.assertEqual((reading["verdict"], reading.get("reason")), ("cannot-tell", REASON_FORM),
                         msg="A4: one byte over 4 MiB is `not in the expected form`")

    def test_an_answer_of_exactly_four_mebibytes_is_still_read(self):
        reading = self.read_real(sessions=[], pad_to=OUTPUT_LIMIT)

        self.assertEqual(reading["verdict"], "read", msg="A4: at most 4 MiB is read (the boundary itself is inside)")

    # -- A2: the claude command is resolved safely --------------------------------------------------------
    def test_a_resolved_command_that_is_relative_or_sits_in_the_main_root_or_the_current_folder_is_not_used(self):
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        cases = {"relative": "claude", "main root": str(self.main / "claude.exe"),
                 "main root spelled with ..": str(self.main) + os.sep + ".." + os.sep + self.main.name + os.sep + "claude.exe",
                 "current folder": str(elsewhere / "claude.exe")}
        for label, exe in cases.items():
            with self.subTest(resolved=label):
                saved = os.getcwd()
                os.chdir(str(elsewhere))
                try:
                    reading = self.read([], exe=exe)
                finally:
                    os.chdir(saved)

                self.assertEqual((reading["verdict"], reading.get("reason")), ("cannot-tell", REASON_NOT_FOUND),
                                 msg=f"A2 ({label}): accepted only if absolute and in neither the current folder nor the main root")

    def test_d4_a_path_entry_that_is_not_a_hit_is_never_resolved_through_the_file_system(self):
        stale = [str(self.tmp / "stale_one"), str(self.tmp / "stale_two")]  # absolute, and not on disk
        resolved: list = []
        real_norm, real_rp = self.module._norm, os.path.realpath

        def norm(path):
            resolved.append(os.fspath(path))
            return real_norm(path)

        def realpath(path, *a, **k):
            resolved.append(os.fspath(path))
            return real_rp(path, *a, **k)

        with mock.patch.dict(os.environ), mock.patch("shutil.which", lambda name, *a, **k: None), \
                mock.patch.object(self.module, "_norm", norm), mock.patch("os.path.realpath", realpath):
            self.clean_session_env({"PATH": os.pathsep.join(stale)})
            reading = self.module._read_session_list(str(self.main))

        self.assertEqual((reading["verdict"], reading.get("reason")), ("cannot-tell", REASON_NOT_FOUND),
                         msg=f"fixture sanity: with nothing on PATH the command is not found; got {reading}")
        touched = [p for p in resolved if any(os.path.normcase(p).startswith(os.path.normcase(s)) for s in stale)]
        self.assertEqual(touched, [],
                         msg=f"D4: only the current folder and the main root may be resolved, never a PATH entry that is not a hit; resolved {resolved}")

    def test_a_resolved_command_in_a_third_folder_is_used(self):
        reading = self.read([])

        self.assertEqual(reading["verdict"], "read", msg="A2: an absolute command in some other folder is fine")

    def plant(self, folder: Path, marker: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        if IS_WINDOWS:
            for ext in (".cmd", ".bat"):
                (folder / ("claude" + ext)).write_bytes(f'@echo off\r\necho ran>"{marker}"\r\necho []\r\n'.encode("utf-8"))
        else:
            planted = folder / "claude"
            planted.write_text(f'#!/bin/sh\necho ran > "{marker}"\necho "[]"\n', encoding="utf-8")
            planted.chmod(0o755)

    def read_resolving(self, *, cwd: Path, planted_in: Path, path_env: str):
        """The real ``shutil.which`` and the real runner, NoDefaultCurrentDirectoryInExePath UNSET."""
        marker = self.tmp / "planted_ran.txt"
        marker.unlink(missing_ok=True)
        (self.tools.bin / "claude_calls.jsonl").unlink(missing_ok=True)
        self.plant(planted_in, marker)
        with mock.patch.dict(os.environ):
            # Test setup, not product behaviour: model a normal user shell, where the variable is unset.
            os.environ.pop("NoDefaultCurrentDirectoryInExePath", None)
            self.clean_session_env({"PATH": path_env})
            saved = os.getcwd()
            os.chdir(str(cwd))
            try:
                reading = self.module._read_session_list(str(self.main))
            finally:
                os.chdir(saved)
        return reading, marker

    def test_a_planted_claude_in_the_main_root_or_the_current_folder_never_runs_and_the_one_on_path_is_used(self):
        other = self.tmp / "other_cwd"
        other.mkdir()
        fake_path = self.tools.bin_dir_text + os.pathsep + os.environ.get("PATH", "")
        cases = {"planted in the main root, started there": (self.main, self.main, fake_path if IS_WINDOWS else str(self.main) + os.pathsep + fake_path),
                 "planted in the current folder": (other, other, fake_path if IS_WINDOWS else str(other) + os.pathsep + fake_path)}
        for label, (cwd, planted_in, path_env) in cases.items():
            with self.subTest(case=label):
                reading, marker = self.read_resolving(cwd=cwd, planted_in=planted_in, path_env=path_env)

                self.assertFalse(marker.exists(), msg=f"A2 ({label}): the planted claude must never run")
                self.assertEqual(reading["verdict"], "read", msg=f"A2 ({label}): the fake claude on PATH is used; got {reading}")
                self.assertEqual([c["args"] for c in claude_calls(self.tools)], [STOP_ARGV], msg="and it was called once, as `agents --json --all`")

    def test_when_only_a_planted_claude_exists_nothing_runs_and_the_reading_says_the_command_was_not_found(self):
        empty = self.tmp / "emptybin"
        empty.mkdir()

        reading, marker = self.read_resolving(cwd=self.main, planted_in=self.main, path_env=str(empty) if IS_WINDOWS else str(self.main))

        self.assertFalse(marker.exists(), msg="A2: the planted claude must never run")
        self.assertEqual((reading["verdict"], reading.get("reason")), ("cannot-tell", REASON_NOT_FOUND),
                         msg="A2: no safe claude command, so the lookup says it was not found")

    # -- A8: the committed real-shape fixture --------------------------------------------------------------
    def test_the_committed_real_shape_list_is_read_end_to_end_and_names_its_holders(self):
        self.assertTrue(AGENTS_LIST_FIXTURE.is_file(), msg=f"A8: the fixture {AGENTS_LIST_FIXTURE} is committed")
        data = AGENTS_LIST_FIXTURE.read_bytes()
        self.assertFalse(data.startswith(b"\xef\xbb\xbf"), msg="A8: no BOM")
        self.assertIsNone(re.search(rb"\\u[0-9a-fA-F]{4}", data), msg="A8: raw UTF-8, not ASCII-escaped")
        text = data.decode("utf-8")
        self.assertTrue(any(ord(c) > 127 for c in text), msg="A8: it holds a non-ASCII session name")
        listed = json.loads(text)
        self.assertIsInstance(listed, list, msg="A8: a bare list")
        self.assertEqual(len(listed), 4)
        for rec in listed:
            self.assertEqual(set(rec), set(REAL_RECORD_KEYS), msg="A8: exactly the real keys")
            self.assertIsInstance(rec["cwd"], str)
            self.assertRegex(rec["id"], r"^[0-9a-f]{8}$")
            self.assertEqual(rec["kind"], "background")
            self.assertIsInstance(rec["name"], str)
            self.assertIs(type(rec["pid"]), int)
            self.assertRegex(rec["sessionId"], r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
            self.assertIs(type(rec["startedAt"]), int)
            self.assertIn(rec["state"], REAL_STATES)
            self.assertIsInstance(rec["status"], str)
        self.assertEqual({r["state"] for r in listed}, set(REAL_STATES), msg="A8: all four states appear")
        listed[0]["cwd"], listed[1]["cwd"] = str(self.tree / "src"), str(self.tree)
        listed[2]["cwd"], listed[3]["cwd"] = str(self.tmp / "elsewhere"), str(self.main)

        reading = self.read_real(raw=self.raw_list(listed), env={"CLAUDE_CODE_SESSION_ID": listed[1]["sessionId"]})

        holders = self.module._holders_for(reading, str(self.tree))
        self.assertEqual(reading["verdict"], "read", msg=f"the real shape is a readable answer; got {reading}")
        self.assertEqual(reading["this_session"], listed[1]["sessionId"], msg="HN-7: the running session is recognised")
        self.assertEqual(holders["verdict"], "found")
        self.assertEqual([(s["id"], s["name"], s["state"]) for s in holders["sessions"]],
                         [(listed[0]["id"], listed[0]["name"], "working"), (listed[1]["id"], listed[1]["name"], "blocked")],
                         msg="exactly the two sessions inside the tree, with their names and states")
        self.assertEqual(self.stops(self.line(holders)), ["claude stop " + listed[0]["id"]], msg="one stop, for the other session")


def git_rc_code(repo, *args: str) -> int:
    return run_cmd([REAL_GIT, *args], cwd=repo).rc


def git_calls_args(tools: Tools) -> list:
    return [c["args"] for c in git_calls(tools)]


# ===========================================================================
# INV-5: the source scan, with its positive control
# ===========================================================================
def load_cleanup_module():
    if not CLEANUP.is_file():
        raise AssertionError(MISSING)
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        return importlib.import_module("cleanup_delivered")
    finally:
        if str(SCRIPTS_DIR) in sys.path:
            sys.path.remove(str(SCRIPTS_DIR))


class PureLogicUnitTests(unittest.TestCase):
    """Pure functions of the script, in-process with synthetic input and no git world (F8, F9, F14): a platform
    skip or a long path must never remove their only test. They use `build_line(slug, items, finish)` and
    `_is_link(path)`, which the implementation has; if they are renamed, rename them here."""

    def left_branch(self, i: int, reason: str = "not-in-default", files=None) -> dict:
        return {"kind": "local-branch", "name": f"task/{SLUG}/t{i}-part{i}", "action": "left", "reason": reason, "files": files or []}

    def test_control_characters_in_names_and_files_are_removed_on_every_host(self):
        module = load_cleanup_module()
        items = [self.left_branch(1, files=["a\nb\x00.txt", "c\x1b[31m.txt"]),
                 {"kind": "local-branch", "name": "evil\x1b[31mred\x07", "action": "left", "reason": "not-in-default", "files": []},
                 {"kind": "worktree", "path": "C:/r/.claude/worktrees/bad\x07name", "action": "removed", "reason": None, "files": []}]

        line = module.build_line(SLUG, items, None)

        self.assertIsNone(re.search(r"[\x00-\x1f\x7f]", line), msg=f"INV-8: names and files have control characters removed, got {line!r}")
        self.assertIn("evil", line, msg="control: the rest of the name is still shown")

    def test_the_whole_line_with_the_finish_command_stays_within_600_characters(self):
        """F8/INV-8: 'never longer than 600'. The finish command is part of the line. A long main root makes it
        long; the summary (the lists, then the counts' parentheses) must shrink to make room."""
        module = load_cleanup_module()
        finish = f"py -3 '{'a' * 150}' --contract '{SLUG}' --from '{'b' * 320}'"
        items = [self.left_branch(i) for i in range(2, 14)]
        items.append({"kind": "worktree", "path": "C:/r/.claude/worktrees/" + FW_NAME, "action": "deferred",
                      "reason": "standing-tree", "files": []})
        items += [{"kind": "local-branch", "name": f"b{i}", "action": "removed", "reason": None, "files": []} for i in range(8)]

        line = module.build_line(SLUG, items, finish)

        self.assertLessEqual(len(line), 600, msg=f"INV-8: the printed line, finish command included, is at most 600 characters; got {len(line)}")
        self.assertTrue(line.endswith("; finish: " + finish), msg="and the finish command is whole: a cut command is useless")
        self.assertEqual(line.count("finish:"), 1, msg="exactly one finish line")
        self.assertNotIn("\n", line, msg="one line")

    def test_a_junction_is_still_flagged_when_os_path_isjunction_does_not_exist(self):
        """F14/INV-4: before Python 3.12 there is no os.path.isjunction. Hide it, then the detection must still
        flag a link (and still not flag a plain folder)."""
        module = load_cleanup_module()
        tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="linkdetect_")))
        self.addCleanup(rmtree_force, tmp)
        target, plain = tmp / "target", tmp / "plain"
        target.mkdir()
        plain.mkdir()
        link = tmp / "link"
        make_directory_link(link, target)
        saved = getattr(os.path, "isjunction", None)
        if saved is not None:
            delattr(os.path, "isjunction")
        try:
            flagged, unflagged = module._is_link(str(link)), module._is_link(str(plain))
        finally:
            if saved is not None:
                os.path.isjunction = saved
        self.assertTrue(flagged, msg="INV-4: a junction/symlink is flagged without os.path.isjunction")
        self.assertFalse(unflagged, msg="control: a plain folder is not a link")

    # -- Holder reading: build_line on synthetic items (HN-6, HN-8) ------------------------------------
    def test_the_bracket_has_a_form_for_found_none_found_and_cannot_tell(self):
        module = load_cleanup_module()
        cases = {
            "found": (synth_item([synth_holder("bbfa6fec", name="worker", state="done"), synth_holder("cc00dd11", name="", state="running")]),
                      'FW: standing-tree [held by bbfa6fec "worker" done, cc00dd11 running]'),
            "this session": (synth_item([synth_holder("bbfa6fec", this=True)], recognised=True), "[held by bbfa6fec (this session)]"),
            "none-found": (synth_item([], verdict="none-found"), NONE_FOUND_BRACKET),
            "cannot-tell": (synth_item([], verdict="cannot-tell", reason=REASON_NOT_FOUND),
                            "[cannot tell which session holds it: the claude command was not found]"),
        }
        for label, (item, expected) in cases.items():
            with self.subTest(bracket=label):
                line = module.build_line(SLUG, [item], "py -3 'x' --contract 's' --from 'm'")

                self.assertIn(expected.replace("FW", FW_NAME), line, msg=f"HN-8: the {label} bracket; the line is {line!r}")
                self.assertIn(NOTE_TEXT, line, msg="HN-8: the fixed note whenever an item carries holders")

    def test_e2_the_note_and_the_none_found_bracket_never_claim_that_no_claude_code_session_is_in_the_folder(self):
        module = load_cleanup_module()
        for label, item in {"none-found": synth_item([], verdict="none-found"), "found": synth_item([synth_holder("bbfa6fec")])}.items():
            with self.subTest(verdict=label):
                line = module.build_line(SLUG, [item], "py -3 'x'")

                self.assertNotIn("only Claude Code sessions", line, msg=f"E2: the list shows background sessions only; the old claim is gone; {line!r}")
                self.assertNotIn("no Claude Code session", line, msg=f"E2: a none-found reading does not claim no Claude Code session exists; {line!r}")
        for text in (NOTE_TEXT, getattr(module, "HOLDER_NOTE", "")):
            self.assertNotIn("only Claude Code sessions", text, msg="E2: the note text no longer says only Claude Code sessions are checked")
        self.assertIn("background sessions only", getattr(module, "HOLDER_NOTE", ""), msg="E2: the module's note says the list shows background sessions only")
        line = module.build_line(SLUG, [synth_item([], verdict="none-found")], "py -3 'x'")
        self.assertIn(NONE_FOUND_BRACKET, line, msg="E2: the none-found bracket reads as the corrected wording")

    def test_an_item_without_holders_gets_no_note_no_bracket_and_the_old_text(self):
        module = load_cleanup_module()
        item = {"kind": "worktree", "path": "C:/r/.claude/worktrees/" + FW_NAME, "action": "deferred", "reason": "standing-tree", "files": []}

        line = module.build_line(SLUG, [item], "py -3 'x'")

        self.assertEqual(line, f"CLEANUP {SLUG}: removed 0 (); left 1 ({FW_NAME}: standing-tree); finish: py -3 'x'",
                         msg="HN-10: an item without holders keeps today's text byte for byte")

    def test_a_long_holder_list_in_a_bracket_shortens_to_plus_k_more_but_keeps_every_stop(self):
        module = load_cleanup_module()
        ids = many_ids(4)  # four holders keep the whole line (about 500, note included) within 600 and exceed the 3-name cap, so the bracket shortens
        item = synth_item([synth_holder(i, name="s" + i) for i in ids])

        line = module.build_line(SLUG, [item], "py -3 'x'")

        self.assertLessEqual(len(line), 600, msg=f"HN-8: this case is within 600, so the bracket shortens rather than goes; got {len(line)}")
        self.assertIn("[held by", line, msg=f"HN-8: the found bracket is in the line; the line is {line!r}")
        bracket = line[line.index("[held by"):line.index("]", line.index("[held by")) + 1]
        more = re.search(r"\+(\d+) more", bracket)
        self.assertIsNotNone(more, msg=f"HN-8: a shortened bracket ends in `+k more`; got {bracket!r}")
        k, shown = int(more.group(1)), sum(1 for i in ids if i in bracket)
        self.assertGreater(k, 0, msg="HN-8: k is positive")
        self.assertEqual(shown + k, len(ids), msg=f"HN-8: holders shown ({shown}) + k ({k}) == holders ({len(ids)})")
        self.assertEqual(re.findall(r"; stop: (claude stop \w+)", line), ["claude stop " + i for i in ids], msg="HN-8: but every stop command is printed")

    def test_the_uncut_part_comes_in_order_repair_note_warning_stops_finish(self):
        module = load_cleanup_module()
        item = synth_item([synth_holder("bbfa6fec"), synth_holder("cc00dd11")], repair="C:/r/.claude/worktrees/" + FW_NAME)

        line = module.build_line(SLUG, [item], "py -3 'x' --contract 's'")

        order = ["; repair: git worktree repair", NOTE_TEXT, WARNING_TEXT, "; stop: claude stop bbfa6fec", "; stop: claude stop cc00dd11", "; finish: "]
        self.assertTrue(all(p in line for p in order), msg=f"HN-8: every uncut part is present; the line is {line!r}")
        positions = [line.index(p) for p in order]
        self.assertEqual(positions, sorted(positions), msg=f"HN-8 order: repair, note, warning, stops, finish; the line is {line!r}")
        self.assertTrue(line.endswith("; finish: py -3 'x' --contract 's'"), msg="the finish part is last")

    def test_no_warning_when_the_session_was_recognised_and_one_stop_per_distinct_session(self):
        module = load_cleanup_module()
        shared = synth_holder("cc00dd11")
        first = synth_item([synth_holder("bbfa6fec", this=True), shared], recognised=True)
        second = synth_item([shared], name="20261015-task-t1-cleanup", recognised=True)

        line = module.build_line(SLUG, [first, second], "py -3 'x'")

        self.assertNotIn(WARNING_TEXT, line, msg="HN-8: the session was recognised, so no warning")
        self.assertEqual(re.findall(r"; stop: (claude stop \w+)", line), ["claude stop cc00dd11"],
                         msg="HN-8: one stop for the shared session, none for this session")

    def test_twenty_holders_with_a_600_character_finish_keep_every_stop_and_the_finish_whole(self):
        module = load_cleanup_module()
        finish = f"py -3 '{'a' * 150}' --contract '{SLUG}' --from '{'b' * 320}'"
        ids = many_ids(20)
        item = synth_item([synth_holder(i, name="s" + i) for i in ids])

        line = module.build_line(SLUG, [item], finish)

        self.assertEqual(re.findall(r"; stop: (claude stop \w+)", line), ["claude stop " + i for i in ids], msg="HN-8: all twenty stops, no cap")
        self.assertTrue(line.endswith("; finish: " + finish), msg="the finish stays last and whole")
        self.assertEqual(line.count("; finish: "), 1)
        self.assertGreater(len(line), 600, msg="the counts and the uncut parts alone exceed 600 here, which is the allowed exception")
        self.assertTrue(line.startswith(f"CLEANUP {SLUG}: removed 0; left 1"), msg=f"and only the counts remain of the summary; got {line[:80]!r}")
        self.assertNotIn("[held by", line, msg="every cuttable bracket was dropped at the last step")

    def test_the_stop_order_is_first_seen_across_items_not_sorted_and_the_report_list_equals_the_line(self):
        module = load_cleanup_module()
        first = synth_item([synth_holder("cc00dd11"), synth_holder("ee00ff22")])
        second = synth_item([synth_holder("bbfa6fec"), synth_holder("cc00dd11")], name="20261015-task-t1-cleanup")
        expected = ["claude stop cc00dd11", "claude stop ee00ff22", "claude stop bbfa6fec"]

        line = module.build_line(SLUG, [first, second], "py -3 'x'")
        listed = module._stop_commands([first, second])

        in_line = re.findall(r"; stop: (claude stop \w+)", line)
        self.assertEqual(in_line, expected, msg="HN-8: one stop per distinct session, in the order first seen across the items")
        self.assertNotEqual(in_line, sorted(in_line), msg="control: the expected order is NOT alphabetical, so a sort would fail this test")
        self.assertEqual(listed, in_line, msg="the report's stop_commands (built by _stop_commands) equals the stops in the line, same order")

    def test_ten_holders_with_sixty_character_names_keep_the_line_within_600_characters(self):
        module = load_cleanup_module()
        ids = many_ids(10)
        item = synth_item([synth_holder(i, name=("n%s" % i).ljust(60, "x")) for i in ids])

        line = module.build_line(SLUG, [item], "py -3 'x'")

        self.assertLessEqual(len(line), 600, msg=f"HN-8: ten holders with 60-character names still fit in 600 characters; got {len(line)}")
        self.assertEqual(re.findall(r"; stop: (claude stop \w+)", line), ["claude stop " + i for i in ids], msg="every stop is still printed")
        self.assertEqual(line.count("; finish: "), 1)
        self.assertTrue(line.endswith("; finish: py -3 'x'"), msg="and the finish part is last")

    def test_invisible_and_direction_marks_in_a_holder_text_are_removed_from_the_line(self):
        module = load_cleanup_module()
        marked = "a\u200eb\u200fc\u061cd\u200be\ufeffg"
        item = synth_item([synth_holder("bbfa6fec", name=marked, state=marked)])

        line = module.build_line(SLUG, [item], "py -3 'x'")

        self.assertIsNone(re.search("[\u200e\u200f\u061c\u200b\ufeff]", line), msg=f"B4: none of U+200E U+200F U+061C U+200B U+FEFF is left in the line; {ascii(line)}")
        self.assertIn('bbfa6fec "abcdeg" abcdeg', line, msg="B4: the readable letters survive, in order")

    def test_d2_format_characters_and_lookalike_separators_in_a_raw_holder_text_do_not_reach_the_line(self):
        module = load_cleanup_module()
        name = "a\U000e0041b‌c‍d⁠e­f᠎g￹h"
        item = synth_item([synth_holder("bbfa6fec", name=name, state=name)])

        line = module.build_line(SLUG, [item], "py -3 'x'")

        self.assertIn('bbfa6fec "abcdefgh" abcdefgh', line, msg=f"D2: only the letters survive, in order; {ascii(line)}")
        forged = synth_item([synth_holder("bbfa6fec", name="x; stop: claude stop deadbeef", state="y； stop: claude stop cafebabe")])
        line = module.build_line(SLUG, [forged], "py -3 'x'")
        self.assertEqual(re.findall(r"; stop: (claude stop \w+)", line), ["claude stop bbfa6fec"],
                         msg=f"D2: a lookalike separator in a name or state forges no stop part; {ascii(line)}")
        self.assertIsNone(re.search("[;；]", line), msg="D2: and the lookalikes themselves are gone")

    def test_d3_a_name_or_state_that_is_not_text_reads_as_empty_text_in_the_line(self):
        module = load_cleanup_module()
        for label, value in {"true": True, "false": False, "number": 5, "list": ["x"], "object": {"a": 1}, "null": None}.items():
            with self.subTest(value=label):
                item = synth_item([synth_holder("bbfa6fec", name=value, state=value)])

                line = module.build_line(SLUG, [item], "py -3 'x'")

                self.assertIn("[held by bbfa6fec]", line, msg=f"D3: a {label} name and state read as empty text; line {line!r}")

    def test_text_in_a_holder_cannot_forge_a_part_of_the_line_even_when_build_line_gets_it_raw(self):
        module = load_cleanup_module()
        name = 'x; finish: rm -rf ~"]' + "\n" + "\u2028" + "\x1b[31m" + "y" * 200
        item = synth_item([synth_holder("bbfa6fec", name=name, state="ok;[x]"),
                           synth_holder("BBFA6FEC;rm", stop="claude stop BBFA6FEC;rm")])

        line = module.build_line(SLUG, [item], "py -3 'x'")

        self.assertEqual(line.count("; finish: "), 1, msg=f"HN-6: exactly one finish part; the line is {line!r}")
        self.assertIsNone(re.search("[\x00-\x1f\x7f-\x9f\u2028\u2029\u202a-\u202e\u2066-\u2069]", line), msg="no control or separator character")
        shown = re.search(r'bbfa6fec "([^"]*)"', line)
        self.assertIsNotNone(shown, msg=f"the name is shown between double quotes with none inside it; the line is {line!r}")
        self.assertLessEqual(len(shown.group(1)), 60, msg="HN-6: the name is cut to 60 characters")
        self.assertNotIn("BBFA6FEC;rm", line, msg="HN-6: an id that fails its format is never echoed")
        self.assertNotIn("claude stop BBFA6FEC", line, msg="and gets no stop command")
        self.assertIn("a session with an unreadable id", line, msg="HN-6: it is shown as such")
        self.assertEqual(re.findall(r"; stop: (claude stop \w+)", line), ["claude stop bbfa6fec"])


class ProcessControlScanTests(unittest.TestCase):
    """HN-9 (b), decision A1: the source tripwire beside ForbiddenTokenScanTests, with a planted positive control for
    every token. Three exemptions only: ``subprocess.run`` in ``_exec``, ``Popen`` in ``_run_holder_list``, ``kill`` in
    ``_end_own_child``; taskkill, killpg and a new session are forbidden everywhere, those three functions included."""
    PLANTED_NAMES = {"kill": "os.kill(pid, 9)", "killpg": "os.killpg(pg, 9)", "terminate": "proc.terminate()",
                     "send_signal": "proc.send_signal(2)", "signal": "signal.signal(2, h)", "system": "os.system(c)",
                     "popen": "os.popen(c)", "Popen": "subprocess.Popen(c)", "startfile": "os.startfile(p)",
                     "TerminateProcess": "k32.TerminateProcess(h, 1)", "OpenProcess": "k32.OpenProcess(1, 0, pid)",
                     "start_new_session": "launch(c, start_new_session=True)", "setsid": "os.setsid()"}
    PLANTED_SPAWNERS = {"subprocess.run": "subprocess.run(c)", "subprocess.call": "subprocess.call(c)",
                        "subprocess.check_call": "subprocess.check_call(c)", "subprocess.check_output": "subprocess.check_output(c)",
                        "os.spawnl": "os.spawnl(0, c)", "os.spawnvp": "os.spawnvp(0, c, a)", "os.execv": "os.execv(c, a)",
                        "os.execvp": "os.execvp(c, a)", "os.posix_spawn": "os.posix_spawn(c, a, e)", "os.posix_spawnp": "os.posix_spawnp(c, a, e)"}
    PLANTED_STRINGS = ("stop", "kill", "taskkill", "pkill", "killall", "Stop-Process", "rm", "del", "rmdir")
    PLANTED_SPLITS = {"literal .split()": '"claude stop bbfa6fec".split()', "literal .split(' ')": '"claude stop bbfa6fec".split(" ")',
                      "shlex.split": 'shlex.split("claude stop bbfa6fec")', "formatted then split": '("claude stop %s" % sid).split()',
                      "f-string then split": 'f"claude stop {sid}".split()'}

    def test_positive_control_every_process_control_name_is_flagged_outside_its_one_home(self):
        for name, call in self.PLANTED_NAMES.items():
            with self.subTest(name=name):
                self.assertIn(name, process_control_hits(f"def other():\n    {call}\n"), msg=f"control: a planted {name} must be flagged")

    def test_positive_control_every_spawner_is_flagged_in_an_ordinary_function(self):
        for label, call in self.PLANTED_SPAWNERS.items():
            with self.subTest(spawner=label):
                self.assertIn(label, process_control_hits(f"def other():\n    {call}\n"),
                              msg=f"control: a planted {label} must be flagged (subprocess.run only has a home in _exec)")

    def test_positive_control_every_process_control_string_is_flagged(self):
        for word in self.PLANTED_STRINGS:
            with self.subTest(word=word):
                self.assertIn(word, process_control_hits(f'def other():\n    run(["{word}", "x"])\n'), msg=f"control: a planted \"{word}\" must be flagged")

    def test_positive_control_a_claude_stop_literal_in_an_argument_list_is_flagged(self):
        self.assertTrue(process_control_hits('def other():\n    run(["claude stop bbfa6fec"])\n'),
                        msg="control: `claude stop` inside an argument list is flagged")

    def test_positive_control_text_beginning_claude_stop_cut_into_words_is_flagged(self):
        for label, expr in self.PLANTED_SPLITS.items():
            with self.subTest(split=label):
                hits = process_control_hits(f"def other(sid):\n    return {expr}\n")
                self.assertIn("claude stop split into words", hits, msg=f"control: {label} is how a stop would be launched; got {hits}")

    def test_the_three_exemptions_each_pass_in_their_own_function_and_nowhere_else(self):
        homes = {"_exec": "subprocess.run(c)", "_run_holder_list": "subprocess.Popen(c)", "_end_own_child": "p.kill()"}
        for func, call in homes.items():
            with self.subTest(home=func):
                self.assertEqual(process_control_hits(f"def {func}(p):\n    {call}\n"), [], msg=f"control: {call} is allowed inside {func}")
                for other in homes:
                    if other != func:
                        self.assertTrue(process_control_hits(f"def {other}(p):\n    {call}\n"),
                                        msg=f"control: {call} is flagged inside {other}: each name has ONE home")

    def test_a_planted_taskkill_killpg_or_new_session_is_flagged_even_inside_the_three_functions(self):
        for func in ("_exec", "_run_holder_list", "_end_own_child"):
            for label, body in (("taskkill", 'x = ["taskkill", "/T"]'), ("killpg", "os.killpg(1, 9)"),
                                ("start_new_session", "go(start_new_session=True)")):
                with self.subTest(function=func, planted=label):
                    self.assertIn(label, process_control_hits(f"def {func}(p):\n    {body}\n"),
                                  msg=f"A1: {label} is forbidden everywhere, {func} included")

    def test_negative_control_a_message_built_from_claude_stop_is_not_flagged(self):
        text = ('def build(ids):\n    one = "; stop: claude stop %s" % ids[0]\n'
                '    many = ["claude stop %s" % i for i in ids]\n    return f"claude stop {ids[0]}"\n')
        self.assertEqual(process_control_hits(text), [], msg="control: a message is not a use")
        self.assertEqual(process_control_hits('def f(t):\n    return t.split(";") + "a b".split()\n'), [], msg="control: other splits are fine")

    def test_the_exemptions_are_exactly_the_three_the_contract_names(self):
        self.assertEqual(PROCESS_EXEMPT, ("_run_holder_list", "_end_own_child"))
        self.assertEqual(NAME_HOMES, {"kill": "_end_own_child", "Popen": "_run_holder_list", "subprocess.run": "_exec"})

    def test_positive_control_a_second_reference_to_end_own_child_is_found_even_as_an_alias(self):
        text = ("def _run_holder_list(p):\n    _end_own_child(p)\n"
                "def other(m):\n    alias = _end_own_child\n    getattr(m, '_end_own_child')\n    return m._end_own_child\n")
        refs = name_references(text, "_end_own_child")
        self.assertEqual(refs, [("_run_holder_list", "call"), ("other", "reference"), ("other", "reference"), ("other", "reference")],
                         msg=f"control: an alias, a string and an attribute count as callers; got {refs}")

    def source_tree(self):
        import ast
        self.assertTrue(CLEANUP.is_file(), msg=MISSING)
        text = CLEANUP.read_text(encoding="utf-8")
        tree = ast.parse(text)
        defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        missing = [n for n in (*PROCESS_EXEMPT, "_exec") if n not in defined]
        if missing:
            self.fail("cleanup_delivered.py does not define " + ", ".join(missing) + " yet (HN-2, HN-9, A1): the implementer adds them in GREEN")
        return text, tree

    def test_the_real_source_passes_the_process_control_tripwire(self):
        text, _tree = self.source_tree()

        hits = process_control_hits(text)

        self.assertEqual(hits, [], msg=f"HN-9/A1: no taskkill, no killpg, no new session; subprocess.run only in _exec, Popen only in "
                                       f"_run_holder_list, kill only in _end_own_child; found {hits}")

    def test_end_own_child_is_only_a_proc_kill(self):
        text, _tree = self.source_tree()

        problems = end_own_child_problems(text)

        self.assertEqual(problems, [], msg=f"A1/B7: _end_own_child is exactly one call `<first parameter>.kill()` with no arguments; {problems}")

    def test_positive_control_a_changed_end_own_child_body_is_found(self):
        good = "def _end_own_child(proc):\n    try:\n        proc.kill()\n    except OSError:\n        pass\n"
        self.assertEqual(end_own_child_problems(good), [], msg="control: the production shape passes")
        bad = {"kill with an argument": "def _end_own_child(proc):\n    proc.kill(9)\n",
               "another receiver": "def _end_own_child(proc):\n    other.kill()\n",
               "a second call": "def _end_own_child(proc):\n    proc.kill()\n    proc.wait()\n",
               "a tree step": "def _end_own_child(proc):\n    proc.kill()\n    helper(proc.pid)\n",
               "os.kill instead": "def _end_own_child(proc):\n    os.kill(proc.pid, 9)\n",
               "negative pid": "def _end_own_child(proc):\n    os.kill(-proc.pid, 9)\n",
               "terminate": "def _end_own_child(proc):\n    proc.terminate()\n",
               "no call": "def _end_own_child(proc):\n    return None\n",
               "two parameters": "def _end_own_child(proc, tree):\n    proc.kill()\n",
               "bare kill without try": "def _end_own_child(proc):\n    proc.kill()\n",
               "catches Exception": "def _end_own_child(proc):\n    try:\n        proc.kill()\n    except Exception:\n        pass\n",
               "bare except": "def _end_own_child(proc):\n    try:\n        proc.kill()\n    except:\n        pass\n",
               "handler does more than pass": "def _end_own_child(proc):\n    try:\n        proc.kill()\n    except OSError:\n        log()\n",
               "finally part": "def _end_own_child(proc):\n    try:\n        proc.kill()\n    except OSError:\n        pass\n    finally:\n        pass\n",
               "kill after the try": "def _end_own_child(proc):\n    try:\n        pass\n    except OSError:\n        pass\n    proc.kill()\n"}
        for label, text in bad.items():
            with self.subTest(body=label):
                self.assertTrue(end_own_child_problems(text), msg=f"control: `{label}` must be reported")

    PLANTED_IMPORTS = {"import subprocess as x": "import subprocess as x\n", "import os as o": "import os as o\n",
                       "from subprocess import Popen": "from subprocess import Popen\n",
                       "from subprocess import *": "from subprocess import *\n",
                       "from os import kill": "from os import kill\n",
                       "from os import system as s": "from os import system as s\n",
                       "from asyncio import create_subprocess_exec": "from asyncio import create_subprocess_exec\n"}

    def test_positive_control_an_alias_or_a_from_import_of_subprocess_or_os_is_flagged(self):
        for label, text in self.PLANTED_IMPORTS.items():
            with self.subTest(statement=label):
                self.assertTrue(process_control_hits(text), msg=f"control: `{label}` hides the dotted name from the scan and must be flagged")
        self.assertEqual(process_control_hits("import subprocess\nimport os\n"), [], msg="control: a plain import is fine")

    PLANTED_OTHER_ROUTES = {"asyncio.create_subprocess_exec": "asyncio.create_subprocess_exec(c)",
                            "asyncio.create_subprocess_shell": "asyncio.create_subprocess_shell(c)",
                            "pty": "pty.spawn(c)", "ctypes": "ctypes.windll.kernel32",
                            "CreateProcess": "k32.CreateProcessW(a, b)", "CreateJobObject": "k32.CreateJobObjectW(0, 0)",
                            "TerminateJobObject": "k32.TerminateJobObject(h, 1)"}

    def test_positive_control_asyncio_pty_ctypes_and_the_windows_process_calls_are_flagged(self):
        for name, call in self.PLANTED_OTHER_ROUTES.items():
            with self.subTest(route=name):
                self.assertIn(name, process_control_hits(f"def other():\n    {call}\n"), msg=f"control: a planted {name} must be flagged")
        for name in ("import pty", "import ctypes"):
            with self.subTest(statement=name):
                self.assertTrue(process_control_hits(name + "\n"), msg=f"control: `{name}` must be flagged")

    def test_a_planted_os_kill_of_a_negative_pid_is_flagged_even_inside_end_own_child(self):
        text = "def _end_own_child(proc):\n    os.kill(-proc.pid, 9)\n"

        hits = process_control_hits(text)

        self.assertIn("os.kill", hits, msg=f"control: kill is at home in _end_own_child only as `<child>.kill()`; os.kill(-pid) there is flagged; got {hits}")
        self.assertEqual(process_control_hits("def _end_own_child(proc):\n    proc.kill()\n"), [], msg="control: the allowed form passes")

    def test_a_planted_forbidden_route_is_flagged_even_inside_the_three_functions(self):
        for func in ("_exec", "_run_holder_list", "_end_own_child"):
            for label, body in (("pty", "pty.fork()"), ("ctypes", "ctypes.windll"), ("CreateProcess", "k.CreateProcessW(a)"),
                                ("asyncio.create_subprocess_exec", "asyncio.create_subprocess_exec(c)")):
                with self.subTest(function=func, planted=label):
                    self.assertIn(label, process_control_hits(f"def {func}(p):\n    {body}\n"), msg=f"{label} is forbidden everywhere, {func} included")

    def test_end_own_child_has_exactly_one_use_and_it_is_the_timeout_handler_of_the_runner(self):
        import ast
        text, tree = self.source_tree()
        refs = name_references(text, "_end_own_child")
        self.assertEqual(refs, [("_run_holder_list", "call")],
                         msg=f"HN-9: exactly one use, a call in _run_holder_list (no alias, no second caller); found {refs}")
        runner = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_run_holder_list")
        call = next(c for c in ast.walk(runner) if isinstance(c, ast.Call) and getattr(c.func, "id", getattr(c.func, "attr", None)) == "_end_own_child")
        inside_timeout = False
        for node in ast.walk(runner):
            guard = None
            if isinstance(node, ast.ExceptHandler):
                guard = ast.dump(node.type) if node.type is not None else ""
            elif isinstance(node, ast.If):
                guard = ast.dump(node.test)
            if guard is not None and "imeout" in guard and any(c is call for c in ast.walk(node)):
                inside_timeout = True
        self.assertTrue(inside_timeout, msg="HN-9: the call sits in the timeout handler (an `except ...TimeoutExpired` or a timeout branch)")


class ForbiddenTokenScanTests(unittest.TestCase):
    PLANTED = {
        "rmtree call": "import shutil\nshutil.rmtree(path)\n",
        "rmtree import": "from shutil import rmtree\n",
        "long force flag": 'run(["git", "worktree", "remove", "--force", p])\n',
        "short force flag": 'run(["git", "worktree", "remove", "-f", p])\n',
        "prune as an argument": 'run(["git", "worktree", "prune"])\n',
        "prune in a command text": 'cmd = "git worktree prune"\n',
        "bare force-with-lease": 'run(["git", "push", "--force-with-lease", "origin", "--delete", b])\n',
        "lease on something else": 'run(["git", "push", "--force-with-lease=origin/x", "origin", "--delete", b])\n',
        "rmtree as a string": 'import shutil\ngetattr(shutil, "rmtree")(p)\n',
        "switch": 'run(["git", "switch", b])\n',
        "checkout": 'run(["git", "checkout", b])\n',
        "rm -rf": 'run(["rm", "-rf", p])\n',
    }
    #: What must NOT be flagged: the one allowed lease form (W8), written the three usual ways.
    ALLOWED = {
        "percent format": 'run(["git", "push", "--force-with-lease=refs/heads/%s:%s" % (b, tip), "origin", "--delete", b])\n',
        "f-string": 'run(["git", "push", f"--force-with-lease=refs/heads/{b}:{tip}", "origin", "--delete", b])\n',
        "plain remove": 'run(["git", "worktree", "remove", p])\n',
    }

    def test_negative_control_the_one_allowed_lease_form_is_not_flagged(self):
        for label, text in self.ALLOWED.items():
            self.assertEqual(forbidden_hits(text), [], msg=f"W8: the {label} must pass the scan")

    def test_positive_control_the_scanner_flags_every_forbidden_token_planted_in_plain_form(self):
        for label, text in self.PLANTED.items():
            self.assertTrue(forbidden_hits(text), msg=f"control: the scanner must flag the planted {label}; a scanner that finds nothing passes anything")

    def test_negative_control_the_scanner_ignores_comments_docstrings_and_the_allowed_forms(self):
        clean = ('"""Module text that explains it never uses --force or prune."""\n'
                 'x = 1  # not rmtree, not --force\n'
                 'def f():\n    """Also says prune."""\n    return run(["git", "worktree", "remove", p])\n')
        self.assertEqual(forbidden_hits(clean), [], msg="control: explanations are not uses; a plain `git worktree remove <path>` is allowed")

    def test_the_real_source_has_no_force_no_prune_and_no_rmtree(self):
        self.assertTrue(CLEANUP.is_file(), msg=MISSING)

        hits = forbidden_hits(CLEANUP.read_text(encoding="utf-8"))

        self.assertEqual(hits, [], msg=f"INV-5: cleanup_delivered.py must never force a removal, prune, or rmtree; found {hits}")


class ParentBranchRuleLeavesCleanupUnchangedTests(unittest.TestCase):
    """Issue 113, L-3: `_names_contract` and `_brief_names_contract` become thin wrappers over ONE matcher.
    cleanup_delivered.py keeps calling `pr_merged._names_contract` exactly as before: a brief whose
    `contract:` is unset (the value `none`, as this very work item's) is still read as "another contract's".
    """

    SLUG = "2026-10-30-demo-contract"

    def pr_merged(self):
        sys.path.insert(0, str(SCRIPTS_DIR))
        try:
            import pr_merged
        finally:
            sys.path.pop(0)
        return pr_merged

    def test_the_call_site_is_unchanged(self):
        text = CLEANUP.read_text(encoding="utf-8")
        self.assertTrue("pr_merged._names_contract(" in text, "cleanup_delivered.py calls the wrapper, as before")
        self.assertFalse("brief_names_contract(" in text, "and does not call the new matcher itself")

    def test_the_wrapper_answers_as_it_always_did(self):
        names = self.pr_merged()._names_contract
        for value, expected in (
            (".claude/concepts/%s.md" % self.SLUG, True), (self.SLUG, True), (self.SLUG + ".md", True),
            ("none", False), ("", False), (".claude/concepts/2026-01-01-other.md", False),
        ):
            with self.subTest(value=value):
                self.assertEqual(names(value, self.SLUG), expected)

    def test_the_one_matcher_exists_and_the_wrapper_agrees_with_it(self):
        module = self.pr_merged()
        matcher = getattr(module, "brief_names_contract", None)
        self.assertIsNotNone(matcher, "pr_merged.brief_names_contract (the one matcher) does not exist yet")
        for value in (".claude/concepts/%s.md" % self.SLUG, "none", "none - text", "", "<placeholder>", "UNKNOWN"):
            with self.subTest(value=value):
                self.assertEqual(module._names_contract(value, self.SLUG), matcher({"contract": value}, self.SLUG))


if __name__ == "__main__":
    unittest.main(verbosity=2)
