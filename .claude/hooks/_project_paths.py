"""Resolve project-scoped Claude paths, with a global fallback.

The 2026-08-22 migration moved this project's Claude setup into the repo at
``<project>/.claude/``. Other projects on this workstation still keep theirs
under ``~/.claude/``. Every helper here returns the project-local location
first and the global one second, so a hook keeps working in either layout and
neither breaks while both exist.

Hooks are launched as standalone scripts (``py -3 "<path>/<hook>.py"``), so
Python puts this file's directory on ``sys.path[0]`` and a plain
``import _project_paths`` resolves. That is the same mechanism
``_memory_common.py`` already relies on.

Runtime state deliberately stays in ``~/.claude`` -- logs, audit trails and
per-session state are machine-level, not repository content.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import posixpath
import re
import shlex
import tempfile
import time
from pathlib import Path

HOME = Path.home()

#: The ``.claude`` directory this module itself lives in.
#:
#: Every hook and script that calls into here **ships inside the tree it needs
#: to resolve** -- ``<repo>/.claude/hooks/`` and ``<repo>/.claude/scripts/``.
#: So the file's own location is the one rank a caller cannot get wrong.
#:
#: This exists because the first fix for work item #35 did not have it, and was
#: therefore only correct when the current directory happened to be the repo
#: root. ``CLAUDE_PROJECT_DIR`` is unset in every plain shell, so resolution
#: fell to ``Path.cwd()`` and then to an emptied ``~/.claude`` -- reproducing
#: the original silent blindness verbatim from any subdirectory, at exit 0.
#: Rebindable (like ``HOME``) so a test harness can neutralize this rank.
SELF_ROOT = Path(__file__).resolve().parent.parent

#: Registry files, which moved into a ``registries/`` subfolder in the repo
#: layout but sit at the root of the global one.
REGISTRY_NAMES = ("MECHANISMS.md", "VOCABULARY.md", "JOURNAL.md", "INTEGRATION.md")


def project_dir() -> Path | None:
    """The project root Claude Code is operating on, if it told us."""
    raw = os.environ.get("CLAUDE_PROJECT_DIR")
    if not raw:
        return None
    try:
        return Path(raw).resolve()
    except OSError:
        return Path(raw)


def claude_roots() -> list[Path]:
    """Every ``.claude`` directory worth searching, project-local first."""
    roots: list[Path] = []

    def add(path: Path) -> None:
        if path not in roots:
            roots.append(path)

    proj = project_dir()
    if proj is not None:
        add(proj / ".claude")
    # Rank 1 -- this module's own .claude. Ranks 0 and 2 are both
    # caller-controlled and both silently wrong when the caller is a plain
    # shell in a subdirectory; SELF_ROOT is not. See the constant's note.
    add(SELF_ROOT)
    try:
        add(Path.cwd() / ".claude")
    except OSError:
        pass
    add(HOME / ".claude")
    return roots


def concepts_roots() -> list[Path]:
    """Concept-contract roots, project-local first.

    The repo keeps contracts **flat** in ``.claude/concepts/``.

    .. note::
       This docstring previously claimed "callers already ``rglob`` these
       roots, so both layouts resolve", describing a project-partitioned
       ``~/.claude/concepts/<project>/`` arrangement as equally supported.
       That is no longer true: work item #35 settled on the flat repo layout
       only (INV-8), and the discovery walks were retargeted accordingly.
       A consequence worth stating plainly: because
       ``first_populated_dir(roots, "*.md")`` matches only files directly
       inside a root, a project-partitioned root can never be selected -- its
       contracts sit one level down. The "global second" fallback is
       therefore structurally unreachable for concepts and north-stars.
    """
    return [root / "concepts" for root in claude_roots()]


def registry(name: str) -> Path:
    """Locate a registry file across both layouts.

    Returns the first candidate that exists; if none do, returns the
    preferred (project-local, ``registries/``-qualified) path so that a caller
    writing the file creates it in the right place.
    """
    candidates: list[Path] = []
    for root in claude_roots():
        candidates.append(root / "registries" / name)
        candidates.append(root / name)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def hook_file(name: str) -> Path:
    """Locate a sidecar file that lives next to the hooks (rules, exceptions).

    INV-O3: the PROJECT's copy (``<CLAUDE_PROJECT_DIR>/.claude/hooks/<name>``) is read first and the
    plugin's template beside this script is the fallback. A hook that runs from a plugin sits beside
    a template, never beside the project's data, so the order is what keeps a project's own rules in
    force. With no project named, the template comes first, as it always did.
    """
    here = Path(__file__).resolve().parent
    proj = project_dir()
    candidates: list[Path] = []
    if proj is not None:
        candidates.append(proj / ".claude" / "hooks" / name)
    candidates.append(here / name)
    candidates.extend(root / "hooks" / name for root in claude_roots())
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def state_dir() -> Path:
    """Per-project hook state, project-local when we know the project.

    These are dedupe cursors (which critic runs and journal entries have
    already been seen). They are per-checkout, not per-machine, so they
    belong beside the hooks that write them. Gitignored -- runtime, not
    content.
    """
    proj = project_dir()
    if proj is not None:
        return proj / ".claude" / "state"
    return HOME / ".claude" / "state"


def logs_dir() -> Path:
    """Hook logs, project-local when we know the project.

    Kept in the repo so the guards' audit trails live beside the guards,
    and so ``~/.claude/hooks/`` is not silently recreated purely to hold
    a log file.
    """
    proj = project_dir()
    if proj is not None:
        return proj / ".claude" / "logs"
    return HOME / ".claude" / "logs"


# ---------------------------------------------------------------------------
# Data-file locators (added for work item #35).
#
# The seven scripts under ``.claude/scripts/`` used to resolve these paths as
# module-level ``Path.home() / ".claude" / ...`` constants. The 2026-08-25
# migration emptied that tree, so they silently read nothing and returned
# empty results. Everything below is a CALL-TIME function -- never evaluate a
# path at import time, or a test cannot redirect the roots and the caller
# cannot follow a checkout. See the contract's INV-2.
# ---------------------------------------------------------------------------


def _first_root_containing(relative: str) -> Path:
    """First Claude data root that actually holds ``relative``.

    Mirrors :func:`registry`: the *presence of the thing sought* decides, not
    the mere existence of a root. When no root holds it, the preferred
    (rank-0, repo-shaped) candidate is returned so a writer creates the file
    in the right place rather than beside an unrelated checkout.
    """
    candidates = [root / relative for root in claude_roots()]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def area_mapping_path() -> Path:
    """The area-map that ``derive_area.py`` buckets contracts against."""
    return _first_root_containing("area-mapping.json")


def memory_blocks_path() -> Path:
    """The memory-surface budgets that the pager and the health audit read.

    Mirrors :func:`area_mapping_path` exactly. It exists because
    ``_memory_common`` hard-coded ``~/.claude/memory-blocks.json``, which the
    2026-08-25 migration emptied: the pager stayed registered, could not find
    its configuration, logged ``config-load-failed`` and returned 0 on every
    single turn for forty-four days. A hook that fails open and logs quietly
    looks exactly like a hook with nothing to say.
    """
    return _first_root_containing("memory-blocks.json")


def settings_path() -> Path:
    """The ``settings.json`` that registers this project's hooks.

    Needed by any check that asks "is that hook actually wired?". Hard-coding
    the answer breaks in a worktree, where the repository root is not the one
    the user cloned.
    """
    return _first_root_containing("settings.json")


def work_item_conventions_path() -> Path:
    """The work-item title/link conventions shared by ``/task`` and ``/ship``.

    Mirrors :func:`area_mapping_path` exactly -- CALL-TIME, zero-argument,
    and decided by the presence of the file rather than the existence of a
    root. Added for work item #39: ``verify_issue_link.py`` reads the
    ``issueLink`` block from here so neither SKILL.md restates the keyword
    data (INV-8).
    """
    return _first_root_containing("work-item-conventions.json")


def work_items_dir() -> Path:
    """The directory holding Work Item Briefs.

    Added for work item #39. This is the locator that makes INV-12's word
    "every" literally true: the brief path is ``verify_issue_link.py``'s
    primary input and was the one path in that script with no resolver
    behind it.
    """
    return _first_root_containing("work-items")


def accuracy_state_path() -> Path:
    """The contract-accuracy ledger.

    Exactly one copy is authoritative and it is the git-tracked repo copy --
    the ledger is repository *content*, not machine state, which is why this
    resolves through ``claude_roots()`` rather than through :func:`state_dir`.
    """
    return _first_root_containing("contract-accuracy.json")


def north_stars_roots() -> list[Path]:
    """North-star roots, project-local first. Mirrors :func:`concepts_roots`."""
    return [root / "north-stars" for root in claude_roots()]


def cache_dir() -> Path:
    """Derived-cache directory, project-local when we know the project.

    Sibling of :func:`state_dir` / :func:`logs_dir` and follows their rule.
    Callers compose their own leaf (``cache_dir() / "cross-area-scans"``).

    Cached scans are keyed on contract text alone while the scan's *result*
    depends on this checkout's ``area-mapping.json`` and ``JOURNAL.md`` -- so
    a cache shared between checkouts can serve one checkout's answer to
    another. Keeping it beside the inputs is what prevents that.

    Unlike :func:`state_dir` and :func:`logs_dir`, this resolves through the
    full root search rather than ``project_dir()`` alone. Those two hold
    machine-level runtime; this holds data *derived from repository content*,
    so a plain ``py -3 .claude/scripts/...`` invocation from inside a checkout
    -- where ``CLAUDE_PROJECT_DIR`` is unset -- must still land in that
    checkout's cache rather than in a machine-wide one shared with every other
    worktree. First existing root wins; if none exists, the preferred (rank-0)
    root, so the directory is created in the right place.
    """
    roots = claude_roots()
    for root in roots:
        if root.is_dir():
            return root / "cache"
    return roots[0] / "cache"


def first_populated_dir(roots, pattern: str = "*") -> Path:
    """First root that actually CONTAINS something matching ``pattern``.

    Deliberately not "first root that exists": a bare existence test lets an
    empty ``.claude/concepts/`` in the current directory win and report zero
    contracts -- silently, with exit 0 -- which is the very defect this work
    item repairs, reconstituted one rank down. This mirrors :func:`registry`'s
    first-that-``is_file`` rule.

    Never a union of roots: unioning would leak another project's contracts
    into this project's inventory and into the accuracy ledger.

    When no root is populated, returns the preferred (rank-0) root, matching
    the preferred-path-on-absence rule above. Callers then glob an empty or
    absent directory and receive an empty inventory -- fail-open preserved.
    """
    candidates = list(roots)
    for candidate in candidates:
        try:
            if candidate.is_dir() and any(candidate.glob(pattern)):
                return candidate
        except OSError:
            continue
    if candidates:
        return candidates[0]
    proj = project_dir()
    return (proj / ".claude") if proj is not None else (HOME / ".claude")


def project_aliases(root: Path) -> set[str]:
    """Case-folded names a ``--project`` filter accepts for this checkout.

    ``root`` is a resolved data root (``<checkout>/.claude/concepts``,
    ``<checkout>/.claude/north-stars``, ...); the checkout is two levels up.

    Why a SET rather than one canonical name: flattening the layout (#35,
    INV-8) removed the ``concepts/<project>/`` directory level that used to
    carry the project identity, and the obvious substitute -- the directory
    above ``.claude`` -- is the **branch slug** inside a worktree
    (``20260826-bug-35-...``). That silently broke
    ``--project <the repository name>``, an invocation both
    ``list-contracts`` and ``north-star-review`` document in their SKILL.md:
    it matched nothing and exited 0.

    So both names are accepted -- the checkout directory and, when this is a
    git worktree, the main working tree's directory. Display still uses the
    checkout name; only *matching* is widened. Comparison is case-folded
    because a hand-typed project name should not have to match casing.
    """
    checkout = root.parent.parent
    names = {checkout.name}

    # In a worktree, `.git` is a FILE containing
    # "gitdir: <main>/.git/worktrees/<name>" -- walk back up to <main>.
    gitfile = checkout / ".git"
    try:
        if gitfile.is_file():
            raw = gitfile.read_text(encoding="utf-8", errors="ignore")
            _, _, target = raw.partition(":")
            gitdir = Path(target.strip())
            if gitdir.parent.name == "worktrees":
                names.add(gitdir.parent.parent.parent.name)
    except (OSError, IndexError, ValueError):
        pass

    return {n.casefold() for n in names if n}


def project_matches(root: Path, requested: str | None) -> bool:
    """True when ``requested`` names this checkout (or no filter was given)."""
    if not requested:
        return True
    return requested.casefold() in project_aliases(root)


# ---------------------------------------------------------------------------
# Guard path helpers (issue #222 -- "worktree source is judged like
# main-checkout source by every path guard").
#
# ``/task`` places every worktree at ``<repo>/.claude/worktrees/<name>/``, so
# every path inside a worktree contains the substring ``/.claude/`` and was
# therefore bypassed outright by every guard's ".claude is always config"
# allow-list rule. The two functions below let a guard test its allow-list
# against the path a file would have in the MAIN checkout -- the
# "checkout-equivalent path" -- instead of the raw one, so worktree source is
# judged exactly like main-checkout source while a worktree's OWN
# ``.claude/`` configuration (which the checkout-equivalent path turns back
# into a plain ``.claude/`` path) stays allowed.
#
# Both functions are PURE (INV-4): one path string in, a string (or ``None``)
# out. No filesystem read, no environment variable, no working directory --
# a worktree segment is recognised from the text alone, so the verdict does
# not depend on which root ``CLAUDE_PROJECT_DIR`` or the working directory
# names.
# ---------------------------------------------------------------------------

#: The literal directory name ``/task`` creates worktrees under, i.e. the
#: middle component of a worktree segment ``.claude/worktrees/<name>/``.
WORKTREES_DIRNAME = "worktrees"


def _split_leading_marker(s: str) -> tuple[str, str]:
    """Split a forward-slashed path into its leading marker and the rest.

    The marker is ``"//"`` for a network path (a leading pair of separators,
    kept verbatim -- INV-8), ``"/"`` for an ordinary absolute path, or ``""``
    for a relative one. The remainder is returned unmodified.
    """
    if s.startswith("//"):
        return "//", s[2:]
    if s.startswith("/"):
        return "/", s[1:]
    return "", s


def _normalized_components(raw_fs: str) -> tuple[str, list[str]]:
    """Return ``(leading_marker, components)`` for a forward-slashed path.

    Runs of separators collapse to one (empty components from a doubled
    separator are dropped) and ``.`` components are dropped, EXCEPT a
    genuine leading ``.`` (a relative-path marker at position 0 of a
    non-absolute path), which is kept -- both per INV-8. This is used only
    to SEARCH for a worktree segment; when none is found the caller must
    fall back to the raw text (INV-3 / the Checkout-equivalent path
    invariant), never to this normalized form.
    """
    leading, rest = _split_leading_marker(raw_fs)
    components: list[str] = []
    for idx, part in enumerate(rest.split("/")):
        if part == "":
            continue  # doubled separator
        if part == ".":
            if leading == "" and idx == 0:
                components.append(part)  # genuine leading "./" marker
            continue  # "." elsewhere is dropped
        components.append(part)
    return leading, components


def _windows_alias_normalize(component: str) -> str:
    """Fold a Windows alias spelling of a path component onto the plain one.

    Windows treats a trailing ``.`` / space run, and an NTFS
    alternate-data-stream suffix (``name::$INDEX_ALLOCATION``), as naming the
    SAME directory as the plain spelling -- ``worktrees.``, ``worktrees ``
    and ``worktrees::$INDEX_ALLOCATION`` all resolve to ``worktrees`` on
    disk. Cuts at the first ``:`` (dropping any ADS suffix) and strips
    trailing dots/spaces from what remains. Does not otherwise change what
    counts as a match: ``worktreesX`` and ``foo.claude`` are unaffected
    (round 3 task F). Casefold is applied by the caller.
    """
    head = component.split(":", 1)[0]
    return head.rstrip(". ")


def _worktree_segment_spans(components: list[str]) -> list[tuple[int, int]]:
    """Non-overlapping ``[start, end)`` index spans of every worktree segment.

    A worktree segment is three consecutive components: ``.claude``
    (case-insensitive whole component, compared LITERALLY -- no alias
    normalization), ``worktrees`` (``WORKTREES_DIRNAME``, case-insensitive,
    compared after :func:`_windows_alias_normalize`), and exactly one more
    component (any name) -- matched even when that third component is the
    last one in the path (the worktree root itself, INV-8). Nested worktrees
    produce two adjacent spans and both are found by this single
    left-to-right scan.

    Only the ``worktrees`` component is alias-folded (round 3 task F).
    ``.claude`` is deliberately compared without :func:`_windows_alias_normalize`
    (round 4 item 3 / security BLOCKER B1, code BLOCKER B1): the real
    project-layout allow-list entries this segment strip feeds into are
    themselves TWO-COMPONENT paths (``src/<project>.api/``,
    ``tools/db-protection/``, ``assets/wiki/``), and master never granted an
    aliased ``.claude`` spelling (``.claude.``, ``.claude::$INDEX_ALLOCATION``)
    the worktree-segment bypass. Folding it would let a component like
    ``.claude.`` sitting between ``src/`` and an allow-listed tail get
    stripped as though it were a genuine worktree segment, JOINING the two
    unrelated halves into a recognised two-component entry that was never
    actually there.
    """
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(components)
    while i < n:
        if (
            i + 2 < n
            and components[i].casefold() == ".claude"
            and _windows_alias_normalize(components[i + 1]).casefold() == WORKTREES_DIRNAME
        ):
            spans.append((i, i + 3))
            i += 3
            continue
        i += 1
    return spans


def checkout_equivalent_path(path_str: str) -> str:
    """The path a file would have in the main checkout (INV-2, INV-3).

    Every worktree segment (``.claude/worktrees/<name>/``, matched
    case-insensitively with either separator, possibly repeated when
    worktrees nest) is removed. This is the ONLY input each guard's
    segment/substring bypass test should read -- filename and extension
    tests, and "Files to touch" matching, keep reading the raw path.

    When the path contains no worktree segment, the raw path is returned
    with backslashes turned to forward slashes and NOTHING else changed --
    not even the doubled-separator/``.``-component normalization used to
    search for a segment -- so no main-checkout verdict can move (INV-3).

    Pure (INV-4): no filesystem, environment or cwd access.
    """
    if not isinstance(path_str, str) or not path_str:
        return path_str
    raw_fs = path_str.replace("\\", "/")
    leading, components = _normalized_components(raw_fs)
    spans = _worktree_segment_spans(components)
    if not spans:
        return raw_fs
    kept: list[str] = []
    cursor = 0
    for start, end in spans:
        kept.extend(components[cursor:start])
        cursor = end
    kept.extend(components[cursor:])
    return leading + "/".join(kept)


def enclosing_worktree_root(path_str: str) -> str | None:
    """The directory ending at the INNERMOST worktree segment, or ``None``.

    Used to add ``<result>/.claude/concepts`` to a target's contract search
    (INV-7 / A3) so a worktree's own approved contract is still found once
    its source is no longer bypassed by the whole-``.claude`` allow-list
    entry. Never a sibling worktree's root, and never derived from anything
    but the target path itself (INV-4).

    Returns ``None`` exactly when ``path_str`` holds no worktree segment.
    """
    if not isinstance(path_str, str) or not path_str:
        return None
    raw_fs = path_str.replace("\\", "/")
    leading, components = _normalized_components(raw_fs)
    spans = _worktree_segment_spans(components)
    if not spans:
        return None
    _, last_end = spans[-1]
    return leading + "/".join(components[:last_end])


# ---------------------------------------------------------------------------
# Main-checkout classification and path resolution (contract
# 2026-10-07-worktree-isolation-by-default, Data Shapes: Tree kind, Main
# checkout root, Resolved path).
#
# Unlike their neighbours these read ``.git`` entries, never the environment
# or the working folder (``resolve_target`` alone reads the hook's environment
# to expand variables). Standard library only; no subprocess.
# ---------------------------------------------------------------------------

#: Git for Windows' own root folders: a path rooted in one of them is outside
#: every repository.
GIT_ROOT_FOLDERS = ("tmp", "usr", "etc", "bin", "dev", "proc", "opt", "var", "mingw32", "mingw64")

#: Marker for a Resolved path that lies outside every repository.
OUTSIDE = "<outside-every-repository>"

_NO_TARGET_BASH = ("/dev/null", "/dev/stdout", "/dev/stderr")
_ENV_REF = re.compile(r"\$\{(\w+)\}|\$(\w+)|%(\w+)%")


def _git_file_kind(gitfile: str, folder: str) -> tuple[str, str | None]:
    """Classify a ``.git`` FILE: linked worktree when its git directory holds ``commondir``."""
    try:
        with open(gitfile, "r", encoding="utf-8") as fh:
            first = fh.readline().strip()
        if not first.startswith("gitdir:") or not first[len("gitdir:"):].strip():
            return "undecidable", None
        target = os.path.normpath(os.path.join(folder, first[len("gitdir:"):].strip()))
        if not os.path.isdir(target):
            return "undecidable", None
        commondir = os.path.join(target, "commondir")
        if not os.path.isfile(commondir):
            return "main-checkout", os.path.realpath(folder)
        with open(commondir, "r", encoding="utf-8") as fh:
            relative = fh.readline().strip()
        common = os.path.realpath(os.path.join(target, relative)) if relative else ""
        if not common or not os.path.isdir(common):
            return "undecidable", None
        return "linked-worktree", os.path.dirname(common)
    except (OSError, ValueError, UnicodeError):
        return "undecidable", None


def _classify(path: str) -> tuple[str, str | None]:
    """``(tree kind, main checkout root)`` of the nearest existing ancestor of ``path``."""
    try:
        folder = os.path.abspath(path)
        while not os.path.exists(folder):
            parent = os.path.dirname(folder)
            if parent == folder:
                return "outside-repository", None
            folder = parent
        while True:
            entry = os.path.join(folder, ".git")
            if os.path.isdir(entry):
                return "main-checkout", os.path.realpath(folder)
            if os.path.isfile(entry):
                return _git_file_kind(entry, folder)
            parent = os.path.dirname(folder)
            if parent == folder:
                return "outside-repository", None
            folder = parent
    except (OSError, ValueError):
        return "undecidable", None


def tree_kind(path: str) -> str:
    """``main-checkout``, ``linked-worktree``, ``outside-repository`` or ``undecidable``."""
    return _classify(path)[0]


def main_checkout_root(path: str) -> str | None:
    """Folder holding the main checkout's ``.git`` (for a linked worktree, the parent of the
    common git directory); ``None`` for outside-repository and undecidable."""
    return _classify(path)[1]


def _expand_variables(text: str) -> str:
    """Expand ``~`` and the variables present in the hook's own environment."""
    if text == "~" or text.startswith(("~/", "~\\")):
        text = os.path.expanduser(text)
    return _ENV_REF.sub(lambda m: os.environ.get(m.group(1) or m.group(2) or m.group(3), m.group(0)), text)


def resolve_target(text: str, acting_dir: str | None, reading: str) -> tuple[str, str | None]:
    """Resolve one path text. Returns ``(status, path)``; status is ``path``, ``no-target``,
    ``outside`` or ``unresolvable``. ``reading`` is ``bash`` or ``windows``; ``acting_dir`` is a
    resolved path, ``OUTSIDE`` or ``None`` (unresolvable)."""
    try:
        t = text.strip()
        if reading == "windows" and t.lower() in ("$null", "nul"):
            return "no-target", None
        t = _expand_variables(t)
        if t.startswith("~") or re.search(r"[$`]|%[^%\s]+%", t):
            return "unresolvable", None
        t = re.sub(r"^[/\\]{2}[?.][/\\]", "", t)
        slashed = t.replace("\\", "/")
        drive = os.path.splitdrive(t)[0]
        if not drive and re.match(r"^/(?!/)", slashed):
            if reading == "bash":
                if slashed in _NO_TARGET_BASH:
                    return "no-target", None
                m = re.match(r"^/(?:(?:cygdrive|mnt)/)?([A-Za-z])(?:/(.*))?$", slashed)
                if m:
                    t = m.group(1).upper() + ":/" + (m.group(2) or "")
                elif slashed.lstrip("/").split("/")[0].lower() in GIT_ROOT_FOLDERS:
                    return "outside", None
                else:
                    return "unresolvable", None
            else:
                lead = os.path.splitdrive(acting_dir)[0] if acting_dir not in (None, OUTSIDE) else ""
                if not lead:
                    return "unresolvable", None
                t = lead + t
        elif not drive:
            if acting_dir is None:
                return "unresolvable", None
            if acting_dir == OUTSIDE:
                return "outside", None
            t = os.path.join(acting_dir, t)
        drive, rest = os.path.splitdrive(t)
        parts = []
        for comp in re.split(r"[/\\]+", rest):
            if comp in ("", "."):
                continue
            if comp != ".." and os.name == "nt":
                comp = _windows_alias_normalize(comp)
            if comp:
                parts.append(comp)
        current = drive + os.sep + os.sep.join(parts)
        tail: list[str] = []
        while not os.path.exists(current):
            parent, leaf = os.path.split(current)
            if parent == current or not leaf:
                break
            tail.insert(0, leaf)
            current = parent
        real = os.path.realpath(current)
        return "path", os.path.normpath(os.path.join(real, *tail)) if tail else real
    except (OSError, ValueError):
        return "unresolvable", None


# ---------------------------------------------------------------------------
# The installed plugin root (contract 2026-10-12-dedupe-claude-config, Business Concept
# "Installed plugin root").
#
# ONE locator for "the plugin version this project runs". The order is fixed and the shell
# snippet every skill carries (see test_skill_script_lookup.py) answers the same way:
#
#   1. the folder named by CLAUDE_PLUGIN_ROOT (the running version);
#   2. the installPath that installed_plugins.json records: an entry scoped to THIS project
#      first (path compared with case and slashes folded), then the user-scope entry;
#   3. the newest version folder in the plugin cache, compared as numbers, never as text.
#
# A recorded path that no longer exists falls through to the next step. A cache folder whose
# name is not a version is ignored. CLAUDE_CONFIG_DIR is honoured, else the home .claude is
# read. Nothing found gives None.
# ---------------------------------------------------------------------------

#: The plugin's name: its cache folders and its installed_plugins.json keys carry it.
PLUGIN_NAME = "agentic-auto-improve"
_VERSION_FOLDER_RE = re.compile(r"^\d+(?:\.\d+)*$")


def _config_dir() -> Path:
    """Claude Code's configuration folder: ``CLAUDE_CONFIG_DIR`` when set, else ``~/.claude``."""
    raw = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    return Path(raw) if raw else Path.home() / ".claude"


def _fold_path(text: object) -> str:
    """A path with its slashes unified and its letter case folded, for equality tests only."""
    return posixpath.normpath(str(text).replace("\\", "/")).casefold()


def _recorded_install_paths(config: Path, project_text: str) -> list[Path]:
    """The ``installPath`` values ``installed_plugins.json`` records for this plugin.

    Entries scoped to ``project_text`` come first, then the user-scope entries, each group in the
    order the file lists them. An unreadable record gives an empty list.
    """
    try:
        data = json.loads((config / "plugins" / "installed_plugins.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    plugins = data.get("plugins") if isinstance(data, dict) else None
    if not isinstance(plugins, dict):
        return []
    for_project: list[Path] = []
    for_user: list[Path] = []
    for key, entries in plugins.items():
        if not (isinstance(key, str) and key.split("@", 1)[0] == PLUGIN_NAME and isinstance(entries, list)):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            install = entry.get("installPath")
            if not isinstance(install, str) or not install.strip():
                continue
            scope = entry.get("scope")
            if scope == "project":
                recorded = entry.get("projectPath")
                if (project_text and isinstance(recorded, str) and recorded.strip()
                        and _fold_path(recorded) == _fold_path(project_text)):
                    for_project.append(Path(install))
            elif scope == "user":
                for_user.append(Path(install))
    return for_project + for_user


def _newest_cached_version(config: Path) -> Path | None:
    """The cache folder with the highest version number, over every marketplace folder."""
    best: Path | None = None
    best_key: tuple[int, ...] | None = None
    try:
        markets = [m for m in (config / "plugins" / "cache").iterdir() if m.is_dir()]
    except OSError:
        return None
    for market in markets:
        try:
            versions = list((market / PLUGIN_NAME).iterdir())
        except OSError:
            continue
        for folder in versions:
            if not (folder.is_dir() and _VERSION_FOLDER_RE.match(folder.name)):
                continue
            key = tuple(int(part) for part in folder.name.split("."))
            if best_key is None or key > best_key:
                best, best_key = folder, key
    return best


def installed_plugin_root(project: "str | os.PathLike[str] | None" = None) -> Path | None:
    """The folder of the plugin version this project runs, or ``None`` when none is installed.

    ``project`` names the project to match a project-scope record against; ``None`` means
    ``CLAUDE_PROJECT_DIR``. See the block comment above for the fixed order.
    """
    named = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip()
    if named and Path(named).is_dir():
        return Path(named)
    config = _config_dir()
    project_text = str(project) if project else os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    for recorded in _recorded_install_paths(config, project_text):
        if recorded.is_dir():
            return recorded
    return _newest_cached_version(config)


# ---------------------------------------------------------------------------
# Guard deference (contract 2026-10-12-dedupe-claude-config, Value Objects "Project guard
# registration", conditions (a) to (h), invariants I-D1 to I-D3).
#
# The plugin registers both database guards. A project that registers its OWN copy of the same
# guard for the same event and tool would run the guard twice, so the plugin's copy stands down
# ("defers") when, and only when, EVERY condition below holds. Any failure or error resolves
# toward ACTING: the worst outcome of a wrong "act" is a guard that runs twice, never a call
# that no guard checks. This is not a guard that turns itself off: the project's copy is the one
# that then blocks, and a deferral is written to the project's db-guard.log so a clean exit with
# no log line is never read as one.
#
# Only ONE top-level function here has "defer" in its name; the guards bind it with getattr and
# fall back to acting when it is missing, stale or raises (test_guard_deference.py D8, D9).
# ---------------------------------------------------------------------------

#: Claude Code's default timeout for a command hook, in seconds. An unset ``timeout`` on either
#: side is read as this value (contract decision 3 of the block 2 review, row D19). It is the
#: value Claude Code's hooks reference documents for a command hook with no ``timeout``.
DEFAULT_HOOK_TIMEOUT_SECONDS = 60
#: Prefix of the session-start marker file. Block 17's changed-file baseline uses another prefix
#: (``auto-improve-changed-baseline-``) so the two never collide (decision 2).
SESSION_MARKER_PREFIX = "auto-improve-session-start-"
#: The SessionStart sources that write a marker. ``clear`` and ``compact`` write none.
SESSION_MARKER_SOURCES = ("startup", "resume")
#: A settings file must be at least this many seconds older than the marker (condition (h)).
SETTINGS_SETTLE_SECONDS = 2.0
#: The only event a database guard is registered for.
GUARD_EVENT = "PreToolUse"
#: A session id is used in a file name, so it may hold only these characters.
_SESSION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_MARKER_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
#: Rotate the project's db-guard.log at this size, like the guard's own audit writer does.
DEFERRAL_LOG_MAX_BYTES = 10 * 1024 * 1024


def _marker_path(session_id: object) -> Path | None:
    """The marker file of a session in the system temporary folder, or ``None`` for an unusable id."""
    if not isinstance(session_id, str) or not _SESSION_ID_RE.fullmatch(session_id):
        return None
    return Path(tempfile.gettempdir()) / (SESSION_MARKER_PREFIX + session_id)


def write_session_start_marker(payload: object) -> bool:
    """Record the start of a session: a file named by ``session_id`` holding the time as a number.

    Written only when the payload's ``source`` is ``startup`` or ``resume``. Returns whether a
    marker was written. It never raises and prints nothing; a failure leaves no marker, which
    makes the guards act (condition (h)).
    """
    if not isinstance(payload, dict) or payload.get("source") not in SESSION_MARKER_SOURCES:
        return False
    path = _marker_path(payload.get("session_id"))
    if path is None:
        return False
    scratch = path.with_name(path.name + ".tmp-%d" % os.getpid())
    try:
        scratch.write_text("%.6f" % time.time(), encoding="utf-8")
        os.replace(scratch, path)
        return True
    except OSError:
        try:
            scratch.unlink()
        except OSError:
            pass
        return False


def _read_session_start(session_id: object) -> float | None:
    """The time a session's marker records, or ``None`` when it is missing, unreadable or not a number."""
    path = _marker_path(session_id)
    if path is None:
        return None
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return float(text) if _MARKER_NUMBER_RE.fullmatch(text) else None


def _read_json_object(path: Path) -> dict:
    """A JSON file that must hold an object. Raises when it cannot be read or is not one."""
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("%s does not hold a JSON object" % path)
    return data


def _launched_script(entry: dict) -> str | None:
    """The script a hook row launches: the first ``args`` element that does not start with ``-``
    (exec form), or the first token after the interpreter that ends in ``.py`` (shell form)."""
    args = entry.get("args")
    if isinstance(args, list):
        for arg in args:
            if isinstance(arg, str) and arg and not arg.startswith("-"):
                return arg
        return None
    command = entry.get("command")
    if not isinstance(command, str):
        return None
    try:
        tokens = shlex.split(command, posix=False)
    except ValueError:
        return None
    for token in tokens[1:]:
        token = token.strip("\"'")
        if token.lower().endswith(".py"):
            return token
    return None


def _matcher_covers(matcher: object, tool: str) -> bool:
    """A hook group's matcher against a tool name, as a whole-string regular expression.
    An empty or missing matcher, or ``*``, matches every tool."""
    if matcher is None or matcher in ("", "*"):
        return True
    if not isinstance(matcher, str):
        return False
    try:
        return re.fullmatch(matcher, tool) is not None
    except re.error:
        return False


def _matching_rows(settings: object, tool: str, launches) -> list[dict]:
    """The ``PreToolUse`` command rows of a settings (or ``hooks.json``) body whose group matcher
    covers ``tool`` and whose launched script satisfies ``launches``."""
    hooks = settings.get("hooks") if isinstance(settings, dict) else None
    groups = hooks.get(GUARD_EVENT) if isinstance(hooks, dict) else None
    rows: list[dict] = []
    if not isinstance(groups, list):
        return rows
    for group in groups:
        if not isinstance(group, dict) or not _matcher_covers(group.get("matcher"), tool):
            continue
        entries = group.get("hooks")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("type") != "command":
                continue
            script = _launched_script(entry)
            if script is not None and launches(script):
                rows.append(entry)
    return rows


def _row_timeout(entry: dict) -> float | None:
    """A row's effective timeout in seconds; unset is the default; an unusable value is ``None``."""
    value = entry.get("timeout")
    if value is None:
        return float(DEFAULT_HOOK_TIMEOUT_SECONDS)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    return float(value)


def _plugin_guard_timeout(guard_file: str, tool: str) -> float:
    """The plugin's own effective timeout for a guard (decision 3): among its ``hooks.json``
    registrations whose matcher covers ``tool``, the largest. Raises when ``hooks.json`` is unusable."""
    body = _read_json_object(Path(__file__).resolve().parent / "hooks.json")
    wanted = guard_file.casefold()
    rows = _matching_rows(body, tool, lambda script: posixpath.basename(script.replace("\\", "/")).casefold() == wanted)
    timeouts = [_row_timeout(row) for row in rows]
    if any(t is None for t in timeouts):
        raise ValueError("a plugin registration of %s has an unusable timeout" % guard_file)
    return max(timeouts) if timeouts else float(DEFAULT_HOOK_TIMEOUT_SECONDS)


def _git_top_level(start: object) -> Path | None:
    """The nearest folder at or above ``start`` that holds a ``.git`` entry (folder or file)."""
    if not isinstance(start, str) or not start.strip():
        return None
    try:
        folder = Path(start).resolve()
    except (OSError, ValueError):
        return None
    for candidate in (folder, *folder.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _candidate_settings(project: Path, payload: dict) -> list[Path]:
    """Settings files whose rows run in this session: the project's, and the top level of the git
    working tree the payload's ``cwd`` sits in when that is a different folder (a session that
    entered a worktree keeps the main checkout as its project dir but runs the worktree's rows).
    A working tree that CONTAINS the project (a monorepo) is not a worktree switch."""
    candidates = [project / ".claude" / "settings.json"]
    top = _git_top_level(payload.get("cwd"))
    if top is not None:
        try:
            resolved = project.resolve()
        except OSError:
            resolved = project
        if _fold_path(top) != _fold_path(resolved) and top not in resolved.parents:
            candidates.append(top / ".claude" / "settings.json")
    return candidates


def _project_registration_stands(guard_file: str, payload: object, running_file: str) -> bool:
    """True when conditions (a) to (h) all hold. Raises on any unexpected error."""
    project_text = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()  # (b)
    if not project_text or not isinstance(payload, dict):
        return False
    tool = payload.get("tool_name")
    if not isinstance(tool, str) or not tool:
        return False
    project = Path(project_text)
    project_copy = project / ".claude" / "hooks" / guard_file
    if os.path.normcase(os.path.realpath(running_file)) == os.path.normcase(os.path.realpath(str(project_copy))):
        return False  # (a) I-D1: a copy never defers to itself
    if not project_copy.is_file():
        return False  # (e)
    started = _read_session_start(payload.get("session_id"))  # (h) needs the marker
    if started is None:
        return False
    plugin_timeout = _plugin_guard_timeout(guard_file, tool)
    resolved_text = str(project.resolve())
    wanted = {_fold_path(project_text + "/.claude/hooks/" + guard_file),
              _fold_path(resolved_text + "/.claude/hooks/" + guard_file)}

    def launches_project_copy(script: str) -> bool:
        expanded = script.replace("${CLAUDE_PROJECT_DIR}", project_text).replace("$CLAUDE_PROJECT_DIR", project_text)
        return _fold_path(expanded) in wanted

    for settings_path in _candidate_settings(project, payload):  # (c)
        if not settings_path.is_file():
            return False
        settings = _read_json_object(settings_path)
        local_path = settings_path.with_name("settings.local.json")
        local = _read_json_object(local_path) if local_path.is_file() else {}
        if settings.get("disableAllHooks") or local.get("disableAllHooks"):
            return False  # (f)
        rows = _matching_rows(settings, tool, launches_project_copy)  # (d)
        usable = [row for row in rows
                  if row.get("async") in (None, False)  # (g) an async row cannot block
                  and (_row_timeout(row) or 0.0) >= plugin_timeout]
        if not usable:
            return False
        if settings_path.stat().st_mtime > started - SETTINGS_SETTLE_SECONDS:
            return False  # (h) the row may have been added after Claude Code fixed its hook set
    return True


def _record_deferral(hook_name: str, guard_file: str, payload: dict) -> bool:
    """Write the ``deferred`` decision to the project's db-guard.log (I-D2). Raises on failure."""
    record = {
        "ts": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "hook": hook_name,
        "session": payload.get("session_id") or "",
        "tool": payload.get("tool_name") or "",
        "decision": "deferred",
        "reason": "project-registers-own-copy",
        "project_copy": str(Path(os.environ.get("CLAUDE_PROJECT_DIR", "").strip()) / ".claude" / "hooks" / guard_file),
    }
    log = logs_dir() / "db-guard.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    if log.exists() and log.stat().st_size > DEFERRAL_LOG_MAX_BYTES:
        rotated = log.with_suffix(log.suffix + ".1")
        if rotated.exists():
            rotated.unlink()
        log.rename(rotated)
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return True


def should_defer_to_project_guard(guard_file: str, payload: object, running_file: str, hook_name: str) -> bool:
    """True when the plugin's copy of a database guard should stand down for this call.

    ``guard_file`` is the guard's file name, ``running_file`` the file now running (the guard's own
    ``__file__``) and ``hook_name`` the name its log records carry. When this returns True it has
    already written the ``deferred`` decision to the project's db-guard.log. Every failure of any
    condition, and every error, returns False: the caller acts as it does today.
    """
    try:
        if not _project_registration_stands(guard_file, payload, running_file):
            return False
        return _record_deferral(hook_name, guard_file, payload)  # type: ignore[arg-type]
    except Exception:
        return False
