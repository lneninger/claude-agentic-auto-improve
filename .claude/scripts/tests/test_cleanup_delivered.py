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
        proc = run_py(CLEANUP, *args, cwd=cwd or self.w.main, env=clean_env(env_extra, tools=self.w.tools))
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
            with mock.patch.dict(os.environ, clean_env(env_extra, tools=self.w.tools), clear=True), \
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
