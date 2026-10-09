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

import os
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
