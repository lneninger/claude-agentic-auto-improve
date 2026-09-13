#!/usr/bin/env python3
"""
test_script_path_resolution.py -- RED suite for project-first path resolution
in .claude/scripts/ (work item #35, contract
.claude/concepts/2026-08-26-claude-scripts-path-resolution.md).

House style: plain runnable script, NO pytest -- matches
.claude/hooks/tests/test_memory_common.py and test_db_destructive_guard.py.
check(name, cond, detail) accumulator, printed PASS/FAIL summary, non-zero
exit on any failure.

    py -3 .claude/scripts/tests/test_script_path_resolution.py

--------------------------------------------------------------------------
WHAT THIS PINS DOWN
--------------------------------------------------------------------------
The seven scripts under .claude/scripts/ resolve their Claude data files
under ``Path.home()/".claude"``, which the 2026-08-25 migration emptied.
They all fail *open* -- empty result, exit 0 -- so the breakage is silent.
This suite makes it loud:

  case 1  project-local layout present -> every locator returns the
          project-local path; derive_areas() returns the LITERAL bucket list;
          the CLI prints the LITERAL two-line stdout and the LITERAL
          --dump-mapping JSON; query() returns LITERAL ledger values; every
          ZERO-ARGUMENT resolver is asserted directly, so a fixture-injected
          root cannot hand a subject its own answer.
          (positive control for cases 2, 2c and 3)
  case 2b SELF_ROOT (rank 1) beats cwd and a POPULATED global root.
  case 2c INV-4 populated-vs-exists: an EMPTY concepts/ + north-stars/ at
          rank 1 must LOSE to a populated lower rank. Without this,
          first_populated_dir reverts to `if candidate.is_dir(): return
          candidate` and /list-contracts reports zero at exit 0 -- the bug
          under repair, one rank down.
  case 2  project-local absent, global present -> every locator returns the
          global path; the same fixture still resolves.
  case 3  missing in BOTH layouts -> the specific neutral value, exit 0,
          no exception (INV-3, fail-open preserved).
  case 4  flat-layout discovery (INV-8, FLAT ONLY): archive_stale_stubs
          finds flat concepts/followups/, north_star_review finds flat
          north-stars/*.md, list_contracts resolves a real project name.
          LITERAL counts -- "non-empty" would not catch a root-only fix.
  case 5  INV-2 call-time resolution: a locator called AFTER the roots move
          returns the NEW value; INV-1 AST source sweep: no script (and not
          the bridge) lets a home expression reach a .claude literal in ANY
          spelling -- with a four-form positive control on the sweep itself.
  case 6  INV-1 negative: the _claude_paths bridge raises ImportError (not a
          silent home fallback) when the hooks sibling is absent -- with a
          positive control that proves the harness itself works, and the
          LITERAL resolved path asserted in the message.
  case 6c the same, under a FABRICATED, POPULATED $HOME, asserted on
          PROVENANCE (which _project_paths.py got loaded) rather than on
          outcome. Case 6 alone passes for a bridge that DOES fall back to
          home, because ~/.claude/hooks is absent on this workstation so the
          fallback fails too -- and its ImportError also says "hooks".
  case 7  the ledger WRITE path (INV-7 / INV-9): record_clean x5 against a
          fake root lands the file at <fake-proj>/.claude/, with
          skip_eligible FALSE at 4 and TRUE at 5, and NOTHING under the fake
          home. Everything else exercises reads only.
  case 8  cross_area_scan's cache round-trips per checkout and MISSES across
          checkouts (a hit would serve one checkout's answer to another).
  case 9  validate_registries' candidate roots and a real 1-alive/1-dead
          count -- the module was never even imported before.
  case 10 --project accepts the checkout directory name OR the git main-repo
          name, case-insensitively, through both consumers, with an explicit
          non-match so "accept everything" is not a passing answer.

--------------------------------------------------------------------------
INV-6 -- SELF-RELATIVE SUBJECTS
--------------------------------------------------------------------------
Every subject under test is resolved via Path(__file__).resolve().parent...
NEVER from Path.home(), never from an absolute path. JOURNAL.md:1012-1026
records this repo shipping a suite where 9 of 21 cases reported PASS against
a file that did not exist, because the subject was addressed absolutely.
Path.home() appears in exactly two places below, both NEGATIVE guards that
assert we did *not* touch the real tree.

--------------------------------------------------------------------------
INV-11 -- THE SEAM (measured, not theorized)
--------------------------------------------------------------------------
claude_roots() consults THREE ranks (_project_paths.py:49-56):

    rank 0   os.environ["CLAUDE_PROJECT_DIR"]      (absent in a plain shell)
    rank 1   _project_paths.SELF_ROOT             (the .claude this module ships in)
    rank 2   Path.cwd() / ".claude"
    rank 3   _project_paths.HOME / ".claude"

Rebinding HOME alone leaves the REAL repo at rank 0 -- measured during
contract revision: "real repo still rank 0 -> True". claude_roots_seam()
below pops CLAUDE_PROJECT_DIR, os.chdir()s to a neutral temp dir, and
rebinds _project_paths.HOME, which measured "leaks to real tree -> NONE".
cwd and the env var are restored in a finally block. Every case additionally
runs assert_seam_isolated(), so a broken seam reports as a distinct failure
instead of silently making the case vacuous.

--------------------------------------------------------------------------
INV-10 -- NO TEST TOUCHES ANY REAL TREE
--------------------------------------------------------------------------
Four mechanisms:
  * LAYER 0, and the only PREVENTIVE one: the suite re-execs itself under a
    fabricated $HOME before anything else runs. Detection was measured to be
    insufficient -- while mutation-probing case 7, a deliberately broken
    _save_state pointed at Path.home() overwrote the real 17,706-byte
    workstation ledger with 472 bytes of fixture data. The sentinel reported
    the write and the file was still gone. claude_roots_seam() rebinds
    _project_paths.HOME, which covers everything flowing through the
    resolver, but a regression that calls Path.home() DIRECTLY bypasses the
    seam -- and that is exactly the regression class this suite exists to
    catch, so the suite has to survive catching it.
  * A boot sandbox is created, CLAUDE_PROJECT_DIR is pointed at it AND the
    process chdir()s to a neutral directory inside it, BEFORE any subject is
    imported. Redirecting the env var alone leaves rank 2 (Path.cwd() /
    ".claude") aimed at the real repo whenever the suite is launched from
    the repo root, so any import-time resolution a subject still performed
    would reach the live tree before a single case ran. accuracy_update
    imports _error_log, whose LOG_DIR is computed at MODULE SCOPE
    (_error_log.py:56-57), so a later redirect would be too late and the
    real <repo>/.claude/logs/errors.jsonl would be appended to.
  * A sys.addaudithook on the `open` event records every access to a real
    Claude DATA path -- READ as well as write. This replaces the claim the
    header used to make on a stat() snapshot's authority: a snapshot cannot
    observe a read, so a subject that resolved the live .claude/concepts and
    inventoried 160 real contracts left every sentinel byte-identical and
    printed PASS. The tripwire carries its own positive control (a
    deliberate read that MUST be caught), because a hook that never fires
    reports a clean bill of health forever.
    Scope is deliberate: real .claude DATA (concepts, north-stars,
    registries, logs, cache, state, the ledger, the area map), not the whole
    of .claude. The suite is REQUIRED to read the real .claude/scripts/*.py
    sources -- INV-6 subject resolution and case 5's sweep -- and importlib
    must open the subject modules themselves.
  * snapshot_real_trees() snapshots the repo ledger, the repo error log and
    their workstation counterparts before the run and re-checks them after.
    Kept alongside the audit hook because it also covers deletion and
    truncation by paths that bypass open() (os.replace, rename, unlink).
    Any mutation is reported as its own FAIL.

--------------------------------------------------------------------------
ASSUMPTIONS THE IMPLEMENTER MAY OVERRIDE (flagged, not smuggled)
--------------------------------------------------------------------------
  * cache_dir() is asserted to return "<root>/.claude/cache" and to follow
    the state_dir()/logs_dir() rule (project_dir() when known, else HOME) --
    NOT "<root>/.claude/cache/cross-area-scans". The contract names the
    helper but not its leaf; this reading matches the two existing runtime
    -directory helpers it sits beside. If GREEN chooses the scan-specific
    leaf, ONE line here changes (EXPECTED_CACHE_LEAF).
  * The bridge's re-export surface is not enumerated by the contract. The
    surface asserted below is "the helper surface the scripts need" read
    literally off the seven call sites.
  * first_populated_dir()'s return value when NO root is populated is
    deliberately NOT asserted -- that detail is undecided, so asserting it
    would be inventing an implementation. Case 3 asserts consumer-level
    neutral values instead, which the contract does state.
"""

from __future__ import annotations

import ast
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager, redirect_stdout
from pathlib import Path

# ---------------------------------------------------------------------------
# INV-10, layer 0 -- RE-EXEC UNDER A FABRICATED $HOME. Must be the first thing
# that happens, before tempfile.mkdtemp() or any Path.home() call.
#
# This exists because detection proved insufficient, and the evidence is
# first-hand. While mutation-probing case 7, a deliberately broken
# ``_save_state`` -- pointed at ``Path.home() / ".claude" /
# "contract-accuracy.json"``, the exact regression case 7 is meant to catch --
# OVERWROTE the real 17,706-byte workstation ledger with 472 bytes of fixture
# data. The INV-10 sentinel dutifully reported the write, and the file was
# still destroyed: a snapshot is a coroner, not a seatbelt.
#
# ``claude_roots_seam`` rebinds ``_project_paths.HOME``, which is enough for
# every path that flows through the resolver -- but a regression that calls
# ``Path.home()`` DIRECTLY reads the live USERPROFILE and bypasses the seam
# entirely. That is precisely the regression class this suite exists to catch,
# so the suite must survive catching it. Fabricating $HOME at the process
# boundary is the only seam that covers a direct call.
#
# The true home is forwarded so the guards below still WATCH the real tree
# (something could hardcode an absolute path) even though nothing can now
# resolve to it.
# ---------------------------------------------------------------------------
_HOME_SANDBOX_ENV = "CLAUDE_RED_PATHS_HOME_SANDBOX"
_REAL_HOME_ENV = "CLAUDE_RED_PATHS_REAL_HOME"

if not os.environ.get(_HOME_SANDBOX_ENV):
    _fab_home = tempfile.mkdtemp(prefix="claude-red-fabhome-")
    _drive, _tail = os.path.splitdrive(_fab_home)
    _child_env = dict(os.environ)
    _child_env.update({
        _HOME_SANDBOX_ENV: _fab_home,
        _REAL_HOME_ENV: str(Path.home()),
        "USERPROFILE": _fab_home,       # ntpath.expanduser consults this first
        "HOME": _fab_home,              # posixpath.expanduser
        "HOMEDRIVE": _drive,            # ntpath fallback pair
        "HOMEPATH": _tail or _fab_home,
    })
    try:
        _rc = subprocess.call(
            [sys.executable, str(Path(__file__).resolve())] + sys.argv[1:],
            env=_child_env,
        )
    finally:
        shutil.rmtree(_fab_home, ignore_errors=True)
    sys.exit(_rc)


def _real_home() -> Path:
    """The workstation home, as it was BEFORE the fabrication above.

    Used only by INV-10's negative guards -- never for resolution (INV-1).
    """
    raw = os.environ.get(_REAL_HOME_ENV)
    return Path(raw) if raw else Path.home()


# ---------------------------------------------------------------------------
# INV-6: every subject resolved relative to THIS file.
# ---------------------------------------------------------------------------
_TESTS_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _TESTS_DIR.parent
_CLAUDE_DIR = _SCRIPTS_DIR.parent
_HOOKS_DIR = _CLAUDE_DIR / "hooks"
_REPO_ROOT = _CLAUDE_DIR.parent

#: The bridge module this contract introduces. Absent today -- that is RED.
_BRIDGE_SRC = _SCRIPTS_DIR / "_claude_paths.py"

#: The seven scripts the contract binds (INV-1 source sweep).
_SEVEN_SCRIPTS = (
    "derive_area.py",
    "cross_area_scan.py",
    "accuracy_update.py",
    "list_contracts.py",
    "north_star_review.py",
    "archive_stale_stubs.py",
    "validate_registries.py",
)

#: INV-1 source sweep set: the seven scripts PLUS the bridge. The bridge is
#: bound by INV-1 too -- its removed "fail soft with home-based defaults"
#: clause is the single most likely thing a future reader "restores".
_INV1_SWEEP_FILES = _SEVEN_SCRIPTS + ("_claude_paths.py",)

#: Assumption, flagged above. Change this one tuple if GREEN decides otherwise.
EXPECTED_CACHE_LEAF = ("cache",)

#: Surface the bridge is expected to re-export (assumption, flagged above).
_BRIDGE_EXPECTED_EXPORTS = (
    "claude_roots",
    "concepts_roots",
    "registry",
    "area_mapping_path",
    "accuracy_state_path",
    "north_stars_roots",
    "cache_dir",
    "first_populated_dir",
)


# ---------------------------------------------------------------------------
# INV-10 boot sandbox -- MUST run before any subject import.
# ---------------------------------------------------------------------------
_SANDBOX = Path(tempfile.mkdtemp(prefix="claude-red-paths-")).resolve()
_BOOT_PROJECT = _SANDBOX / "BootProject"
(_BOOT_PROJECT / ".claude" / "logs").mkdir(parents=True, exist_ok=True)
_SAVED_CPD_AT_BOOT = os.environ.get("CLAUDE_PROJECT_DIR")
os.environ["CLAUDE_PROJECT_DIR"] = str(_BOOT_PROJECT)

# ...and neutralize rank 2 at boot too. Redirecting CLAUDE_PROJECT_DIR alone
# leaves ``Path.cwd() / ".claude"`` pointing at the real repo whenever the
# suite is launched from the repo root, so ANY import-time resolution a
# subject still performs would reach the live tree before a single case runs.
# The seam handles this per-case; this handles the window before the seam.
_ORIGINAL_CWD = Path.cwd()
_BOOT_CWD = _SANDBOX / "boot-neutral-cwd"
_BOOT_CWD.mkdir(parents=True, exist_ok=True)
os.chdir(_BOOT_CWD)

# ---------------------------------------------------------------------------
# INV-10 tripwire -- an audit hook on ``open``, not a stat() snapshot.
#
# The suite header used to claim "no real tree was read-modified or written"
# on the strength of a size/mtime snapshot. A snapshot cannot observe a READ:
# a subject that resolved the live <repo>/.claude/concepts and inventoried
# 160 real contracts would leave every sentinel byte-identical and the claim
# would print PASS. sys.addaudithook fires on every open() -- including the
# io.open_code path importlib uses -- so a read is observable.
#
# SCOPE, stated deliberately: the guarded set is the real *data* trees, not
# the whole of ``.claude``. The suite is REQUIRED to read the real
# ``.claude/scripts/*.py`` sources -- that is INV-6's self-relative subject
# resolution and case 5's INV-1 sweep -- and importlib must open the subject
# modules themselves. Guarding those would make the tripwire unimplementable.
# What INV-10 actually forbids is touching *knowledge and state*: contracts,
# north-stars, registries, the ledger, the logs, the caches.
#
# Violations are RECORDED, not raised: an exception thrown from inside an
# audit hook surfaces at an arbitrary call site and would read as a crash
# rather than as the specific invariant that broke.
# ---------------------------------------------------------------------------
def _guarded_data_prefixes() -> tuple[str, ...]:
    # The home paths here are NEGATIVE guards, not resolution (INV-1 exempt).
    leaves = (
        "concepts", "north-stars", "registries", "logs", "cache", "state",
        "contract-accuracy.json", "area-mapping.json",
    )
    out: list[str] = []
    # Repo tree: DATA leaves only. scripts/ and hooks/ must stay readable --
    # that is INV-6 subject resolution and case 5's source sweep.
    for leaf in leaves:
        out.append(str(_CLAUDE_DIR / leaf).replace("\\", "/").lower())
    # Home trees: the WHOLE .claude, for both the real workstation home and
    # the fabricated one. Nothing in this suite has any business opening
    # either, so the broadest guard is also the correct one -- and it is what
    # turns a direct Path.home() regression into a labelled FAIL instead of a
    # destroyed workstation file.
    for home in (_real_home(), Path.home()):
        out.append(str(home / ".claude").replace("\\", "/").lower())
    return tuple(dict.fromkeys(out))


_GUARDED_PREFIXES = _guarded_data_prefixes()
_AUDIT_VIOLATIONS: list[str] = []


def _inv10_audit_hook(event: str, args) -> None:
    if event != "open":
        return
    try:
        raw = args[0]
    except (IndexError, TypeError):
        return
    if isinstance(raw, int):          # fd-based open -- no path to judge
        return
    try:
        resolved = os.path.abspath(os.fspath(raw))
    except (TypeError, ValueError, OSError):
        return
    low = resolved.replace("\\", "/").lower()
    for guarded in _GUARDED_PREFIXES:
        # Plain startswith, not a "/"-anchored one: the atomic-write path
        # opens "<ledger>.tmp.<pid>", which an anchored test would let past.
        if low.startswith(guarded):
            mode = args[1] if len(args) > 1 else "?"
            _AUDIT_VIOLATIONS.append(f"open({resolved!r}, mode={mode!r})")
            return


sys.addaudithook(_inv10_audit_hook)

# scripts dir keeps import priority; hooks dir is APPENDED (same rule the
# bridge is bound by), so a hooks-side module can never shadow a script.
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
if str(_HOOKS_DIR) not in sys.path:
    sys.path.append(str(_HOOKS_DIR))


def _try_import(name: str):
    """Import a subject, returning (module | None, error-string | None).

    A missing subject must surface as ONE clearly-labelled failure, not as a
    collection error that masks every other case.
    """
    try:
        __import__(name)
        return sys.modules[name], None
    except BaseException as exc:  # noqa: BLE001 -- diagnostics, not control flow
        return None, f"{type(exc).__name__}: {exc}"


pp, _ERR_PP = _try_import("_project_paths")
derive_area, _ERR_DERIVE = _try_import("derive_area")
accuracy_update, _ERR_ACCURACY = _try_import("accuracy_update")
north_star_review, _ERR_NORTHSTAR = _try_import("north_star_review")
archive_stale_stubs, _ERR_STUBS = _try_import("archive_stale_stubs")
list_contracts, _ERR_LIST = _try_import("list_contracts")
# Both of these were absent from the import block until now, which meant a
# module-scope `raise RuntimeError` in either would have left the suite fully
# green: nothing referenced them, so nothing noticed they were unloadable.
cross_area_scan, _ERR_SCAN = _try_import("cross_area_scan")
validate_registries, _ERR_VALIDATE = _try_import("validate_registries")
_claude_paths, _ERR_BRIDGE = _try_import("_claude_paths")


# ---------------------------------------------------------------------------
# House-style accumulator (test_memory_common.py shape).
# ---------------------------------------------------------------------------
_PASS = 0
_FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  PASS  {name}")
    else:
        _FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def check_call(label: str, module, attr: str, expected, args: tuple = ()) -> None:
    """Assert module.attr(*args) == expected, with MISSING SYMBOL as its own
    distinguishable failure rather than an AttributeError that aborts the case."""
    if module is None:
        check(label, False, f"MISSING MODULE for .{attr} (RED: module did not import)")
        return
    fn = getattr(module, attr, None)
    if not callable(fn):
        check(
            label,
            False,
            f"MISSING SYMBOL {module.__name__}.{attr}() "
            f"(RED: locator not implemented yet)",
        )
        return
    try:
        got = fn(*args)
    except BaseException as exc:  # noqa: BLE001
        check(label, False, f"RAISED {type(exc).__name__}: {exc}")
        return
    check(label, got == expected, f"expected {expected!r}, got {got!r}")


def call_or_none(module, attr: str, args: tuple = ()):
    """Call module.attr(*args); return (value, err). Never raises."""
    if module is None:
        return None, "module did not import"
    fn = getattr(module, attr, None)
    if not callable(fn):
        return None, f"MISSING SYMBOL {module.__name__}.{attr}()"
    try:
        return fn(*args), None
    except BaseException as exc:  # noqa: BLE001
        return None, f"RAISED {type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# INV-11 seam B.
# ---------------------------------------------------------------------------
@contextmanager
def claude_roots_seam(
    project_root: Path | None,
    home_root: Path,
    cwd: Path,
    self_root: Path | None = None,
):
    """Neutralize ALL FOUR ranks of claude_roots(). See module docstring.

    ``self_root`` is rank 1 -- ``_project_paths.SELF_ROOT``, the ``.claude``
    the module itself lives in. It was added after review found the fix was
    only correct when the current directory happened to be the repo root:
    ``CLAUDE_PROJECT_DIR`` is unset in every plain shell, so resolution fell
    to cwd and then to an emptied ``~/.claude``, reproducing the original
    blindness from any subdirectory at exit 0.

    It MUST be neutralized here. Left alone it points at the real repository
    ``.claude``, which both defeats the isolation and violates INV-10 --
    every case would silently read the live 160 contracts. Default is a
    ``_absent`` subdirectory of the temp sandbox, i.e. a rank that exists as
    a path but holds nothing, so it never wins.
    """
    saved_cwd = os.getcwd()
    saved_env = os.environ.get("CLAUDE_PROJECT_DIR")
    saved_home = getattr(pp, "HOME", None) if pp is not None else None
    saved_self = getattr(pp, "SELF_ROOT", None) if pp is not None else None
    try:
        os.environ.pop("CLAUDE_PROJECT_DIR", None)          # rank 0
        if project_root is not None:
            os.environ["CLAUDE_PROJECT_DIR"] = str(project_root)
        if pp is not None:                                   # rank 1
            pp.SELF_ROOT = Path(self_root) if self_root is not None else (
                Path(cwd) / "_absent_self_root" / ".claude"
            )
        os.chdir(cwd)                                        # rank 2
        if pp is not None:
            pp.HOME = Path(home_root)                        # rank 3
        yield
    finally:
        os.chdir(saved_cwd)
        if saved_env is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = saved_env
        if pp is not None and saved_home is not None:
            pp.HOME = saved_home
        if pp is not None and saved_self is not None:
            pp.SELF_ROOT = saved_self


# ---------------------------------------------------------------------------
# INV-1 source sweep (AST). See the note at its call site in case 5.
# ---------------------------------------------------------------------------
_HOME_NAMES = {"HOME", "CLAUDE_ROOT", "USERPROFILE"}
_EXPANDUSER_NAMES = {"expanduser", "expandvars"}


def _is_home_expr(node) -> bool:
    """True when this expression evaluates to (something rooted at) $HOME."""
    if isinstance(node, ast.Call):
        fn = node.func
        if isinstance(fn, ast.Attribute):
            if fn.attr == "home":                       # Path.home()
                return True
            if fn.attr in _EXPANDUSER_NAMES:            # os.path.expanduser(...)
                return True
        if isinstance(fn, ast.Name) and fn.id in _EXPANDUSER_NAMES:
            return True
        # Path(<home expr>) / str(<home expr>) -- wrappers preserve home-ness.
        if isinstance(fn, ast.Name) and fn.id in {"Path", "str", "PurePath"}:
            return any(_is_home_expr(a) for a in node.args)
        return False
    if isinstance(node, ast.Name):
        return node.id in _HOME_NAMES
    if isinstance(node, ast.Attribute):
        if node.attr in _HOME_NAMES:                    # pp.HOME, _pp.HOME
            return True
        return _is_home_expr(node.value)                # Path.home().parent
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _is_home_expr(node.left)                 # HOME / "a" / "b"
    if isinstance(node, ast.Subscript):
        # os.environ["USERPROFILE"] / os.environ["HOME"]
        idx = node.slice
        if isinstance(idx, ast.Constant) and isinstance(idx.value, str):
            return idx.value.upper() in _HOME_NAMES
    return False


def _mentions_claude(node) -> bool:
    """True when any string constant in this subtree names ``.claude``."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            norm = sub.value.replace("\\", "/").lower()
            if norm == ".claude" or ".claude/" in norm or norm.endswith("/.claude"):
                return True
    return False


def _literal_home_claude(node) -> bool:
    """True for a direct ``"~/.claude..."`` string argument."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        norm = node.value.replace("\\", "/").lower()
        return norm.startswith("~/.claude")
    return False


def home_claude_hits(path: Path) -> tuple[list[str], str | None]:
    """Every ``<home expr>`` that reaches a ``.claude`` literal, in any form.

    Returns ``(["<line>: <form>", ...], error)``. Docstrings and comments are
    structurally invisible to this walk, which is the second reason it beats
    the line-regex: ``accuracy_update``'s docstring legitimately names
    ``~/.claude/logs/errors.jsonl`` and a text scan has to special-case it.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), str(path))
    except (OSError, SyntaxError) as exc:
        return [], f"could not parse {path.name}: {type(exc).__name__}: {exc}"

    hits: list[str] = []
    for node in ast.walk(tree):
        # HOME / ".claude" / ...
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            if _is_home_expr(node.left) and _mentions_claude(node.right):
                hits.append(f"{node.lineno}: divide")
                continue
        if isinstance(node, ast.Call):
            fn = node.func
            # HOME.joinpath(".claude", ...)
            if isinstance(fn, ast.Attribute) and fn.attr == "joinpath":
                if _is_home_expr(fn.value) and any(_mentions_claude(a) for a in node.args):
                    hits.append(f"{node.lineno}: joinpath")
                    continue
            # os.path.join(str(Path.home()), ".claude", ...)
            if isinstance(fn, ast.Attribute) and fn.attr == "join":
                if any(_is_home_expr(a) for a in node.args) and \
                        any(_mentions_claude(a) for a in node.args):
                    hits.append(f"{node.lineno}: os.path.join")
                    continue
            # expanduser("~/.claude...") / Path("~/.claude...")
            if any(_literal_home_claude(a) for a in node.args):
                hits.append(f"{node.lineno}: expanduser-literal")
                continue
    return sorted(set(hits)), None


def _is_under(path: Path, base: Path) -> bool:
    try:
        return Path(path).resolve().is_relative_to(Path(base).resolve())
    except (OSError, ValueError):
        return False


def assert_seam_isolated(label: str) -> None:
    """The seam's own positive control: prove no rank points at a real tree.

    Path.home() below is a NEGATIVE guard (INV-10 evidence), not resolution.
    """
    roots, err = call_or_none(pp, "claude_roots")
    if err:
        check(f"{label}: INV-11 seam isolated from every real tree", False, err)
        return
    real_trees = [_CLAUDE_DIR, _real_home() / ".claude", Path.home() / ".claude"]
    leaks = [str(r) for r in roots if any(_is_under(r, t) for t in real_trees)]
    check(
        f"{label}: INV-11 seam isolated from every real tree",
        not leaks,
        f"LEAKED {leaks} -- roots={[str(r) for r in roots]}",
    )


# ---------------------------------------------------------------------------
# Fixture content.
# ---------------------------------------------------------------------------
FIXTURE_CONTRACT = """\
# Fixture concept contract

**Status:** approved

**Files to touch:**
- `src/alpha/thing.cs`
- `src/beta/other.ts`
"""

MAPPING_PROJECT = {
    "schema_version": 1,
    "areas": {
        "alpha-area": {"patterns": ["src/alpha/"]},
        "beta-area": {"patterns": ["src/beta/"]},
    },
}
EXPECTED_PROJECT_AREAS = ["alpha-area", "beta-area"]

MAPPING_HOME = {
    "schema_version": 1,
    "areas": {"home-only-area": {"patterns": ["src/alpha/", "src/beta/"]}},
}
EXPECTED_HOME_AREAS = ["home-only-area"]

LEDGER_PROJECT = {
    "schema_version": 1,
    "areas": {
        "fixture-area": {
            "clean_streak": 2,
            "skip_eligible": False,
            "total_runs": 7,
            "last_updated": "2026-01-01T00:00:00Z",
            "last_contract": "fixture",
            "last_verdict": "clean",
            "history": [],
        }
    },
}
LEDGER_HOME = {
    "schema_version": 1,
    "areas": {
        "home-ledger-area": {
            "clean_streak": 1,
            "skip_eligible": False,
            "total_runs": 3,
            "last_updated": "2026-01-01T00:00:00Z",
            "last_contract": "fixture-home",
            "last_verdict": "clean",
            "history": [],
        }
    },
}

NORTH_STAR_TEMPLATE = """\
# {title}

**Status:** active
**Slug:** {slug}

## Aspiration

Fixture aspiration for {slug}.

## Anti-patterns (what would BLOCK us getting there)

- Something with a `fixture-snippet` in it.

## Current gap (Claude-maintained)

unknown

## Suggested next steps (Claude-maintained)

- nothing yet
"""

STUB_TEMPLATE = """\
# {slug}

**Status:** stub

Fixture follow-up stub.
"""

CONTRACT_TEMPLATE = """\
# {title}

**Status:** {status}

**Files to touch:**
- `src/alpha/thing.cs`
"""

#: case 9 -- one LIVE backticked path (resolves under the fixture repo root)
#: and one DEAD one. Both must be counted, so `dead == 1` is not satisfiable
#: by a validator that reports everything dead OR everything alive.
MECHANISMS_FIXTURE = """\
# Fixture MECHANISMS

## Project: ValidateRoot

- **Live mechanism** -- `src/live/thing.cs` -- this file exists on disk.
- **Dead mechanism** -- `src/dead/gone.cs` -- this file does NOT exist.

```
- **Fenced, must be ignored** -- `src/fenced/ignored.cs`
```
"""


def _write_json(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def build_populated_root(
    root: Path,
    *,
    mapping,
    ledger,
    north_star_slugs: tuple[str, ...],
    contract_titles: tuple[str, ...],
    stub_slugs: tuple[str, ...],
) -> Path:
    """Build a FLAT (repo-shaped) .claude tree. INV-8: flat only, no
    project-partitioned variant -- that tolerance was dropped at Q7."""
    claude = root / ".claude"
    _write_json(claude / "area-mapping.json", mapping)
    _write_json(claude / "contract-accuracy.json", ledger)
    _write_text(claude / "registries" / "MECHANISMS.md", "# Fixture MECHANISMS\n")
    _write_text(claude / "registries" / "VOCABULARY.md", "# Fixture VOCABULARY\n")
    _write_text(claude / "registries" / "JOURNAL.md", "# Fixture JOURNAL\n")

    for i, slug in enumerate(north_star_slugs, start=1):
        _write_text(
            claude / "north-stars" / f"2026-01-0{i}-{slug}.md",
            NORTH_STAR_TEMPLATE.format(title=f"North star {slug}", slug=slug),
        )
    if north_star_slugs:
        # Underscore-prefixed files must be excluded by discover().
        _write_text(
            claude / "north-stars" / "_template.md",
            NORTH_STAR_TEMPLATE.format(title="Template", slug="template"),
        )

    for i, title in enumerate(contract_titles, start=1):
        _write_text(
            claude / "concepts" / f"2026-02-0{i}-{title}.md",
            CONTRACT_TEMPLATE.format(title=title, status="approved"),
        )
    for i, slug in enumerate(stub_slugs, start=1):
        _write_text(
            claude / "concepts" / "followups" / f"2026-03-0{i}-{slug}.followup.md",
            STUB_TEMPLATE.format(slug=slug),
        )
    if stub_slugs:
        # Already-archived stub must NOT be re-collected (idempotence).
        _write_text(
            claude / "concepts" / "followups" / "2026-03-09-old.followup.archived.md",
            STUB_TEMPLATE.format(slug="old"),
        )
    (claude / "cache").mkdir(parents=True, exist_ok=True)
    return root


def build_empty_root(root: Path) -> Path:
    """A .claude that EXISTS but holds none of the sought files.

    INV-4's corrected rule: a bare directory-existence test would let this
    win and report zero -- the bug under repair, one rank down.
    """
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    return root


# ---------------------------------------------------------------------------
# Case 1 -- project-local layout present (POSITIVE CONTROL for 2 and 3).
# ---------------------------------------------------------------------------
def case1_project_local_wins(env) -> None:
    print("\ncase 1 -- project-local layout present")
    proj, home, cwd, fixture = env["proj"], env["home"], env["cwd"], env["fixture"]
    pc = proj / ".claude"

    with claude_roots_seam(project_root=proj, home_root=home, cwd=cwd):
        assert_seam_isolated("case1")

        # Existing two-layer helper -- proves the seam itself works. If this
        # FAILS, every other case-1 failure is harness noise, not defect.
        check_call(
            "case1: registry() -> project-local (seam positive control)",
            pp, "registry", pc / "registries" / "MECHANISMS.md", ("MECHANISMS.md",),
        )

        check_call(
            "case1: area_mapping_path() -> project-local",
            pp, "area_mapping_path", pc / "area-mapping.json",
        )
        check_call(
            "case1: accuracy_state_path() -> project-local",
            pp, "accuracy_state_path", pc / "contract-accuracy.json",
        )
        check_call(
            "case1: cache_dir() -> project-local",
            pp, "cache_dir", pc.joinpath(*EXPECTED_CACHE_LEAF),
        )

        roots, err = call_or_none(pp, "concepts_roots")
        if err:
            check("case1: first_populated_dir(concepts_roots) -> project-local", False, err)
        else:
            check_call(
                "case1: first_populated_dir(concepts_roots) -> project-local",
                pp, "first_populated_dir", pc / "concepts", (roots, "*.md"),
            )

        ns_roots, err = call_or_none(pp, "north_stars_roots")
        if err:
            check("case1: first_populated_dir(north_stars_roots) -> project-local", False, err)
        else:
            check_call(
                "case1: first_populated_dir(north_stars_roots) -> project-local",
                pp, "first_populated_dir", pc / "north-stars", (ns_roots, "*.md"),
            )

        # Behaviour through the real consumer, asserted on LITERAL slugs.
        mapping, err = call_or_none(derive_area, "load_area_mapping")
        check(
            "case1: load_area_mapping() reads the project-local map",
            err is None and sorted(mapping or {}) == EXPECTED_PROJECT_AREAS,
            err or f"expected keys {EXPECTED_PROJECT_AREAS}, got {sorted(mapping or {})}",
        )

        areas, err = call_or_none(derive_area, "derive_areas", (fixture,))
        check(
            "case1: derive_areas() returns the LITERAL project buckets",
            err is None and areas == EXPECTED_PROJECT_AREAS,
            err or f"expected {EXPECTED_PROJECT_AREAS}, got {areas!r}",
        )

        rows, err = call_or_none(accuracy_update, "dump_table")
        check(
            "case1: dump_table() reads the project-local ledger",
            err is None and [r["area"] for r in (rows or [])] == ["fixture-area"],
            err or f"expected ['fixture-area'], got {[r['area'] for r in (rows or [])]!r}",
        )

        # -- query() POSITIVE control ---------------------------------------
        # Case 3 asserts query() -> None for an unknown area. On its own that
        # is unfalsifiable: `def query(area): return None` satisfies it. Only
        # a literal-valued hit through the same code path makes it a test.
        q, err = call_or_none(accuracy_update, "query", ("fixture-area",))
        check(
            "case1: query() returns the LITERAL clean_streak from the ledger",
            err is None and isinstance(q, dict) and q.get("clean_streak") == 2,
            err or f"expected clean_streak 2, got {q!r}",
        )
        check(
            "case1: query() returns the LITERAL total_runs from the ledger",
            err is None and isinstance(q, dict) and q.get("total_runs") == 7,
            err or f"expected total_runs 7, got {q!r}",
        )

        # -- derive_area CLI POSITIVE control -------------------------------
        # Case 3 asserts the CLI prints 'uncategorized' and exits 0. On its
        # own that is satisfied by `print("uncategorized"); return 0` -- the
        # blind script the work item exists to repair would PASS it. The
        # literal two-line stdout below is what makes the pair falsifiable.
        buf = io.StringIO()
        rc, exc = None, None
        try:
            with redirect_stdout(buf):
                rc = derive_area.main([str(fixture)])
        except BaseException as e:  # noqa: BLE001
            exc = f"{type(e).__name__}: {e}"
        check(
            "case1: derive_area CLI exits 0 on a resolvable map",
            exc is None and rc == 0,
            exc or f"rc={rc!r}",
        )
        check(
            "case1: derive_area CLI prints the LITERAL 'alpha-area\\nbeta-area\\n'",
            buf.getvalue() == "alpha-area\nbeta-area\n",
            f"stdout={buf.getvalue()!r}",
        )

        buf = io.StringIO()
        rc, exc = None, None
        try:
            with redirect_stdout(buf):
                rc = derive_area.main(["--dump-mapping"])
        except BaseException as e:  # noqa: BLE001
            exc = f"{type(e).__name__}: {e}"
        expected_dump = json.dumps(
            {"alpha-area": ["src/alpha/"], "beta-area": ["src/beta/"]}, indent=2
        )
        check(
            "case1: derive_area --dump-mapping exits 0",
            exc is None and rc == 0,
            exc or f"rc={rc!r}",
        )
        check(
            "case1: derive_area --dump-mapping prints the LITERAL fixture map",
            buf.getvalue().strip() == expected_dump,
            f"expected {expected_dump!r}, got {buf.getvalue()!r}",
        )

        # -- zero-argument resolvers, asserted DIRECTLY ----------------------
        # Everywhere else these are exercised by handing the subject a root
        # the fixture already knows -- which tests the walk, not the
        # resolution. Repointing any one of them at a home path would stay
        # green without these four.
        check_call(
            "case1: archive_stale_stubs.default_root() -> project-local concepts",
            archive_stale_stubs, "default_root", pc / "concepts",
        )
        check_call(
            "case1: list_contracts.concepts_root() -> project-local concepts",
            list_contracts, "concepts_root", pc / "concepts",
        )
        check_call(
            "case1: north_star_review.north_stars_root() -> project-local north-stars",
            north_star_review, "north_stars_root", pc / "north-stars",
        )
        check_call(
            "case1: validate_registries.concepts_root() -> project-local concepts",
            validate_registries, "concepts_root", pc / "concepts",
        )
        check_call(
            "case1: validate_registries.mechanisms_file() -> project-local registry",
            validate_registries, "mechanisms_file", pc / "registries" / "MECHANISMS.md",
        )
        check_call(
            "case1: validate_registries.vocabulary_file() -> project-local registry",
            validate_registries, "vocabulary_file", pc / "registries" / "VOCABULARY.md",
        )
        check_call(
            "case1: cross_area_scan.journal_path() -> project-local registry",
            cross_area_scan, "journal_path", pc / "registries" / "JOURNAL.md",
        )
        check_call(
            "case1: cross_area_scan.cache_dir() -> project-local scan cache",
            cross_area_scan, "cache_dir",
            pc.joinpath(*EXPECTED_CACHE_LEAF) / "cross-area-scans",
        )

        # default_repo_root(): the hardcoded d:/Dev root's replacement. Both
        # branches asserted -- the match branch AND the cwd fallback -- so
        # `return Path.cwd()` unconditionally cannot survive.
        check_call(
            "case1: default_repo_root('FakeProject') -> the resolved project root",
            north_star_review, "default_repo_root", proj, ("FakeProject",),
        )
        check_call(
            "case1: default_repo_root('NoSuchProject') -> cwd fallback",
            north_star_review, "default_repo_root", Path(cwd).resolve(),
            ("NoSuchProject",),
        )


# ---------------------------------------------------------------------------
# Case 2 -- global-only fallback. REQUIRES seam B.
# ---------------------------------------------------------------------------
def case2b_self_root_beats_cwd(env) -> None:
    """The scenario the first implementation got wrong.

    A plain shell has no ``CLAUDE_PROJECT_DIR``, and a developer runs
    ``py -3 .claude/scripts/list_contracts.py`` from a SUBDIRECTORY. Before
    ``SELF_ROOT`` existed, rank 0 was absent, rank "cwd" had no ``.claude``,
    and resolution fell through to an emptied ``~/.claude`` -- reproducing
    the original defect verbatim at exit 0 ("No concept contracts found"
    against 160 real contracts).

    Here the home root is POPULATED with different content, so falling
    through is not merely empty, it is *wrong* -- and the assertion says
    which root won, not merely that something was found. Without the
    SELF_ROOT rank every check below resolves to the home fixture and fails.
    """
    print("\ncase 2b -- SELF_ROOT wins over cwd and a populated global root")
    proj, home, cwd, fixture = env["proj"], env["home"], env["cwd"], env["fixture"]
    pc = proj / ".claude"
    hc = home / ".claude"

    # No CLAUDE_PROJECT_DIR, cwd is a neutral directory elsewhere, home is
    # populated -- but SELF_ROOT points into the subject tree, as it does in
    # production where the scripts ship inside the .claude they resolve.
    with claude_roots_seam(
        project_root=None, home_root=home, cwd=cwd, self_root=pc
    ):
        assert_seam_isolated("case2b")

        check_call(
            "case2b: registry() -> SELF_ROOT, not the populated global",
            pp, "registry", pc / "registries" / "MECHANISMS.md", ("MECHANISMS.md",),
        )
        check_call(
            "case2b: area_mapping_path() -> SELF_ROOT",
            pp, "area_mapping_path", pc / "area-mapping.json",
        )
        check_call(
            "case2b: accuracy_state_path() -> SELF_ROOT",
            pp, "accuracy_state_path", pc / "contract-accuracy.json",
        )

        # Literal slugs, not "non-empty": the home fixture also resolves to a
        # non-empty list, so only the specific value distinguishes the roots.
        areas, err = call_or_none(derive_area, "derive_areas", (fixture,))
        check(
            "case2b: derive_areas() returns the SELF_ROOT buckets, not the global ones",
            err is None and areas == EXPECTED_PROJECT_AREAS,
            err or f"expected {EXPECTED_PROJECT_AREAS}, got {areas!r}",
        )

        rows, err = call_or_none(accuracy_update, "dump_table")
        check(
            "case2b: dump_table() reads the SELF_ROOT ledger, not the global one",
            err is None and [r["area"] for r in (rows or [])] == ["fixture-area"],
            err or f"expected ['fixture-area'], got {[r['area'] for r in (rows or [])]!r}",
        )

        # Negative control on the loser: the global root is populated and
        # must NOT have supplied any of the above.
        check(
            "case2b: the populated global root did NOT win",
            pp.area_mapping_path() != hc / "area-mapping.json",
            f"resolved to the global root {hc / 'area-mapping.json'}",
        )


def case2c_empty_high_rank_loses_to_populated_low_rank(env) -> None:
    """INV-4: *populated*, never merely *existing*.

    No other fixture in this suite presents a root that EXISTS but is EMPTY
    ranked ABOVE a populated one, so ``first_populated_dir`` could be reverted
    to::

        for candidate in candidates:
            if candidate.is_dir():
                return candidate

    and every case stayed green -- while ``/list-contracts`` reported zero of
    160 contracts, silently, at exit 0. That is the defect under repair,
    reconstituted one rank down, and it is exactly the shape the contract
    calls out (INV-4's "corrected from the draft" note).

    Here rank 1 (SELF_ROOT) holds ``concepts/`` and ``north-stars/``
    directories that exist and are EMPTY; rank 3 (home) is populated. The
    empty root must LOSE -- asserted on the resolved path, and again on the
    literal inventories three consumers return.
    """
    print("\ncase 2c -- an EMPTY high-rank root loses to a populated low-rank one (INV-4)")
    empty_self, home, cwd = env["empty_dirs_self"], env["home"], env["cwd"]
    sc = empty_self / ".claude"
    hc = home / ".claude"

    # Fixture control FIRST: if the empty directories are not actually on
    # disk, every assertion below passes for the wrong reason.
    check(
        "case2c: fixture -- rank-1 concepts/ and north-stars/ EXIST and are EMPTY",
        (sc / "concepts").is_dir() and not any((sc / "concepts").iterdir())
        and (sc / "north-stars").is_dir() and not any((sc / "north-stars").iterdir()),
        f"concepts={list((sc / 'concepts').glob('*')) if (sc / 'concepts').is_dir() else 'MISSING'} "
        f"north-stars={list((sc / 'north-stars').glob('*')) if (sc / 'north-stars').is_dir() else 'MISSING'}",
    )

    with claude_roots_seam(
        project_root=None, home_root=home, cwd=cwd, self_root=sc
    ):
        assert_seam_isolated("case2c")

        # The empty rank must be present in the search order and must lose.
        roots, err = call_or_none(pp, "concepts_roots")
        check(
            "case2c: the EMPTY concepts root is genuinely ranked above the populated one",
            err is None and roots is not None
            and (sc / "concepts") in roots and (hc / "concepts") in roots
            and roots.index(sc / "concepts") < roots.index(hc / "concepts"),
            err or f"roots={[str(r) for r in (roots or [])]}",
        )
        if err is None and roots is not None:
            check_call(
                "case2c: first_populated_dir(concepts) skips the EMPTY root",
                pp, "first_populated_dir", hc / "concepts", (roots, "*.md"),
            )

        ns_roots, err = call_or_none(pp, "north_stars_roots")
        if err is None and ns_roots is not None:
            check_call(
                "case2c: first_populated_dir(north-stars) skips the EMPTY root",
                pp, "first_populated_dir", hc / "north-stars", (ns_roots, "*.md"),
            )

        # -- and now through the three real consumers, on LITERAL values -----
        check_call(
            "case2c: list_contracts.concepts_root() skips the EMPTY root",
            list_contracts, "concepts_root", hc / "concepts",
        )
        rows, err = call_or_none(list_contracts, "collect", (None, None))
        names = sorted(r["path"].name for r in (rows or []))
        expected_rows = sorted([
            "2026-02-01-home-one.md",
            "2026-03-01-home-one.followup.md",
            "2026-03-09-old.followup.archived.md",
        ])
        check(
            "case2c: collect() returns the populated root's LITERAL inventory",
            err is None and names == expected_rows,
            err or f"expected {expected_rows}, got {names}",
        )

        check_call(
            "case2c: north_star_review.north_stars_root() skips the EMPTY root",
            north_star_review, "north_stars_root", hc / "north-stars",
        )
        stars, err = call_or_none(north_star_review, "discover", (None,))
        slugs = sorted(ns.slug for ns in (stars or []))
        check(
            "case2c: discover(None) returns the populated root's LITERAL slugs",
            err is None and slugs == ["home-ns"],
            err or f"expected ['home-ns'], got {slugs}",
        )

        check_call(
            "case2c: archive_stale_stubs.default_root() skips the EMPTY root",
            archive_stale_stubs, "default_root", hc / "concepts",
        )
        root, err = call_or_none(archive_stale_stubs, "default_root")
        if err:
            check("case2c: find_followup_stubs() returns the populated root's LITERAL stubs",
                  False, err)
        else:
            found, err = call_or_none(
                archive_stale_stubs, "find_followup_stubs", (root,)
            )
            stub_names = sorted(p.name for p in (found or []))
            check(
                "case2c: find_followup_stubs() returns the populated root's LITERAL stubs",
                err is None and stub_names == ["2026-03-01-home-one.followup.md"],
                err or f"expected ['2026-03-01-home-one.followup.md'], got {stub_names}",
            )


def case2_global_fallback(env) -> None:
    print("\ncase 2 -- project-local absent, global root present")
    home, cwd, fixture = env["home"], env["cwd"], env["fixture"]
    hc = home / ".claude"

    # CLAUDE_PROJECT_DIR popped entirely: "project-local absent" in the
    # strongest sense. cwd is a neutral temp dir with no .claude.
    with claude_roots_seam(project_root=None, home_root=home, cwd=cwd):
        assert_seam_isolated("case2")

        check_call(
            "case2: registry() -> global (seam positive control)",
            pp, "registry", hc / "registries" / "MECHANISMS.md", ("MECHANISMS.md",),
        )
        check_call(
            "case2: area_mapping_path() -> global",
            pp, "area_mapping_path", hc / "area-mapping.json",
        )
        check_call(
            "case2: accuracy_state_path() -> global",
            pp, "accuracy_state_path", hc / "contract-accuracy.json",
        )
        check_call(
            "case2: cache_dir() -> global",
            pp, "cache_dir", hc.joinpath(*EXPECTED_CACHE_LEAF),
        )

        roots, err = call_or_none(pp, "concepts_roots")
        if err:
            check("case2: first_populated_dir(concepts_roots) -> global", False, err)
        else:
            check_call(
                "case2: first_populated_dir(concepts_roots) -> global",
                pp, "first_populated_dir", hc / "concepts", (roots, "*.md"),
            )

        ns_roots, err = call_or_none(pp, "north_stars_roots")
        if err:
            check("case2: first_populated_dir(north_stars_roots) -> global", False, err)
        else:
            check_call(
                "case2: first_populated_dir(north_stars_roots) -> global",
                pp, "first_populated_dir", hc / "north-stars", (ns_roots, "*.md"),
            )

        areas, err = call_or_none(derive_area, "derive_areas", (fixture,))
        check(
            "case2: derive_areas() returns the LITERAL global buckets",
            err is None and areas == EXPECTED_HOME_AREAS,
            err or f"expected {EXPECTED_HOME_AREAS}, got {areas!r}",
        )

        rows, err = call_or_none(accuracy_update, "dump_table")
        check(
            "case2: dump_table() reads the global ledger",
            err is None and [r["area"] for r in (rows or [])] == ["home-ledger-area"],
            err or f"expected ['home-ledger-area'], got {[r['area'] for r in (rows or [])]!r}",
        )


# ---------------------------------------------------------------------------
# Case 3 -- missing in BOTH layouts. INV-3 fail-open.
# ---------------------------------------------------------------------------
def case3_missing_in_both(env) -> None:
    print("\ncase 3 -- missing in BOTH layouts (INV-3 fail-open)")
    proj, home, cwd, fixture = (
        env["empty_proj"], env["empty_home"], env["cwd"], env["fixture"],
    )
    pc = proj / ".claude"

    with claude_roots_seam(project_root=proj, home_root=home, cwd=cwd):
        assert_seam_isolated("case3")

        # INV-5: nothing exists anywhere -> the PREFERRED (rank-0, repo-shaped)
        # candidate, so a writer creates the file in the right place.
        check_call(
            "case3: area_mapping_path() -> preferred path on absence (INV-5)",
            pp, "area_mapping_path", pc / "area-mapping.json",
        )
        check_call(
            "case3: accuracy_state_path() -> preferred path on absence (INV-5)",
            pp, "accuracy_state_path", pc / "contract-accuracy.json",
        )

        mapping, err = call_or_none(derive_area, "load_area_mapping")
        check(
            "case3: load_area_mapping() -> {} exactly",
            err is None and mapping == {},
            err or f"expected {{}}, got {mapping!r}",
        )

        areas, err = call_or_none(derive_area, "derive_areas", (fixture,))
        check(
            "case3: derive_areas() -> ['uncategorized'] exactly",
            err is None and areas == ["uncategorized"],
            err or f"expected ['uncategorized'], got {areas!r}",
        )

        # Exit 0 AND the literal stdout -- never exit code alone.
        buf = io.StringIO()
        rc, exc = None, None
        try:
            with redirect_stdout(buf):
                rc = derive_area.main([str(fixture)])
        except BaseException as e:  # noqa: BLE001
            exc = f"{type(e).__name__}: {e}"
        check(
            "case3: derive_area CLI exits 0 with no exception (INV-3)",
            exc is None and rc == 0,
            exc or f"rc={rc!r}",
        )
        check(
            "case3: derive_area CLI prints 'uncategorized'",
            buf.getvalue().strip() == "uncategorized",
            f"stdout={buf.getvalue()!r}",
        )

        found, err = call_or_none(
            archive_stale_stubs, "find_followup_stubs", (pc / "concepts",)
        )
        check(
            "case3: find_followup_stubs() -> [] exactly",
            err is None and found == [],
            err or f"expected [], got {found!r}",
        )

        stars, err = call_or_none(north_star_review, "discover", (None,))
        check(
            "case3: north_star_review.discover(None) -> [] exactly",
            err is None and stars == [],
            err or f"expected [], got {stars!r}",
        )

        rows, err = call_or_none(list_contracts, "collect", (None, None))
        check(
            "case3: list_contracts.collect() -> [] exactly",
            err is None and rows == [],
            err or f"expected [], got {rows!r}",
        )

        table, err = call_or_none(accuracy_update, "dump_table")
        check(
            "case3: dump_table() -> [] exactly (neutral ledger)",
            err is None and table == [],
            err or f"expected [], got {table!r}",
        )
        q, err = call_or_none(accuracy_update, "query", ("fixture-area",))
        check(
            "case3: query() -> None on an unknown area",
            err is None and q is None,
            err or f"expected None, got {q!r}",
        )


# ---------------------------------------------------------------------------
# Case 4 -- FLAT layout discovery (INV-8). LITERAL counts.
# ---------------------------------------------------------------------------
def case4_flat_layout_discovery(env) -> None:
    print("\ncase 4 -- flat-layout discovery (INV-8, flat ONLY)")
    proj, home, cwd = env["proj"], env["home"], env["cwd"]
    pc = proj / ".claude"

    with claude_roots_seam(project_root=proj, home_root=home, cwd=cwd):
        assert_seam_isolated("case4")

        # -- archive_stale_stubs: flat concepts/followups/ --------------------
        found, err = call_or_none(
            archive_stale_stubs, "find_followup_stubs", (pc / "concepts",)
        )
        names = sorted(p.name for p in (found or []))
        expected_stubs = [
            "2026-03-01-one.followup.md",
            "2026-03-02-two.followup.md",
            "2026-03-03-three.followup.md",
        ]
        check(
            "case4: find_followup_stubs() finds EXACTLY 3 flat stubs",
            err is None and len(found or []) == 3,
            err or f"expected 3, got {len(found or [])} -> {names}",
        )
        check(
            "case4: find_followup_stubs() returns the LITERAL stub names",
            err is None and names == sorted(expected_stubs),
            err or f"expected {sorted(expected_stubs)}, got {names}",
        )

        # -- north_star_review: flat north-stars/*.md -------------------------
        stars, err = call_or_none(north_star_review, "discover", (None,))
        slugs = sorted(ns.slug for ns in (stars or []))
        check(
            "case4: discover() finds EXACTLY 3 flat north-stars",
            err is None and len(stars or []) == 3,
            err or f"expected 3, got {len(stars or [])} -> {slugs}",
        )
        check(
            "case4: discover() returns the LITERAL north-star slugs",
            err is None and slugs == ["alpha-ns", "beta-ns", "gamma-ns"],
            err or f"expected ['alpha-ns', 'beta-ns', 'gamma-ns'], got {slugs}",
        )
        # Fixture control -- without it, "template not in slugs" passes
        # vacuously against the empty list the unfixed code returns.
        on_disk = sorted(p.name for p in (pc / "north-stars").glob("*.md"))
        check(
            "case4: fixture holds 4 north-star files incl. _template.md",
            len(on_disk) == 4 and "_template.md" in on_disk,
            f"on_disk={on_disk}",
        )
        check(
            "case4: discover() excludes the _template.md file (3 of 4 on disk)",
            err is None and len(stars or []) == 3 and "template" not in slugs,
            err or f"on_disk={on_disk} slugs={slugs}",
        )
        projects = sorted({ns.project for ns in (stars or [])})
        check(
            "case4: north-star .project is the project name, not 'north-stars'",
            err is None and projects == ["FakeProject"],
            err or f"expected ['FakeProject'], got {projects}",
        )

        # -- list_contracts: flat concepts/ ----------------------------------
        rows, err = call_or_none(list_contracts, "collect", (None, None))
        # 2 contracts + 3 followup stubs + 1 archived stub = 6 *.md under rglob.
        check(
            "case4: collect() inventories EXACTLY 6 flat markdown files",
            err is None and len(rows or []) == 6,
            err or f"expected 6, got {len(rows or [])} -> "
                   f"{sorted(r['path'].name for r in (rows or []))}",
        )
        row_projects = sorted({r["project"] for r in (rows or [])})
        check(
            "case4: contract .project is the project name, not '<loose>'",
            err is None and row_projects == ["FakeProject"],
            err or f"expected ['FakeProject'], got {row_projects}",
        )


# ---------------------------------------------------------------------------
# Case 5 -- INV-2 call-time resolution + INV-1 source sweep.
# ---------------------------------------------------------------------------
def case5_no_import_time_capture(env) -> None:
    print("\ncase 5 -- INV-2 call-time resolution / INV-1 no home-resolved data")
    root_a, root_b, home, cwd = env["root_a"], env["root_b"], env["empty_home"], env["cwd"]

    # The subject modules were imported LONG before either root existed.
    with claude_roots_seam(project_root=root_a, home_root=home, cwd=cwd):
        assert_seam_isolated("case5a")
        map_a, err_a = call_or_none(derive_area, "load_area_mapping")
        rows_a, lerr_a = call_or_none(list_contracts, "collect", (None, None))

    with claude_roots_seam(project_root=root_b, home_root=home, cwd=cwd):
        assert_seam_isolated("case5b")
        map_b, err_b = call_or_none(derive_area, "load_area_mapping")
        rows_b, lerr_b = call_or_none(list_contracts, "collect", (None, None))

    check(
        "case5: load_area_mapping() reflects root A (positive control)",
        err_a is None and sorted(map_a or {}) == ["root-a-area"],
        err_a or f"expected ['root-a-area'], got {sorted(map_a or {})}",
    )
    check(
        "case5: load_area_mapping() reflects root B AFTER the roots moved",
        err_b is None and sorted(map_b or {}) == ["root-b-area"],
        err_b or f"expected ['root-b-area'], got {sorted(map_b or {})}",
    )
    check(
        "case5: the two calls DIFFER (no import-time capture)",
        err_a is None and err_b is None and map_a != map_b,
        f"A={sorted(map_a or {})} B={sorted(map_b or {})}",
    )
    check(
        "case5: collect() reflects root A (1 contract)",
        lerr_a is None and len(rows_a or []) == 1,
        lerr_a or f"expected 1, got {len(rows_a or [])}",
    )
    check(
        "case5: collect() reflects root B (2 contracts) AFTER the roots moved",
        lerr_b is None and len(rows_b or []) == 2,
        lerr_b or f"expected 2, got {len(rows_b or [])}",
    )

    # -- INV-1 source sweep: no script may resolve a .claude data file from
    # home. AST-based, not line-regex.
    #
    # The regex this replaces was `(Path.home()|HOME|CLAUDE_ROOT) / ".claude"`.
    # It required the literal ``/ ".claude"`` operator form and therefore
    # missed every other spelling of the same thing:
    #   Path.home().joinpath(".claude", "area-mapping.json")
    #   os.path.join(str(Path.home()), ".claude", "contract-accuracy.json")
    #   Path(os.path.expanduser("~/.claude")) / "concepts"
    #   HOME.joinpath(".claude")
    # A line-regex is evadable by reformatting; the parse tree is not. Proven
    # falsifiable by injecting each of the four forms above -- see HANDOFF.
    for name in _INV1_SWEEP_FILES:
        path = _SCRIPTS_DIR / name
        if not path.is_file():
            check(f"case5: INV-1 -- {name} resolves no .claude data from home", False,
                  f"MISSING FILE {path}")
            continue
        hits, parse_err = home_claude_hits(path)
        if parse_err:
            check(f"case5: INV-1 -- {name} resolves no .claude data from home",
                  False, parse_err)
            continue
        check(
            f"case5: INV-1 -- {name} resolves no .claude data from home",
            not hits,
            f"home-rooted .claude resolution at {hits}",
        )

    # Positive control for the sweep itself. Without it, a sweep that always
    # returned [] -- a broken walker, a typo'd node type -- would report a
    # clean bill of health for all eight files and nothing would notice.
    probe = _write_text(
        env["sandbox"] / "inv1_probe" / "evader.py",
        "from pathlib import Path\n"
        "import os\n"
        "A = Path.home().joinpath('.claude', 'area-mapping.json')\n"
        "B = os.path.join(str(Path.home()), '.claude', 'contract-accuracy.json')\n"
        "C = Path(os.path.expanduser('~/.claude')) / 'concepts'\n"
        "HOME = Path.home()\n"
        "D = HOME / '.claude' / 'north-stars'\n",
    )
    probe_hits, probe_err = home_claude_hits(probe)
    check(
        "case5: INV-1 sweep CATCHES all four evasive home/.claude spellings",
        probe_err is None and sorted(probe_hits) == ["3: joinpath", "4: os.path.join",
                                                    "5: expanduser-literal", "7: divide"],
        probe_err or f"expected 4 labelled hits, got {sorted(probe_hits)}",
    )

    # -- the hardcoded d:/Dev repo root must be GONE, not merely different --
    # getattr(ns, "DEFAULT_REPO_ROOTS", "") returns "" for a symbol that no
    # longer exists, and "" never contains the hardcoded path, so the old
    # form was a tautology that would pass forever regardless of what
    # north_star_review actually did. hasattr is falsifiable; the behavioural
    # replacement is default_repo_root(), asserted in both branches in case 1.
    ns = north_star_review
    check(
        "case5: north_star_review.DEFAULT_REPO_ROOTS is DELETED, not renamed",
        ns is not None and not hasattr(ns, "DEFAULT_REPO_ROOTS"),
        f"symbol still present: {getattr(ns, 'DEFAULT_REPO_ROOTS', None)!r}",
    )
    check(
        "case5: north_star_review exposes default_repo_root() in its place",
        ns is not None and callable(getattr(ns, "default_repo_root", None)),
        "default_repo_root() missing -- nothing replaced the deleted constant",
    )


# ---------------------------------------------------------------------------
# Case 6 -- INV-1 negative: the bridge raises, it does NOT fall back to home.
# ---------------------------------------------------------------------------
_BRIDGE_DRIVER = '''\
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
try:
    import _claude_paths as cp
except BaseException as exc:
    out = {"outcome": type(exc).__name__, "message": str(exc)}
else:
    p0 = sys.path[0].replace("\\\\", "/").lower()
    pp = getattr(cp, "_pp", None)
    out = {
        "outcome": "imported",
        "exports": sorted(n for n in dir(cp) if not n.startswith("__")),
        "hooks_at_zero": p0.rstrip("/").endswith("/hooks"),
        # PROVENANCE: which _project_paths.py actually got loaded, and
        # whether it was a decoy planted in the fabricated $HOME.
        "pp_file": getattr(pp, "__file__", None),
        "pp_marker": getattr(pp, "MARKER", None),
    }
# Reported on BOTH branches: case 6c's harness control needs to know what
# Path.home() resolved to inside the child even when the import raised.
out["home"] = str(Path.home())
print("RESULT " + json.dumps(out))
'''


def _run_bridge_driver(driver: Path, scripts_dir: Path, cwd: Path, extra_env=None):
    """Run the bridge import in a CLEAN interpreter.

    In-process, the suite has already imported _project_paths, so a bridge
    that merely did `import _project_paths` would succeed from sys.modules
    and the ImportError case would pass vacuously. A subprocess with a
    scrubbed environment removes that masking.
    """
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("PYTHONPATH", None)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, str(driver), str(scripts_dir)],
        cwd=str(cwd), env=env, capture_output=True, text=True, timeout=60,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT "):
            return json.loads(line[len("RESULT "):]), proc
    return None, proc


def case6_bridge_raises_without_hooks(env) -> None:
    print("\ncase 6 -- INV-1 negative: bridge raises ImportError, no home fallback")
    sandbox, cwd = env["sandbox"], env["cwd"]

    if not _BRIDGE_SRC.is_file():
        detail = (
            f"MISSING FILE {_BRIDGE_SRC} "
            f"(RED: the _claude_paths bridge is not implemented yet)"
        )
        check("case6: bridge raises ImportError when hooks/ is absent", False, detail)
        check("case6: ImportError names the path it looked for", False, detail)
        check("case6: bridge imports fine WITH a hooks sibling (positive control)", False, detail)
        check("case6: bridge APPENDS hooks dir (scripts keep sys.path priority)", False, detail)
        check("case6: bridge re-exports the locator surface", False, detail)
        return

    driver = _write_text(sandbox / "bridge_driver.py", _BRIDGE_DRIVER)

    # -- negative: no hooks/ sibling -------------------------------------
    no_hooks = sandbox / "bridge_no_hooks" / "scripts"
    no_hooks.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_BRIDGE_SRC, no_hooks / "_claude_paths.py")
    out, proc = _run_bridge_driver(driver, no_hooks, cwd)
    if out is None:
        detail = f"no RESULT line. stdout={proc.stdout!r} stderr={proc.stderr!r}"
        check("case6: bridge raises ImportError when hooks/ is absent", False, detail)
        check("case6: ImportError names the path it looked for", False, detail)
    else:
        check(
            "case6: bridge raises ImportError when hooks/ is absent",
            out.get("outcome") == "ImportError",
            f"outcome={out.get('outcome')!r} message={out.get('message')!r}",
        )
        # LITERAL resolved path, not the substring "hooks". The old form was
        # satisfied by the SECOND ImportError too ("...could not import
        # _project_paths from it"), i.e. by a bridge that had already found a
        # hooks directory somewhere else entirely.
        expected_hooks = (no_hooks.parent / "hooks").resolve()
        check(
            "case6: ImportError names the LITERAL sibling path it looked for",
            str(expected_hooks) in str(out.get("message", "")),
            f"expected {str(expected_hooks)!r} in message={out.get('message')!r}",
        )

    # -- positive control: hooks/ sibling present -------------------------
    with_hooks = sandbox / "bridge_with_hooks"
    (with_hooks / "scripts").mkdir(parents=True, exist_ok=True)
    (with_hooks / "hooks").mkdir(parents=True, exist_ok=True)
    shutil.copy2(_BRIDGE_SRC, with_hooks / "scripts" / "_claude_paths.py")
    shutil.copy2(_HOOKS_DIR / "_project_paths.py", with_hooks / "hooks" / "_project_paths.py")
    out, proc = _run_bridge_driver(driver, with_hooks / "scripts", cwd)
    if out is None:
        detail = f"no RESULT line. stdout={proc.stdout!r} stderr={proc.stderr!r}"
        check("case6: bridge imports fine WITH a hooks sibling (positive control)", False, detail)
        check("case6: bridge APPENDS hooks dir (scripts keep sys.path priority)", False, detail)
        check("case6: bridge re-exports the locator surface", False, detail)
    else:
        check(
            "case6: bridge imports fine WITH a hooks sibling (positive control)",
            out.get("outcome") == "imported",
            f"outcome={out.get('outcome')!r} message={out.get('message')!r}",
        )
        check(
            "case6: bridge APPENDS hooks dir (scripts keep sys.path priority)",
            out.get("hooks_at_zero") is False,
            f"sys.path[0] ends with /hooks -> {out.get('hooks_at_zero')!r}",
        )
        missing = [n for n in _BRIDGE_EXPECTED_EXPORTS if n not in out.get("exports", [])]
        check(
            "case6: bridge re-exports the locator surface",
            not missing,
            f"missing exports {missing}; got {out.get('exports')}",
        )


def _fabricated_home_env(fab_home: Path) -> dict:
    """Environment that makes ``Path.home()`` resolve to ``fab_home``.

    ntpath.expanduser consults USERPROFILE first, then HOMEDRIVE+HOMEPATH;
    posixpath.expanduser consults HOME. All four are set so the fixture is
    not silently a no-op on either platform.
    """
    drive, tail = os.path.splitdrive(str(fab_home))
    return {
        "USERPROFILE": str(fab_home),
        "HOME": str(fab_home),
        "HOMEDRIVE": drive,
        "HOMEPATH": tail or str(fab_home),
    }


def case6c_bridge_never_falls_back_to_home(env) -> None:
    """The probe case 6 could not catch: PROVENANCE under a POPULATED $HOME.

    Case 6 asserts ``outcome == "ImportError"`` and ``"hooks" in message``.
    Both are satisfied by a bridge that DOES fall back to ``~/.claude/hooks``
    -- because that directory does not exist on this workstation (the
    2026-08-25 migration emptied it), so the fallback fails too, and the
    resulting *second* ImportError also contains the word "hooks". The test
    passes for a reason that has nothing to do with the invariant.

    So: fabricate a $HOME that IS populated with a working
    ``.claude/hooks/_project_paths.py`` and re-run both halves.

      * hooks sibling ABSENT  -> a home-fallback bridge would now IMPORT
        SUCCESSFULLY. The correct bridge still raises ImportError.
      * hooks sibling PRESENT -> assert WHICH file was loaded. The home copy
        carries MARKER = "DECOY"; the sibling does not. Provenance, not
        outcome, is what distinguishes "resolved correctly" from "resolved by
        luck".
    """
    print("\ncase 6c -- bridge provenance under a fabricated POPULATED $HOME")
    sandbox, cwd = env["sandbox"], env["cwd"]

    if not _BRIDGE_SRC.is_file():
        detail = f"MISSING FILE {_BRIDGE_SRC}"
        for label in (
            "case6c: fabricated $HOME really holds a working _project_paths",
            "case6c: $HOME is really redirected inside the child interpreter",
            "case6c: bridge still raises with NO sibling and a POPULATED $HOME",
            "case6c: ImportError names the LITERAL sibling path, not the $HOME one",
            "case6c: _project_paths is loaded from the sibling hooks/, not from $HOME",
            "case6c: the $HOME decoy module was NOT loaded",
        ):
            check(label, False, detail)
        return

    driver = _write_text(sandbox / "bridge_driver.py", _BRIDGE_DRIVER)

    # -- the fabricated, POPULATED home --------------------------------------
    fab_home = sandbox / "fabricated-home"
    fab_hooks = fab_home / ".claude" / "hooks"
    fab_hooks.mkdir(parents=True, exist_ok=True)
    decoy = fab_hooks / "_project_paths.py"
    decoy.write_text(
        _HOOKS_DIR.joinpath("_project_paths.py").read_text(encoding="utf-8")
        + '\n\nMARKER = "DECOY"\n',
        encoding="utf-8",
    )
    fab_env = _fabricated_home_env(fab_home)
    check(
        "case6c: fabricated $HOME really holds a working _project_paths",
        decoy.is_file() and "MARKER" in decoy.read_text(encoding="utf-8"),
        f"decoy={decoy}",
    )

    # -- half 1: NO sibling hooks/, but a populated $HOME --------------------
    no_hooks = sandbox / "bridge6c_no_hooks" / "scripts"
    no_hooks.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_BRIDGE_SRC, no_hooks / "_claude_paths.py")
    out, proc = _run_bridge_driver(driver, no_hooks, cwd, extra_env=fab_env)
    if out is None:
        detail = f"no RESULT line. stdout={proc.stdout!r} stderr={proc.stderr!r}"
        check("case6c: $HOME is really redirected inside the child interpreter", False, detail)
        check("case6c: bridge still raises with NO sibling and a POPULATED $HOME", False, detail)
        check("case6c: ImportError names the LITERAL sibling path, not the $HOME one", False, detail)
    else:
        # Harness control: if the child's Path.home() is NOT the fabricated
        # one, the whole case is vacuous and must say so in its own voice.
        # (The ImportError branch reports `home` too -- see the driver.)
        check(
            "case6c: $HOME is really redirected inside the child interpreter",
            _child_home(out, proc) == str(fab_home),
            f"child Path.home()={_child_home(out, proc)!r}, expected {str(fab_home)!r}",
        )
        check(
            "case6c: bridge still raises with NO sibling and a POPULATED $HOME",
            out.get("outcome") == "ImportError",
            f"outcome={out.get('outcome')!r} -- a home fallback would report "
            f"'imported' here. message={out.get('message')!r}",
        )
        expected_hooks = (no_hooks.parent / "hooks").resolve()
        msg = str(out.get("message", ""))
        check(
            "case6c: ImportError names the LITERAL sibling path, not the $HOME one",
            str(expected_hooks) in msg and str(fab_hooks) not in msg,
            f"expected {str(expected_hooks)!r} and NOT {str(fab_hooks)!r}; message={msg!r}",
        )

    # -- half 2: sibling hooks/ PRESENT, $HOME still populated ---------------
    with_hooks = sandbox / "bridge6c_with_hooks"
    (with_hooks / "scripts").mkdir(parents=True, exist_ok=True)
    (with_hooks / "hooks").mkdir(parents=True, exist_ok=True)
    shutil.copy2(_BRIDGE_SRC, with_hooks / "scripts" / "_claude_paths.py")
    shutil.copy2(_HOOKS_DIR / "_project_paths.py",
                 with_hooks / "hooks" / "_project_paths.py")
    out, proc = _run_bridge_driver(driver, with_hooks / "scripts", cwd, extra_env=fab_env)
    if out is None:
        detail = f"no RESULT line. stdout={proc.stdout!r} stderr={proc.stderr!r}"
        check("case6c: _project_paths is loaded from the sibling hooks/, not from $HOME", False, detail)
        check("case6c: the $HOME decoy module was NOT loaded", False, detail)
    else:
        pp_file = out.get("pp_file")
        expected_dir = (with_hooks / "hooks").resolve()
        check(
            "case6c: _project_paths is loaded from the sibling hooks/, not from $HOME",
            out.get("outcome") == "imported"
            and pp_file is not None
            and _is_under(Path(pp_file), expected_dir),
            f"outcome={out.get('outcome')!r} pp_file={pp_file!r} "
            f"expected under {expected_dir}",
        )
        check(
            "case6c: the $HOME decoy module was NOT loaded",
            out.get("pp_marker") is None,
            f"pp_marker={out.get('pp_marker')!r} -- the bridge imported "
            f"{pp_file!r} out of the fabricated home",
        )


def _child_home(out: dict, proc) -> str | None:
    """Path.home() as the child saw it. Reported on BOTH driver branches."""
    return out.get("home")


def _tree_snapshot(root: Path) -> set[str]:
    """Every path under ``root``, relative and normalized. For no-write proofs."""
    if not root.exists():
        return set()
    out = {"."}
    for p in root.rglob("*"):
        out.add(str(p.relative_to(root)).replace("\\", "/"))
    return out


# ---------------------------------------------------------------------------
# Case 7 -- the ledger WRITE path (INV-7 authority, INV-9 skip safety).
# ---------------------------------------------------------------------------
def case7_ledger_writes_land_project_local(env) -> None:
    """Everything before this case exercises ``dump_table()`` and ``query()``
    -- both READS. Nothing calls ``record_clean`` / ``record_failure``, so
    ``_save_state`` could be pointed at a home path and the suite would stay
    fully green while the ledger the repo tracks never moved. That is INV-7's
    "exactly one authoritative copy" going unasserted, and it is precisely
    the split brain the work item describes: signal accumulating on the
    workstation while 15 areas of real history sat stranded in the repo.

    Five calls, because five is the ``WARMUP_THRESHOLD`` boundary: INV-9 says
    ``skip_eligible`` is true only at ``clean_streak >= 5``, so both sides of
    the boundary are asserted -- an off-by-one that made an area skip-eligible
    one run early would otherwise ship.
    """
    print("\ncase 7 -- ledger writes land project-local (INV-7 / INV-9)")
    proj, home, cwd = env["ledger_proj"], env["ledger_home"], env["cwd"]
    expected_ledger = proj / ".claude" / "contract-accuracy.json"
    home_before = _tree_snapshot(home)

    check(
        "case7: fixture -- no ledger exists at the target before the run",
        not expected_ledger.exists(),
        f"{expected_ledger} already present",
    )

    with claude_roots_seam(project_root=proj, home_root=home, cwd=cwd):
        assert_seam_isolated("case7")

        # INV-5: nothing holds the ledger yet, so the preferred rank-0
        # candidate is where the writer must create it.
        check_call(
            "case7: state_path() -> the project-local ledger before any write",
            accuracy_update, "state_path", expected_ledger,
        )

        results = []
        err = None
        for i in range(1, 6):
            r, err = call_or_none(
                accuracy_update, "record_clean", ("ledger-area", f"contract-{i}.md")
            )
            if err:
                break
            results.append(r)

        if err:
            for label in (
                "case7: clean_streak is 4 and skip_eligible is FALSE at run 4 (INV-9)",
                "case7: clean_streak is 5 and skip_eligible is TRUE at run 5 (INV-9)",
                "case7: the ledger file lands at the project-local path",
                "case7: the written ledger holds the LITERAL post-warmup entry",
                "case7: query() reads back the value just written",
            ):
                check(label, False, err)
        else:
            check(
                "case7: clean_streak is 4 and skip_eligible is FALSE at run 4 (INV-9)",
                results[3]["clean_streak"] == 4 and results[3]["skip_eligible"] is False,
                f"run 4 -> {results[3]!r}",
            )
            check(
                "case7: clean_streak is 5 and skip_eligible is TRUE at run 5 (INV-9)",
                results[4]["clean_streak"] == 5 and results[4]["skip_eligible"] is True,
                f"run 5 -> {results[4]!r}",
            )
            check(
                "case7: the ledger file lands at the project-local path",
                expected_ledger.is_file(),
                f"nothing at {expected_ledger}",
            )
            if expected_ledger.is_file():
                data = json.loads(expected_ledger.read_text(encoding="utf-8"))
                entry = data.get("areas", {}).get("ledger-area", {})
                check(
                    "case7: the written ledger holds the LITERAL post-warmup entry",
                    entry.get("clean_streak") == 5
                    and entry.get("total_runs") == 5
                    and entry.get("skip_eligible") is True
                    and entry.get("last_verdict") == "clean"
                    and entry.get("last_contract") == "contract-5.md"
                    and len(entry.get("history", [])) == 5,
                    f"areas['ledger-area']={entry!r}",
                )
            else:
                check("case7: the written ledger holds the LITERAL post-warmup entry",
                      False, "ledger file absent")

            q, qerr = call_or_none(accuracy_update, "query", ("ledger-area",))
            check(
                "case7: query() reads back the value just written",
                qerr is None and isinstance(q, dict) and q.get("clean_streak") == 5,
                qerr or f"expected clean_streak 5, got {q!r}",
            )

    # -- the negative half: NOTHING was created under the fake home ----------
    home_after = _tree_snapshot(home)
    check(
        "case7: the fake home tree is byte-for-byte unchanged (no stray ledger)",
        home_after == home_before,
        f"new under fake home: {sorted(home_after - home_before)}",
    )
    check(
        "case7: no ledger was created at the fake-home path",
        not (home / ".claude" / "contract-accuracy.json").exists(),
        f"unexpected {home / '.claude' / 'contract-accuracy.json'}",
    )


# ---------------------------------------------------------------------------
# Case 8 -- cross_area_scan's cache: write, read back, and MISS across roots.
# ---------------------------------------------------------------------------
def case8_scan_cache_is_per_checkout(env) -> None:
    """``cross_area_scan`` was never imported by this suite until now, so a
    module-scope ``raise RuntimeError`` in it stayed green. Beyond mere
    importability, its cache is the one place where getting the root wrong is
    actively *harmful* rather than merely blind: entries are keyed on contract
    text alone while the scan's RESULT depends on this checkout's
    ``area-mapping.json`` and ``JOURNAL.md``. A machine-wide cache therefore
    serves one checkout's answer to another. The cross-root MISS below is what
    pins that down -- a hit would be a correctness bug wearing a performance
    win's clothing.
    """
    print("\ncase 8 -- cross-area scan cache is per-checkout")
    root_a, root_b, home, cwd = (
        env["cache_a"], env["cache_b"], env["cache_home"], env["cwd"],
    )
    home_before = _tree_snapshot(home)
    text = "# fixture contract text for the scan cache\n"
    payload = {"areas": [{"area": "alpha-area", "score": 5}], "fixture": True}

    sha, err = call_or_none(cross_area_scan, "content_hash", (text,))
    check(
        "case8: content_hash() is the sha1 of the contract text",
        err is None and sha == __import__("hashlib").sha1(text.encode("utf-8")).hexdigest(),
        err or f"got {sha!r}",
    )

    expected_file = root_a / ".claude" / "cache" / "cross-area-scans" / f"{sha}.json"

    with claude_roots_seam(project_root=root_a, home_root=home, cwd=cwd):
        assert_seam_isolated("case8a")
        check_call(
            "case8: cache_dir() -> <root A>/.claude/cache/cross-area-scans",
            cross_area_scan, "cache_dir",
            root_a / ".claude" / "cache" / "cross-area-scans",
        )
        _, err = call_or_none(cross_area_scan, "save_cache", (text, payload))
        check("case8: save_cache() completes without raising", err is None, err or "")
        check(
            "case8: the cache entry lands at the LITERAL per-checkout path",
            expected_file.is_file(),
            f"nothing at {expected_file}; "
            f"cache tree={sorted(_tree_snapshot(root_a / '.claude' / 'cache'))}",
        )
        got, err = call_or_none(cross_area_scan, "load_cache", (text,))
        check(
            "case8: load_cache() round-trips the LITERAL payload (positive control)",
            err is None and got == payload,
            err or f"expected {payload!r}, got {got!r}",
        )

    # -- cross-root MISS: a DIFFERENT checkout must not be served root A's
    # answer. Without the positive control above this would pass vacuously
    # (a save_cache that wrote nothing also misses everywhere).
    with claude_roots_seam(project_root=root_b, home_root=home, cwd=cwd):
        assert_seam_isolated("case8b")
        check_call(
            "case8: cache_dir() follows the roots to checkout B",
            cross_area_scan, "cache_dir",
            root_b / ".claude" / "cache" / "cross-area-scans",
        )
        got, err = call_or_none(cross_area_scan, "load_cache", (text,))
        check(
            "case8: checkout B MISSES checkout A's entry for the same contract text",
            err is None and got is None,
            err or f"checkout B was served {got!r} -- the cache is machine-wide",
        )

    home_after = _tree_snapshot(home)
    check(
        "case8: nothing was written under the fake home",
        home_after == home_before,
        f"new under fake home: {sorted(home_after - home_before)}",
    )


# ---------------------------------------------------------------------------
# Case 9 -- validate_registries: candidate roots + a real dead-reference count.
# ---------------------------------------------------------------------------
def case9_validate_registries(env) -> None:
    """The other never-imported module. ``find_candidate_roots`` is the part
    the contract changed (the flat layout made the old "every child of
    concepts/ is a project name" inference degenerate, yielding no usable root
    at all), and ``validate`` is the part whose false green -- "[OK] 0/0
    references resolve, 0 dead" -- is what let this script report everything
    fine for a year while resolving nothing.
    """
    print("\ncase 9 -- validate_registries roots and dead-reference counting")
    vr, home, cwd = env["validate_root"], env["empty_home"], env["cwd"]

    with claude_roots_seam(project_root=vr, home_root=home, cwd=cwd):
        assert_seam_isolated("case9")

        roots, err = call_or_none(validate_registries, "find_candidate_roots", ([],))
        expected_roots = [Path(cwd).resolve(), vr.resolve()]
        check(
            "case9: find_candidate_roots([]) -> the LITERAL [cwd, resolved-project-root]",
            err is None and roots == expected_roots,
            err or f"expected {[str(p) for p in expected_roots]}, "
                   f"got {[str(p) for p in (roots or [])]}",
        )
        check(
            "case9: the resolved project root is a candidate at all",
            err is None and vr.resolve() in (roots or []),
            err or f"project root missing from {[str(p) for p in (roots or [])]}",
        )

        mech, err = call_or_none(validate_registries, "mechanisms_file")
        check(
            "case9: mechanisms_file() -> the fixture registry",
            err is None and mech == vr / ".claude" / "registries" / "MECHANISMS.md",
            err or f"got {mech!r}",
        )

        if err is None and roots is not None:
            report, verr = call_or_none(
                validate_registries, "validate", (mech, roots)
            )
            check(
                "case9: validate() counts EXACTLY 2 references (fenced block ignored)",
                verr is None and (report or {}).get("total") == 2,
                verr or f"report={report!r}",
            )
            check(
                "case9: validate() finds EXACTLY 1 alive reference (positive control)",
                verr is None and (report or {}).get("alive") == 1,
                verr or f"report={report!r}",
            )
            check(
                "case9: validate() finds EXACTLY 1 dead reference",
                verr is None and (report or {}).get("dead") == 1,
                verr or f"report={report!r}",
            )
            dead_refs = [d["reference"] for d in (report or {}).get("dead_entries", [])]
            check(
                "case9: the dead entry is the LITERAL src/dead/gone.cs",
                verr is None and dead_refs == ["src/dead/gone.cs"],
                verr or f"dead_entries={dead_refs!r}",
            )


# ---------------------------------------------------------------------------
# Case 10 -- --project accepts BOTH names, case-insensitively.
# ---------------------------------------------------------------------------
def case10_project_alias_matching(env) -> None:
    """Flattening the layout (INV-8) removed the ``concepts/<project>/``
    directory level that used to carry project identity. The obvious
    substitute -- the directory above ``.claude`` -- is the BRANCH SLUG inside
    a worktree, so the ``--project <the repository name>`` invocation both
    SKILL.md files document matched nothing and exited 0. ``project_aliases``
    widens matching to the main working tree's name as well, case-folded.

    Asserted through the two real consumers, on literal counts, with an
    explicit non-match so "accept everything" is not a passing answer.
    """
    print("\ncase 10 -- --project accepts checkout name OR main-repo name, any casing")
    wt, home, cwd = env["worktree"], env["empty_home"], env["cwd"]
    wc = wt / ".claude"

    with claude_roots_seam(project_root=wt, home_root=home, cwd=cwd):
        assert_seam_isolated("case10")

        aliases, err = call_or_none(pp, "project_aliases", (wc / "concepts",))
        check(
            "case10: project_aliases() -> the LITERAL {checkout-slug, main-repo} set",
            err is None
            and aliases == {"20260826-bug-35-fixture-worktree", "mainrepofixture"},
            err or f"got {aliases!r}",
        )

        for label, requested, expect in (
            ("exact checkout slug", "20260826-bug-35-fixture-worktree", True),
            ("upper-cased checkout slug", "20260826-BUG-35-FIXTURE-WORKTREE", True),
            ("main-repo name", "MainRepoFixture", True),
            ("lower-cased main-repo name", "mainrepofixture", True),
            ("bogus project name", "NoSuchProjectAnywhere", False),
        ):
            got, err = call_or_none(pp, "project_matches", (wc / "concepts", requested))
            check(
                f"case10: project_matches({label}) is {expect}",
                err is None and got is expect,
                err or f"got {got!r}",
            )

        # -- through list_contracts.collect() --------------------------------
        for label, requested, expected_n in (
            ("no filter", None, 2),
            ("checkout slug", "20260826-bug-35-fixture-worktree", 2),
            ("upper-cased checkout slug", "20260826-BUG-35-FIXTURE-WORKTREE", 2),
            ("main-repo name", "MainRepoFixture", 2),
            ("lower-cased main-repo name", "mainrepofixture", 2),
            ("bogus name", "NoSuchProjectAnywhere", 0),
        ):
            rows, err = call_or_none(list_contracts, "collect", (requested, None))
            check(
                f"case10: collect(--project {label}) -> EXACTLY {expected_n}",
                err is None and len(rows or []) == expected_n,
                err or f"expected {expected_n}, got {len(rows or [])} -> "
                       f"{sorted(r['path'].name for r in (rows or []))}",
            )

        # -- through north_star_review.discover() ----------------------------
        for label, requested, expected_slugs in (
            ("no filter", None, ["wt-ns"]),
            ("checkout slug", "20260826-bug-35-fixture-worktree", ["wt-ns"]),
            ("upper-cased checkout slug", "20260826-BUG-35-FIXTURE-WORKTREE", ["wt-ns"]),
            ("main-repo name", "MainRepoFixture", ["wt-ns"]),
            ("lower-cased main-repo name", "mainrepofixture", ["wt-ns"]),
            ("bogus name", "NoSuchProjectAnywhere", []),
        ):
            stars, err = call_or_none(north_star_review, "discover", (requested,))
            slugs = sorted(ns.slug for ns in (stars or []))
            check(
                f"case10: discover(--project {label}) -> {expected_slugs}",
                err is None and slugs == expected_slugs,
                err or f"expected {expected_slugs}, got {slugs}",
            )


# ---------------------------------------------------------------------------
# INV-10 -- prove no real tree was touched.
# ---------------------------------------------------------------------------
def _sentinel_paths() -> list[Path]:
    # The home path here is a NEGATIVE guard, not resolution (INV-1 exempt).
    # _real_home(), not Path.home(): Path.home() is fabricated for this
    # process, and the point of the sentinel is to watch the REAL file.
    home = _real_home()
    return [
        _CLAUDE_DIR / "contract-accuracy.json",
        _CLAUDE_DIR / "logs" / "errors.jsonl",
        _CLAUDE_DIR / "area-mapping.json",
        home / ".claude" / "contract-accuracy.json",
        home / ".claude" / "logs" / "errors.jsonl",
    ]


def snapshot_real_trees() -> dict:
    snap = {}
    for p in _sentinel_paths():
        try:
            st = p.stat()
            snap[str(p)] = (True, st.st_size, st.st_mtime_ns)
        except OSError:
            snap[str(p)] = (False, -1, -1)
    return snap


def case11_same_answer_from_any_directory() -> None:
    """Run each script for real, twice, from two real working directories.

    This is the only assertion in the suite that does NOT use the fabricated
    seam -- and it is the one that would have caught the two defects that
    shipped in the first pass. Both had the same shape: the resolver was
    correct, but a call site anchored something on ``os.getcwd()`` instead,
    so the script produced a different answer from a subdirectory and exited
    0 either way.

    Measured before the fix:
        validate_registries   118/144 references resolve  (repo root)
                                0/144 references resolve  (repo/src)
        cross_area_scan       3 adjacent areas            (repo root)
                              none above threshold        (repo/src)

    The seam cannot observe this class, because the seam replaces the very
    thing under test. Only a real subprocess from a real second directory can.
    """
    print("\ncase 11 -- identical output from two real working directories")

    repo = _SCRIPTS_DIR.parent.parent
    second = None
    for candidate in ("src", "tools", "docs", "lib", "app"):
        if (repo / candidate).is_dir():
            second = repo / candidate
            break
    if second is None:
        # Any real subdirectory that is not part of the tooling itself. Named
        # candidates come first only so the chosen directory is stable run to
        # run; the case needs a second real CWD, not a particular one.
        for child in sorted(repo.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                second = child
                break
    if second is None:
        check("case11: a second real directory exists to run from", False,
              "no non-dot subdirectory under the checkout to run from")
        return
    check("case11: a second real directory exists to run from", True, "")

    contract = None
    for md in sorted((repo / ".claude" / "concepts").glob("*.md")):
        contract = md
        break

    invocations = [
        ("derive_area.py", [str(contract)] if contract else []),
        ("list_contracts.py", []),
        ("validate_registries.py", []),
        ("accuracy_update.py", ["dump-table"]),
        ("archive_stale_stubs.py", []),
        ("cross_area_scan.py", [str(contract), "--no-cache"] if contract else []),
    ]

    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)  # the plain-shell case, where this bit

    for name, args in invocations:
        script = _SCRIPTS_DIR / name
        if not script.is_file():
            check(f"case11: {name} exists", False, f"missing {script}")
            continue
        outs = []
        for cwd in (repo, second):
            try:
                proc = subprocess.run(
                    [sys.executable, str(script), *args],
                    capture_output=True, text=True, cwd=str(cwd), env=env, timeout=180,
                )
                # Compared BYTE-FOR-BYTE, deliberately. An earlier draft of
                # this case normalized the working directory out of the text,
                # because `validate_registries` echoed cwd in its candidate-root
                # header. That would have let any future script quietly leak
                # the working directory into its output. The script was made
                # reproducible instead -- it now prunes candidate roots that sit
                # inside another candidate -- so this assertion can stay strict.
                outs.append(proc.stdout)
            except (OSError, subprocess.TimeoutExpired) as exc:
                outs.append(f"<<RUN FAILED: {exc}>>")
        same = outs[0] == outs[1]
        detail = ""
        if not same:
            a, b = outs[0].splitlines(), outs[1].splitlines()
            first_diff = next(
                (f"root={x!r} vs {second.name}={y!r}"
                 for x, y in zip(a, b) if x != y),
                f"line counts {len(a)} vs {len(b)}",
            )
            detail = f"output differs by working directory -- {first_diff}"
        check(f"case11: {name} -- same stdout from repo root and {second.name}/",
              same, detail)


def case_inv10_no_real_writes(before: dict) -> None:
    print("\nINV-10 -- no real data tree was READ, modified or written")

    # (0) layer 0's own harness control. If the re-exec silently did not
    # happen -- a swallowed subprocess error, someone exporting the guard
    # variable by hand -- every assertion below reverts to detect-only and
    # a direct Path.home() write reaches the workstation again. Asserted on
    # the LITERAL fabricated path, and on it being distinct from the real one.
    fab = os.environ.get(_HOME_SANDBOX_ENV)
    check(
        "INV-10: the suite is running under a FABRICATED $HOME (layer 0)",
        bool(fab) and Path.home() == Path(fab) and Path.home() != _real_home(),
        f"$HOME sandbox={fab!r} Path.home()={Path.home()} real={_real_home()}",
    )

    # (a) the READ tripwire. A stat()-based snapshot cannot observe a read:
    # a subject that resolved the live <repo>/.claude/concepts and inventoried
    # 160 real contracts leaves every sentinel byte-identical. This is the
    # assertion the header's claim actually rests on.
    check(
        "INV-10: no open() ever touched a real Claude DATA path (read or write)",
        not _AUDIT_VIOLATIONS,
        f"{len(_AUDIT_VIOLATIONS)} violation(s): {_AUDIT_VIOLATIONS[:8]}",
    )

    # (b) the tripwire's own positive control. An audit hook that never fires
    # -- wrong event name, a prefix list built from the wrong root, a typo in
    # the separator handling -- reports a clean bill of health forever. Read
    # one real guarded path deliberately and require that it IS caught.
    probe_target = _CLAUDE_DIR / "registries" / "MECHANISMS.md"
    baseline = len(_AUDIT_VIOLATIONS)
    probe_ran = False
    try:
        with open(probe_target, "rb"):
            probe_ran = True
    except OSError:
        pass
    check(
        "INV-10: the tripwire CATCHES a deliberate read of a real registry",
        probe_ran and len(_AUDIT_VIOLATIONS) == baseline + 1,
        f"probe_ran={probe_ran} target={probe_target} "
        f"violations {baseline} -> {len(_AUDIT_VIOLATIONS)}",
    )
    del _AUDIT_VIOLATIONS[baseline:]          # the probe is not a violation

    # (c) the write snapshot, kept: it also covers deletion and truncation by
    # anything that bypasses open() (os.replace, rename, unlink).
    after = snapshot_real_trees()
    for key, was in before.items():
        check(
            f"INV-10: unchanged {key}",
            after.get(key) == was,
            f"before={was} after={after.get(key)}",
        )

    # (d) the module-scope LOG_DIR capture. Previously, an absent _error_log
    # scored a hardcoded `check(..., True, "")` -- a free PASS that inflated
    # the count and asserted nothing. _error_log IS reachable (accuracy_update
    # imports it through the bridge), so its absence is a real finding: it
    # would mean the audit trail went dark again, which is half of what #35
    # repaired.
    errlog = sys.modules.get("_error_log")
    check(
        "INV-10: accuracy_update really imported the hooks logger (not the stub)",
        errlog is not None,
        "_error_log absent from sys.modules -- the fail-soft stub is live and "
        "the accuracy audit trail is dark",
    )
    log_dir = Path(getattr(errlog, "LOG_DIR", Path("/nonexistent-log-dir")))
    check(
        "INV-10: _error_log.LOG_DIR was captured inside the boot sandbox",
        errlog is not None and _is_under(log_dir, _SANDBOX),
        f"LOG_DIR={log_dir} (module-scope capture escaped the sandbox)",
    )


# ---------------------------------------------------------------------------
# Fixture assembly + entry point.
# ---------------------------------------------------------------------------
def build_env() -> dict:
    sandbox = _SANDBOX
    cwd = sandbox / "neutral-cwd"          # rank 1: a dir with NO .claude
    cwd.mkdir(parents=True, exist_ok=True)

    proj = build_populated_root(
        sandbox / "FakeProject",
        mapping=MAPPING_PROJECT,
        ledger=LEDGER_PROJECT,
        north_star_slugs=("alpha-ns", "beta-ns", "gamma-ns"),
        contract_titles=("one", "two"),
        stub_slugs=("one", "two", "three"),
    )
    home = build_populated_root(
        sandbox / "fake-home",
        mapping=MAPPING_HOME,
        ledger=LEDGER_HOME,
        north_star_slugs=("home-ns",),
        contract_titles=("home-one",),
        stub_slugs=("home-one",),
    )

    root_a = build_populated_root(
        sandbox / "RootA",
        mapping={"schema_version": 1, "areas": {"root-a-area": {"patterns": ["src/alpha/"]}}},
        ledger={"schema_version": 1, "areas": {}},
        north_star_slugs=(),
        contract_titles=("a-one",),
        stub_slugs=(),
    )
    root_b = build_populated_root(
        sandbox / "RootB",
        mapping={"schema_version": 1, "areas": {"root-b-area": {"patterns": ["src/beta/"]}}},
        ledger={"schema_version": 1, "areas": {}},
        north_star_slugs=(),
        contract_titles=("b-one", "b-two"),
        stub_slugs=(),
    )

    empty_proj = build_empty_root(sandbox / "EmptyProject")
    (empty_proj / ".claude" / "concepts").mkdir(parents=True, exist_ok=True)
    empty_home = build_empty_root(sandbox / "empty-home")

    # case 2c: a root whose concepts/ and north-stars/ EXIST but are EMPTY.
    empty_dirs_self = sandbox / "EmptyDirsSelfRoot"
    for leaf in ("concepts", "north-stars"):
        (empty_dirs_self / ".claude" / leaf).mkdir(parents=True, exist_ok=True)

    # case 7: ledger write target. `.claude/` exists so the root is real, but
    # it holds no ledger -- INV-5's preferred-path-on-absence must place the
    # new file here, in the repo-shaped rank-0 candidate.
    ledger_proj = build_empty_root(sandbox / "LedgerProject")
    ledger_home = build_empty_root(sandbox / "ledger-fake-home")

    # case 8: two distinct cache roots, to prove a cross-root miss.
    cache_a = build_empty_root(sandbox / "CacheRootA")
    cache_b = build_empty_root(sandbox / "CacheRootB")
    cache_home = build_empty_root(sandbox / "cache-fake-home")

    # case 9: a registry-validation root. Its concepts/ holds ONLY flat *.md
    # (no followups/ subdirectory), so find_candidate_roots' per-child
    # "parent hint" probe has nothing to iterate and the candidate list is
    # deterministic.
    vr = sandbox / "ValidateRoot"
    _write_text(vr / ".claude" / "concepts" / "2026-02-01-vr.md",
                CONTRACT_TEMPLATE.format(title="vr", status="approved"))
    _write_text(vr / ".claude" / "registries" / "MECHANISMS.md", MECHANISMS_FIXTURE)
    _write_text(vr / ".claude" / "registries" / "VOCABULARY.md", "# Fixture VOCABULARY\n")
    _write_text(vr / "src" / "live" / "thing.cs", "// alive\n")

    # case 10: a WORKTREE-shaped checkout. The directory name is a branch
    # slug; the main working tree's name is reachable only through the `.git`
    # FILE. Both must satisfy --project, case-insensitively.
    main_repo = sandbox / "MainRepoFixture"
    (main_repo / ".git" / "worktrees" / "wt1").mkdir(parents=True, exist_ok=True)
    worktree = build_populated_root(
        sandbox / "20260826-bug-35-fixture-worktree",
        mapping=MAPPING_PROJECT,
        ledger=LEDGER_PROJECT,
        north_star_slugs=("wt-ns",),
        contract_titles=("wt-one", "wt-two"),
        stub_slugs=(),
    )
    _write_text(
        worktree / ".git",
        f"gitdir: {main_repo / '.git' / 'worktrees' / 'wt1'}\n",
    )

    fixture = _write_text(sandbox / "fixtures" / "fixture-contract.md", FIXTURE_CONTRACT)

    return {
        "sandbox": sandbox,
        "cwd": cwd,
        "proj": proj,
        "home": home,
        "root_a": root_a,
        "root_b": root_b,
        "empty_proj": empty_proj,
        "empty_home": empty_home,
        "empty_dirs_self": empty_dirs_self,
        "ledger_proj": ledger_proj,
        "ledger_home": ledger_home,
        "cache_a": cache_a,
        "cache_b": cache_b,
        "cache_home": cache_home,
        "validate_root": vr,
        "worktree": worktree,
        "main_repo": main_repo,
        "fixture": fixture,
    }


def report_import_health() -> bool:
    """A missing subject must read as ONE labelled failure, never a crash."""
    print("import health")
    ok = True
    for label, mod, err, fatal in (
        ("_project_paths (hooks helper)", pp, _ERR_PP, True),
        ("derive_area", derive_area, _ERR_DERIVE, True),
        ("accuracy_update", accuracy_update, _ERR_ACCURACY, True),
        ("north_star_review", north_star_review, _ERR_NORTHSTAR, True),
        ("archive_stale_stubs", archive_stale_stubs, _ERR_STUBS, True),
        ("list_contracts", list_contracts, _ERR_LIST, True),
        ("cross_area_scan", cross_area_scan, _ERR_SCAN, True),
        ("validate_registries", validate_registries, _ERR_VALIDATE, True),
    ):
        check(f"import: {label}", mod is not None, err or "")
        if mod is None and fatal:
            ok = False

    # The bridge does not exist yet -- that is the defect, reported as such.
    check(
        "import: _claude_paths bridge (contract's new mechanism)",
        _claude_paths is not None,
        _ERR_BRIDGE or "",
    )
    return ok


def main() -> int:
    print("test_script_path_resolution -- RED suite for work item #35")
    print(f"  repo root : {_REPO_ROOT}")
    print(f"  scripts   : {_SCRIPTS_DIR}")
    print(f"  sandbox   : {_SANDBOX}")
    print()

    before = snapshot_real_trees()

    # ONE try/finally around everything after the sandbox exists. The
    # import-health early return used to bail out ahead of the cleanup, so
    # every run that went RED on an unimportable subject stranded a temp
    # sandbox -- and, since boot now chdir()s into it, left the process
    # sitting in a directory it had just orphaned.
    try:
        healthy = report_import_health()
        if not healthy:
            print("-" * 60)
            print(" HARNESS FAILURE: a subject module under test did not import.")
            print(" This is NOT the RED signal -- fix the import before reading results.")
            print("-" * 60)
            print(f" {_PASS} passed, {_FAIL} failed")
            return 1

        env = build_env()
        case1_project_local_wins(env)
        case2b_self_root_beats_cwd(env)
        case2c_empty_high_rank_loses_to_populated_low_rank(env)
        case2_global_fallback(env)
        case3_missing_in_both(env)
        case4_flat_layout_discovery(env)
        case5_no_import_time_capture(env)
        case6_bridge_raises_without_hooks(env)
        case6c_bridge_never_falls_back_to_home(env)
        case7_ledger_writes_land_project_local(env)
        case8_scan_cache_is_per_checkout(env)
        case9_validate_registries(env)
        case10_project_alias_matching(env)
        case11_same_answer_from_any_directory()
        case_inv10_no_real_writes(before)

        print()
        print("-" * 60)
        print(f" {_PASS} passed, {_FAIL} failed")
        print("-" * 60)
        return 1 if _FAIL else 0
    finally:
        if _SAVED_CPD_AT_BOOT is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = _SAVED_CPD_AT_BOOT
        # cwd must leave the sandbox BEFORE rmtree, or Windows refuses to
        # remove the tree the process is sitting in and the litter survives
        # the run.
        try:
            os.chdir(_ORIGINAL_CWD)
        except OSError:
            pass
        shutil.rmtree(_SANDBOX, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
