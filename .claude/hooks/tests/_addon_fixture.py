#!/usr/bin/env python3
"""_addon_fixture.py -- the one shared helper that finds an add-on hook and installs an add-on.

An add-on hook is a hook file the plugin ships under ``.claude/addons/<add-on>/hooks/`` and does NOT
register in its ``hooks.json``. A project gets it only through that add-on's install skill, which copies
the hook files (and the helper files the add-on's manifest names) into the project's ``.claude/hooks/``.
Several suites test those hooks. They all go through this module, so the lookup is written once and the
two repositories that vendor this file see the same behaviour.

This file holds no project name. It is vendored identically in the plugin and in a consuming repository.

THE TWO FUNCTIONS EVERY SUITE USES
----------------------------------
``source(add_on, file)``
    The add-on hook file. Searched in this order:
      1. beside the tests' hooks folder (``<tests>/../<file>``): a consuming repository's unregistered or
         installed copy;
      2. ``<plugin root>/.claude/addons/<add_on>/hooks/<file>``.
    Anything else FAILS the calling test (``AddonFixtureError``, an ``AssertionError``). It never skips:
    a skipped case is a case nobody notices has stopped running.

``install_disabled(add_on, project=None)``
    The same copy for the add-on's DISABLED hooks (the manifest's ``disabled`` list) and its helpers.

``install(add_on, project=None)``
    Builds a project (a new temporary folder, or the folder given) and copies into its ``.claude/hooks/``
    the add-on's hook files AND every helper the add-on's manifest names, exactly as the install
    subcommand does: a hook file is copied from ``source()``; a helper is copied from the plugin's default
    tree to the same relative path in the project, only when the project lacks it, never over an existing
    one. Returns the installed hook paths, in the manifest's order.

THE PLUGIN ROOT
---------------
In the plugin repository the plugin root is the repository root (it holds ``.claude-plugin/plugin.json``).
In a consuming repository it is the Installed plugin root, found by ``_project_paths.installed_plugin_root``
(``CLAUDE_PLUGIN_ROOT``, then the recorded install path, then the newest cached version). When neither is
found the fixture fails; it never guesses.

THE MANIFEST
------------
``addon.json`` is read from, in order: this project's own ``.claude/addons/<add-on>/`` folder, beside the
source (``<source dir>/addon.json``), the source's parent (the add-on folder), and the plugin's add-on folder. The keys this fixture reads are the constants below;
they are the single place a change to the manifest's field names has to be made.
"""
from __future__ import annotations

import atexit
import json
import shutil
import sys
import tempfile
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
HOOKS_DIR = TESTS_DIR.parent
PROJECT_ROOT = HOOKS_DIR.parent.parent

#: The three add-ons the plugin ships.
ADDONS = ("angular-tailwind", "codegraph", "strict-shell-gate")
#: A hook file each add-on is known by. The manifest search uses it to look BESIDE the source before the
#: manifest (and so the full hook list) has been read.
KNOWN_HOOKS = {"angular-tailwind": "angular-tailwind-advisor.py", "codegraph": "codegraph-first-guard.py",
               "strict-shell-gate": "bash-gate.py"}

#: Manifest field names (the Add-on manifest, Data Shapes of the contract).
KEY_HOOKS = "hooks"
KEY_HELPERS = "helpers"
KEY_ROWS = "registrations"
KEY_PREREQUISITES = "prerequisites"
KEY_KILL_SWITCHES = "kill_switches"
KEY_INSTALL_SKILL = "install_skill"
KEY_UNINSTALL_SKILL = "uninstall_skill"
KEY_DOCUMENTS = "documents"
KEY_SNIPPET = "stylesheet_snippet"
KEY_DISABLED = "disabled"
#: Fields of one disabled hook entry.
DISABLED_HOOK, DISABLED_FORMER, DISABLED_ROW, DISABLED_NOTE, DISABLED_HASHES = (
    "hook", "former_names", "registration", "note", "released_sha256")
#: Fields of one registration row.
ROW_EVENT, ROW_MATCHER, ROW_HOOK, ROW_ARGS, ROW_ASYNC, ROW_STATUS = (
    "event", "matcher", "hook", "args", "async", "statusMessage")

#: THE ROW FORMS OLDER INSTALLS CARRY for the retired angular-tailwind advisor, as read from git history
#: (``git log -S`` over ``.claude/hooks/hooks.json``, the add-on folder and the finish-install script). Each
#: form is the hook dict of one ``UserPromptSubmit`` row (no matcher) that names the advisor file ``<file>``:
#:   ``plugin-string``   the plugin's own hooks.json up to 0.6.x (commit 9beb09f: ``py -3 "${CLAUDE_PLUGIN_ROOT}/
#:                       .claude/hooks/architecture-advisor.py"``), which a project copied by hand into its
#:                       settings.json. 0.7.0 (304ca12) took the row out of hooks.json, so a plugin install no
#:                       longer registers it;
#:   ``project-string``  the same string with the project path variable, the form a hand copy of a vendored
#:                       hook takes;
#:   ``exec-py``         the exec form the finish-install writer has written since 05a1784, and the add-on
#:                       install of 0.9.9 to 0.9.21 (5876b17): ``"command": "py", "args": ["-3", <path>]``;
#:   ``exec-python3``    the same on macOS and Linux (``"command": "python3"``).
#: A test that cleans an old install builds one project per form and per file name (current or former).
OLD_ROW_FORMS = ("plugin-string", "project-string", "exec-py", "exec-python3")
OLD_ROW_EVENT = "UserPromptSubmit"


def old_row(form: str, file: str) -> dict:
    """The hook dict of one old-install row of ``form`` that names the hook file ``file``."""
    project_path = "${CLAUDE_PROJECT_DIR}/.claude/hooks/" + file
    if form == "plugin-string":
        return {"type": "command", "command": 'py -3 "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/%s"' % file}
    if form == "project-string":
        return {"type": "command", "command": 'py -3 "%s"' % project_path}
    if form == "exec-py":
        return {"type": "command", "command": "py", "args": ["-3", project_path]}
    if form == "exec-python3":
        return {"type": "command", "command": "python3", "args": [project_path]}
    raise AddonFixtureError("no old row form %r (known: %s)" % (form, ", ".join(OLD_ROW_FORMS)))


_TEMP_FOLDERS: list[Path] = []


class AddonFixtureError(AssertionError):
    """The add-on source, manifest or plugin root could not be found. A test that gets this FAILS."""


@atexit.register
def _cleanup() -> None:
    for folder in _TEMP_FOLDERS:
        shutil.rmtree(folder, ignore_errors=True)


def new_project(prefix: str = "addon-project-") -> Path:
    """A new empty temporary project folder, removed when the process ends."""
    folder = Path(tempfile.mkdtemp(prefix=prefix))
    _TEMP_FOLDERS.append(folder)
    return folder


def plugin_root() -> Path:
    """The plugin root: this repository when it is the plugin, else the Installed plugin root."""
    if (PROJECT_ROOT / ".claude-plugin" / "plugin.json").is_file():
        return PROJECT_ROOT
    try:
        if str(HOOKS_DIR) not in sys.path:
            sys.path.append(str(HOOKS_DIR))
        import _project_paths  # noqa: WPS433
        found = _project_paths.installed_plugin_root(PROJECT_ROOT)
    except Exception as exc:  # noqa: BLE001 - any failure is the fixture's own failure
        raise AddonFixtureError(
            "no plugin root: this folder is not the plugin and the Installed plugin root could not be "
            "resolved (%s)" % exc)
    if not found or not Path(found).is_dir():
        raise AddonFixtureError(
            "no plugin root: this folder is not the plugin and no Installed plugin root was found")
    return Path(found)


def addon_dir(add_on: str) -> Path:
    """``<plugin root>/.claude/addons/<add_on>``; the folder need not exist (callers check)."""
    return plugin_root() / ".claude" / "addons" / add_on


def source(add_on: str, file: str) -> Path:
    """The add-on hook ``file``: beside the tests' hooks folder first, else the plugin's add-on folder."""
    beside = HOOKS_DIR / file
    if beside.is_file():
        return beside
    in_plugin = addon_dir(add_on) / "hooks" / file
    if in_plugin.is_file():
        return in_plugin
    raise AddonFixtureError(
        "add-on hook %r of add-on %r not found: looked beside the tests' hooks folder (%s) and at %s"
        % (file, add_on, beside, in_plugin))


def manifest_path(add_on: str, file: str | None = None) -> Path:
    """The add-on's ``addon.json``: this project's own add-on folder, beside the source, the source's parent,
    then the plugin's add-on folder (the order in the module docstring). ``file`` defaults to the add-on's
    known hook file."""
    file = file or KNOWN_HOOKS.get(add_on)
    candidates: list[Path] = [PROJECT_ROOT / ".claude" / "addons" / add_on / "addon.json"]
    if file is not None:
        try:
            src_dir = source(add_on, file).parent
            candidates += [src_dir / "addon.json", src_dir.parent / "addon.json"]
        except AddonFixtureError:
            pass
    candidates.append(addon_dir(add_on) / "addon.json")
    candidates = list(dict.fromkeys(candidates))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise AddonFixtureError(
        "manifest addon.json of add-on %r not found; looked at: %s"
        % (add_on, ", ".join(str(c) for c in candidates)))


def manifest(add_on: str, file: str | None = None) -> dict:
    """The parsed manifest; a manifest that does not parse fails the caller."""
    path = manifest_path(add_on, file)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AddonFixtureError("manifest %s does not parse: %s" % (path, exc))
    if not isinstance(data, dict):
        raise AddonFixtureError("manifest %s is not a JSON object" % path)
    return data


def hook_files(add_on: str) -> list[str]:
    """The hook file names the manifest lists."""
    names = manifest(add_on, KNOWN_HOOKS.get(add_on)).get(KEY_HOOKS)
    # An add-on may ship documents only (angular-tailwind), so the list may be empty; it must still be a list.
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise AddonFixtureError("manifest of %r has no %r list of file names" % (add_on, KEY_HOOKS))
    return list(names)


def disabled_entries(add_on: str) -> list[dict]:
    """The disabled hook entries of the manifest (an empty list when it declares none)."""
    entries = manifest(add_on, KNOWN_HOOKS.get(add_on)).get(KEY_DISABLED, [])
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise AddonFixtureError("manifest of %r has a %r that is not a list of entries" % (add_on, KEY_DISABLED))
    return list(entries)


def disabled_hook_files(add_on: str) -> list[str]:
    """The current file names of the manifest's disabled hooks."""
    names = [e.get(DISABLED_HOOK) for e in disabled_entries(add_on)]
    if not names or not all(isinstance(n, str) for n in names):
        raise AddonFixtureError("manifest of %r declares no disabled hook with a %r name" % (add_on, DISABLED_HOOK))
    return list(names)


def helper_paths(add_on: str) -> list[str]:
    """The helper paths (plugin default tree, relative to the plugin root) the manifest lists."""
    names = manifest(add_on, KNOWN_HOOKS.get(add_on)).get(KEY_HELPERS)
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise AddonFixtureError("manifest of %r has no %r list of paths" % (add_on, KEY_HELPERS))
    return list(names)


def registrations(add_on: str) -> list[dict]:
    """The registration rows the manifest lists."""
    rows = manifest(add_on, KNOWN_HOOKS.get(add_on)).get(KEY_ROWS)
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise AddonFixtureError("manifest of %r has no %r list of rows" % (add_on, KEY_ROWS))
    return list(rows)


def install(add_on: str, project: Path | str | None = None) -> list[Path]:
    """Install ``add_on`` into ``project`` (a new temporary project when None); return the hook paths."""
    return _copy_into(add_on, project, hook_files(add_on))


def install_disabled(add_on: str, project: Path | str | None = None) -> list[Path]:
    """Copy the add-on's DISABLED hooks and its helpers into ``project``; return the hook paths.

    No install writes a disabled hook, so a suite that still tests one (the retired angular-tailwind
    advisor) installs it through this function and nowhere else."""
    return _copy_into(add_on, project, disabled_hook_files(add_on))


def _copy_into(add_on: str, project: Path | str | None, files: list[str]) -> list[Path]:
    target = Path(project) if project is not None else new_project()
    helpers = helper_paths(add_on)
    hooks_dir = target / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    installed: list[Path] = []
    for name in files:
        dest = hooks_dir / name
        shutil.copyfile(source(add_on, name), dest)
        installed.append(dest)
    root = plugin_root()
    for rel in helpers:
        src = root / Path(rel)
        if not src.is_file():
            raise AddonFixtureError("helper %r of add-on %r is not in the plugin's default tree (%s)"
                                    % (rel, add_on, src))
        dest = target / Path(rel)
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    return installed


# ======================================================================================================
# CODEGRAPH FIXTURE HELPERS (issue #259, concept contract 2026-11-05-codegraph-guard-fail-open)
# ------------------------------------------------------------------------------------------------------
# Test-side fixtures shared by the codegraph guard suites. They read nothing from the developer's real
# home or temp folder: every caller passes the fixture home and the fixture temp folder.
#   * Project index        <folder>/.codegraph/codegraph.db is a regular file (a ``.codegraph`` folder with no
#                          codegraph.db is NOT an index: it is the shape of CodeGraph's per-user ``~/.codegraph``).
#   * Session folder       <temp>/auto-improve-codegraph-<session key>/ holding ``turn.json`` (the Turn marker).
#   * Linked worktree      a main checkout (.git FOLDER) + .git/worktrees/<name>/commondir + a worktree .git FILE.
# ======================================================================================================
import os  # noqa: E402
import subprocess  # noqa: E402

#: Manifest keys the contract adds.
KEY_PERMISSIONS_ALLOW = "permissions_allow"
KEY_RELEASED = "released_sha256"
#: Issue #295: ``released_versions`` maps ``{<hook>: {<folded sha256>: <earliest release label>}}``; every hash listed in
#: ``released_sha256`` has a label and no label names a hash that is not listed.
KEY_RELEASED_VERSIONS = "released_versions"
#: Issue #295: the optional ``if`` of a registration row (a non-empty string when present).
ROW_IF = "if"
#: What the codegraph add-on must grant: the wildcard only, never a per-tool name.
CODEGRAPH_WILDCARD = "mcp__codegraph__*"
CODEGRAPH_SESSION_PREFIX = "auto-improve-codegraph-"
CODEGRAPH_INDEX = ("." + "codegraph", "codegraph.db")


def permissions_allow(add_on: str) -> list:
    """The manifest's ``permissions_allow`` list; a manifest without it, or with a malformed one, FAILS the caller."""
    data = manifest(add_on, KNOWN_HOOKS.get(add_on))
    if KEY_PERMISSIONS_ALLOW not in data:
        raise AddonFixtureError("manifest of %r has no %r key" % (add_on, KEY_PERMISSIONS_ALLOW))
    value = data[KEY_PERMISSIONS_ALLOW]
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise AddonFixtureError("manifest of %r has a %r that is not a list of non-empty strings"
                                % (add_on, KEY_PERMISSIONS_ALLOW))
    return list(value)


def released_hashes(add_on: str) -> dict:
    """The manifest's ``released_sha256`` map ``{<active hook>: [sha256 hex, ...]}``; absent or malformed FAILS."""
    data = manifest(add_on, KNOWN_HOOKS.get(add_on))
    if KEY_RELEASED not in data:
        raise AddonFixtureError("manifest of %r has no %r key" % (add_on, KEY_RELEASED))
    value = data[KEY_RELEASED]
    ok = isinstance(value, dict) and value and all(
        isinstance(k, str) and isinstance(v, list) and v and all(
            isinstance(h, str) and len(h) == 64 and h == h.lower() and all(c in "0123456789abcdef" for c in h)
            for h in v)
        for k, v in value.items())
    if not ok:
        raise AddonFixtureError("manifest of %r has a %r that is not {hook: [64-hex, ...]}" % (add_on, KEY_RELEASED))
    return dict(value)


def released_versions(add_on: str) -> dict:
    """The manifest's ``released_versions`` map ``{<hook>: {<sha256 hex>: <release label>}}``; absent or malformed FAILS."""
    data = manifest(add_on, KNOWN_HOOKS.get(add_on))
    if KEY_RELEASED_VERSIONS not in data:
        raise AddonFixtureError("manifest of %r has no %r key" % (add_on, KEY_RELEASED_VERSIONS))
    value = data[KEY_RELEASED_VERSIONS]
    ok = isinstance(value, dict) and value and all(
        isinstance(k, str) and isinstance(v, dict) and v and all(
            isinstance(h, str) and len(h) == 64 and isinstance(label, str) and label.count(".") == 2
            for h, label in v.items())
        for k, v in value.items())
    if not ok:
        raise AddonFixtureError("manifest of %r has a %r that is not {hook: {64-hex: 'x.y.z'}}"
                                % (add_on, KEY_RELEASED_VERSIONS))
    return {k: dict(v) for k, v in value.items()}


class Sandbox:
    """A throw-away root with a fixture home folder and a fixture temp folder; removed on exit, pass or fail."""

    def __init__(self, prefix: str = "cgsandbox-") -> None:
        self.root = Path(tempfile.mkdtemp(prefix=prefix)).resolve()
        self.home = self.root / "home"
        self.tmp = self.root / "tmp"
        self.home.mkdir()
        self.tmp.mkdir()
        (self.home / "AppData" / "Local").mkdir(parents=True)

    def __enter__(self) -> "Sandbox":
        return self

    def __exit__(self, *exc) -> None:
        self.remove()

    def remove(self) -> None:
        # a folder link inside the sandbox is removed as a link first, so the cleanup never follows it
        for entry in self.root.rglob("*"):
            try:
                if is_link(entry):
                    os.rmdir(str(entry)) if entry.is_dir() else os.remove(str(entry))
            except OSError:
                pass
        shutil.rmtree(self.root, ignore_errors=True)
        if self.root.exists():
            LEFTOVERS.append(str(self.root))


#: Sandboxes this process could not remove (reported by the suites that care).
LEFTOVERS: list[str] = []


def is_link(path: Path) -> bool:
    """Delivery cleanup's link test: lstat, then S_ISLNK, or a Windows reparse point. Never is_junction."""
    import stat
    try:
        st = os.lstat(str(path))
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(st, "st_file_attributes", 0) & reparse)


def make_dir_link(link: Path, target: Path) -> bool:
    """A folder link at ``link`` pointing at ``target``: a junction on Windows (no privilege), a symlink on POSIX."""
    try:
        if os.name == "nt":
            done = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
            return done.returncode == 0 and link.exists()
        os.symlink(str(target), str(link), target_is_directory=True)
        return True
    except OSError:
        return False


#: The process's REAL temp folder, read once at import (before any suite points ``tempfile.tempdir`` at a fixture).
REAL_TEMP = tempfile.gettempdir()


def parent_base(env, os_name: str):
    """The Parent base rule of contract 2026-11-06-session-folder-owner-and-tool-named, as a pure function of the
    environment mapping and the OS name: ``(base path or None, problem or None)``. It reads ONLY ``env``. Windows:
    ``LOCALAPPDATA``. POSIX: ``XDG_CACHE_HOME``, and when that is unset or empty ``HOME`` + ``/.cache``; both unset
    or empty gives ``unset``. A set but relative value gives ``not-absolute`` (never skipped to the next name)."""
    import ntpath
    import posixpath
    if os_name == "nt":
        raw, isabs = env.get("LOCALAPPDATA") or "", ntpath.isabs
    else:
        isabs = posixpath.isabs
        raw = env.get("XDG_CACHE_HOME") or ""
        if not raw:
            home = env.get("HOME") or ""
            if not home:
                return None, "unset"
            if not isabs(home):
                return None, "not-absolute"
            return posixpath.join(home, ".cache"), None
    if not raw:
        return None, "unset"
    if not isabs(raw):
        return None, "not-absolute"
    return raw, None


def session_parent(home: Path, create: bool = True) -> Path:
    """The Per-user session parent the CodeGraph hooks use for a run whose fixture home is ``home``:
    ``<base>/auto-improve-codegraph``, the base computed by the pure rule from the SAME variables ``isolated_env``
    sets (``LOCALAPPDATA`` = ``<home>/AppData/Local``, ``XDG_CACHE_HOME`` = ``<home>/.cache``). Created on demand
    with ``os.mkdir(p, 0o700)`` then ``os.chmod(p, 0o700)``, never ``mkdir(parents=True)`` (a umask mode would make
    every POSIX row fail closed with ``open-mode``)."""
    home = Path(home)
    env = {"LOCALAPPDATA": str(home / "AppData" / "Local"), "XDG_CACHE_HOME": str(home / ".cache"), "HOME": str(home)}
    base, problem = parent_base(env, os.name)
    if base is None:
        raise AddonFixtureError("session_parent: the Parent base rule gave %r for %r" % (problem, env))
    parent = Path(base) / "auto-improve-codegraph"
    if create:
        for folder in (Path(base), parent):
            if not folder.is_dir():
                os.mkdir(str(folder), 0o700)
                os.chmod(str(folder), 0o700)
    return parent


def real_parent() -> Path | None:
    """The REAL Per-user session parent of the developer running the suite, by the pure rule over the ORIGINAL
    environment; None when the rule gives none."""
    base, _problem = parent_base(os.environ, os.name)
    return (Path(base) / "auto-improve-codegraph") if base else None


#: The REAL Per-user session parent, computed once at import from the original ``os.environ`` (before any suite patches it).
REAL_PARENT = real_parent()


def real_temp_codegraph_entries() -> set:
    """The names of the ``auto-improve-codegraph-*`` entries in the real temp folder (the leak check of the suites that
    run the CodeGraph hooks: a run must add none)."""
    try:
        return {n for n in os.listdir(REAL_TEMP) if n.startswith(CODEGRAPH_SESSION_PREFIX)}
    except OSError:
        return set()


def real_parent_codegraph_entries() -> set:
    """The names of the ``auto-improve-codegraph-*`` entries in the REAL Per-user session parent (a run must add none)."""
    try:
        return {n for n in os.listdir(str(REAL_PARENT)) if n.startswith(CODEGRAPH_SESSION_PREFIX)} if REAL_PARENT else set()
    except OSError:
        return set()


def real_parent_snapshot():
    """Review fix round T-L3: a snapshot of the REAL Per-user session parent that notices more than a new
    ``auto-improve-codegraph-*`` name: ``None`` when the parent folder does not exist, else the frozenset of EVERY entry name
    in it (a ``.tmp-*`` file or any non-prefixed entry counts). Comparing two snapshots also catches the parent being
    created by a run (None -> a set)."""
    if REAL_PARENT is None:
        return None
    try:
        return frozenset(os.listdir(str(REAL_PARENT)))
    except OSError:
        return None


def can_make_file_symlink(folder: Path) -> bool:
    """True when the OS lets this process create a FILE symlink under ``folder`` (Windows needs Developer Mode)."""
    probe_target = Path(folder) / "symlink-probe-target"
    probe_link = Path(folder) / "symlink-probe-link"
    try:
        probe_target.write_text("x\n", encoding="utf-8")
        os.symlink(str(probe_target), str(probe_link))
        return True
    except (OSError, NotImplementedError):
        return False
    finally:
        for leftover in (probe_link, probe_target):
            try:
                os.remove(str(leftover))
            except OSError:
                pass


def make_file_link(link: Path, target: Path, kind: str) -> bool:
    """A FILE link at ``link`` to ``target``: ``kind`` is ``hard`` (os.link, no privilege on NTFS) or ``symlink``."""
    try:
        if kind == "hard":
            os.link(str(target), str(link))
        else:
            os.symlink(str(target), str(link))
        return True
    except (OSError, NotImplementedError):
        return False


def plant_index(folder: Path) -> Path:
    """A Project index: ``<folder>/.codegraph/codegraph.db`` (a regular file) and a config.json beside it."""
    cg = Path(folder) / CODEGRAPH_INDEX[0]
    cg.mkdir(parents=True, exist_ok=True)
    (cg / "config.json").write_text("{}\n", encoding="utf-8")
    db = cg / CODEGRAPH_INDEX[1]
    db.write_bytes(b"SQLite format 3\x00 fixture index\n")
    return db


def plant_decoy(folder: Path) -> Path:
    """CodeGraph's per-user data folder shape: ``.codegraph`` with daemons/ and telemetry, and NO codegraph.db."""
    cg = Path(folder) / CODEGRAPH_INDEX[0]
    (cg / "daemons").mkdir(parents=True, exist_ok=True)
    (cg / "telemetry.json").write_text("{}\n", encoding="utf-8")
    (cg / "update-check.json").write_text("{}\n", encoding="utf-8")
    return cg


def plant_server(folder: Path, name: str = "codegraph", disabled: bool = False) -> Path:
    """A configured MCP server entry in ``<folder>/.mcp.json``; ``disabled`` also lists it in the project's
    ``.claude/settings.json`` ``disabledMcpjsonServers`` (a real read layer)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ".mcp.json"
    path.write_text(json.dumps({"mcpServers": {name: {"command": "codegraph", "args": ["serve", "--mcp"]}}}),
                    encoding="utf-8")
    if disabled:
        (folder / ".claude").mkdir(parents=True, exist_ok=True)
        (folder / ".claude" / "settings.json").write_text(
            json.dumps({"disabledMcpjsonServers": [name]}), encoding="utf-8")
    return path


def ancestors_holding(path: Path, *rel: str) -> list:
    """Every ancestor of ``path`` (and ``path`` itself) that holds ``rel`` (for example ('.codegraph', 'codegraph.db'))."""
    found = []
    current = Path(path).resolve()
    while True:
        if os.path.lexists(str(current.joinpath(*rel))):
            found.append(current)
        if current.parent == current:
            return found
        current = current.parent


def make_main_checkout(folder: Path) -> Path:
    folder = Path(folder)
    (folder / ".git").mkdir(parents=True, exist_ok=True)
    return folder


def make_linked_worktree(base: Path, name: str = "wt1", layout: str = "inside",
                         gitdir_form: str = "absolute", main: Path | None = None) -> dict:
    """A REAL linked-worktree layout: ``<main>/.git`` folder, ``<main>/.git/worktrees/<name>/commondir`` = ``../..``
    and a worktree ``.git`` FILE ``gitdir: <admin folder>``.

    ``layout``: ``inside`` puts the worktree under ``<main>/.claude/worktrees/<name>``, ``outside`` puts it beside
    the main folder. ``gitdir_form``: ``absolute`` or ``relative`` (resolved against the worktree folder).
    Returns ``{main, worktree, admin, gitdir_text}``."""
    base = Path(base)
    main = make_main_checkout(Path(main) if main else base / "main")
    admin = main / ".git" / "worktrees" / name
    admin.mkdir(parents=True, exist_ok=True)
    (admin / "commondir").write_text("../..\n", encoding="utf-8")
    worktree = (main / ".claude" / "worktrees" / name) if layout == "inside" else (base / ("wt-" + name))
    worktree.mkdir(parents=True, exist_ok=True)
    if gitdir_form == "absolute":
        text = admin.as_posix()
    elif gitdir_form == "relative":
        text = os.path.relpath(str(admin), str(worktree)).replace("\\", "/")
    else:
        raise AddonFixtureError("unknown gitdir form %r" % gitdir_form)
    (worktree / ".git").write_text("gitdir: %s\n" % text, encoding="utf-8")
    return {"main": main, "worktree": worktree, "admin": admin, "gitdir_text": text}


def session_folder(parent: Path, session_id: str) -> Path:
    """The Session folder the three hooks share for ``session_id`` under the Per-user session parent ``parent``
    (``af.session_parent(<fixture home>)``), never under the system temp folder."""
    return Path(parent) / (CODEGRAPH_SESSION_PREFIX + session_id)


def write_marker(parent: Path, session_id: str, tool: str = "mcp__codegraph__" + "codegraph_explore",
                 stamped: bool = True) -> Path:
    """Write the Turn marker as the tracker does: ``turn.json`` in the Session folder under ``parent``. ``stamped``
    (the default) writes {ts, tool, summary, pid, writer: "codegraph-turn-tracker", session: session_id}, an OWN
    marker; ``stamped=False`` writes the 0.15.2 shape {ts, tool, summary, pid}, a Foreign marker."""
    folder = session_folder(parent, session_id)
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder / "turn.json"
    body = {"ts": 1, "tool": tool, "summary": "fixture", "pid": 1}
    if stamped:
        body.update({"writer": "codegraph-turn-tracker", "session": session_id})
    marker.write_text(json.dumps(body) + "\n", encoding="utf-8")
    return marker


def remove_marker(parent: Path, session_id: str) -> None:
    marker = session_folder(parent, session_id) / "turn.json"
    if marker.exists():
        marker.unlink()


# ------------------------------------------------------------------------------------------------------
# TRANSCRIPT BUILDERS (issue #262, the cut-over). The guard decides from the session transcript, so a row that expects
# a block needs a CLOSED transcript (a human prompt and nothing after it) and a row that expects an allow through the
# gate needs an OPEN one. The shapes are the ones the t1 live checks recorded for Claude Code 2.1.318.
# ------------------------------------------------------------------------------------------------------
def t_human(n: int = 0, prompt_id: str | None = None) -> str:
    """One human prompt entry (the only entry that closes a turn)."""
    return json.dumps({"type": "user", "isSidechain": False, "promptId": prompt_id or ("p%d" % n), "promptSource": "sdk",
                       "turnOrigin": "sdk", "message": {"role": "user", "content": "question %d" % n}})


def t_assistant(*blocks: dict) -> str:
    """One assistant entry holding the given content blocks."""
    return json.dumps({"type": "assistant", "isSidechain": False,
                       "message": {"role": "assistant", "content": list(blocks)}})


def t_mcp_use(name: str = "mcp__codegraph__" + "codegraph_explore") -> str:
    return t_assistant({"type": "tool_use", "id": "toolu_mcp", "name": name, "input": {"query": "x"}})


def t_bash_use(command: str, background: bool = False) -> str:
    tool_input: dict = {"command": command}
    if background:
        tool_input["run_in_background"] = True
    return t_assistant({"type": "tool_use", "id": "toolu_bash", "name": "Bash", "input": tool_input})


def t_agent_use(name: str = "Agent") -> str:
    return t_assistant({"type": "tool_use", "id": "toolu_agent", "name": name,
                        "input": {"description": "look", "prompt": "look around", "subagent_type": "Explore"}})


def t_tool_result() -> str:
    return json.dumps({"type": "user", "isSidechain": False, "toolUseResult": {}, "sourceToolAssistantUUID": "u",
                       "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "x"}]}})


def t_task_notification() -> str:
    """A background task notification: it fires the prompt event but is NOT a human prompt (t1, point b)."""
    return json.dumps({"type": "user", "isSidechain": False, "promptId": "pn", "promptSource": "system",
                       "origin": {"kind": "task-notification"}, "message": {"role": "user", "content": "<task-notification/>"}})


def t_filler(size: int = 1000) -> str:
    return json.dumps({"type": "attachment", "attachment": {"type": "x", "content": "x" * size}})


def write_transcript(path: Path | str, lines: list) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return path


def closed_transcript(folder: Path | str, name: str = "closed.jsonl") -> Path:
    """A transcript whose last entry is a human prompt: the gate is CLOSED (a source read blocks)."""
    return write_transcript(Path(folder) / name, [t_human(1)])


def open_transcript(folder: Path | str, name: str = "open.jsonl", route: str = "mcp") -> Path:
    """A transcript with a CodeGraph use after the last human prompt: the gate is OPEN. ``route``: mcp, cli or agent."""
    use = {"mcp": t_mcp_use, "cli": lambda: t_bash_use("codegraph explore Thing"), "agent": t_agent_use}[route]()
    return write_transcript(Path(folder) / name, [t_human(1), use, t_tool_result()])


def isolated_env(home: Path, tmp: Path, project: Path | None = None, extra: dict | None = None) -> dict:
    """The environment of a codegraph row: HOME, USERPROFILE and CLAUDE_CONFIG_DIR at the fixture home, LOCALAPPDATA at
    ``<home>/AppData/Local`` and XDG_CACHE_HOME at ``<home>/.cache`` (so the Per-user session parent is inside the
    fixture), TMP and TEMP at the fixture temp folder, every CLAUDE_* and GIT_* variable of the developer removed."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_") and not k.startswith("GIT_")}
    env.update({"HOME": str(home), "USERPROFILE": str(home), "CLAUDE_CONFIG_DIR": str(home),
                "LOCALAPPDATA": str(Path(home) / "AppData" / "Local"), "XDG_CACHE_HOME": str(Path(home) / ".cache"),
                "TMP": str(tmp), "TEMP": str(tmp), "TMPDIR": str(tmp),
                "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"})
    if project is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project)
    if extra:
        env.update(extra)
    return env


def canon(path) -> str | None:
    """A comparable form of a path: real path, forward slashes, no trailing slash, lower case (Windows is case blind)."""
    if path is None:
        return None
    return os.path.realpath(str(path)).replace("\\", "/").rstrip("/").lower()


def own_root_cases(fn, base: Path) -> list:
    """The unit rows of ``_project_paths.worktree_own_root`` as ``[(name, ok, detail)]`` (the Own tree root row of the
    contract plus its Approval addendum, item 1). ``fn`` is the function, or None when it does not exist yet: then
    every row FAILS with a diagnostic, and the runner goes on. Shared by the guard suite and the path-guards suite."""
    base = Path(base)
    rows: list = []

    def row(name: str, ok: bool, detail: str = "") -> None:
        rows.append((name, bool(ok), detail))

    def call(name: str, path: Path):
        if fn is None:
            row(name, False, "_project_paths.worktree_own_root is not defined")
            return None
        try:
            return fn(str(path))
        except Exception as exc:  # noqa: BLE001 - a raising helper is a failing row, never a crash of the runner
            row(name, False, "worktree_own_root(%r) raised %r" % (str(path), exc))
            return None

    def shape(got) -> tuple:
        if isinstance(got, (tuple, list)) and len(got) == 2:
            return (canon(got[0]), canon(got[1]) if got[1] is not None else None)
        return ("<bad shape %r>" % (got,), None)

    # no .git anywhere up the path is a precondition of the (None, None) rows: say so loudly when it does not hold
    plain = base / "nogit" / "deep"
    plain.mkdir(parents=True, exist_ok=True)
    above = ancestors_holding(plain, ".git")
    if above:
        row("worktree_own_root precondition: no ancestor of the no-git fixture holds a .git entry", False,
            "ancestors holding .git: %s" % ", ".join(str(a) for a in above))

    main = make_main_checkout(base / "main-checkout")
    (main / "src" / "deeper").mkdir(parents=True, exist_ok=True)
    name = "worktree_own_root: a main checkout (.git FOLDER) returns (folder, None) from a sub folder"
    got = call(name, main / "src" / "deeper")
    if got is not None or fn is not None:
        row(name, shape(got) == (canon(main), None), "got %r, expected (%s, None)" % (got, main))
    name = "worktree_own_root: a path that does not exist yet walks from its nearest existing ancestor"
    got = call(name, main / "src" / "not" / "yet" / "File.cs")
    if got is not None or fn is not None:
        row(name, shape(got) == (canon(main), None), "got %r, expected (%s, None)" % (got, main))

    for layout in ("inside", "outside"):
        for form in ("absolute", "relative"):
            info = make_linked_worktree(base / ("lw-%s-%s" % (layout, form)), layout=layout, gitdir_form=form)
            sub = info["worktree"] / "src" / "sub"
            sub.mkdir(parents=True, exist_ok=True)
            name = "worktree_own_root: linked worktree (%s layout, %s gitdir) from a sub folder returns its OWN root" % (
                layout, form)
            got = call(name, sub)
            if got is not None or fn is not None:
                expected = (canon(info["worktree"]), canon(info["admin"]))
                row(name, shape(got) == expected, "got %r, expected %r" % (got, expected))
            name = "worktree_own_root: that gitdir comes back with forward slashes (%s layout, %s gitdir)" % (layout, form)
            got = call(name, sub)
            if got is not None and isinstance(got, (tuple, list)) and len(got) == 2:
                row(name, isinstance(got[1], str) and "\\" not in got[1], "gitdir element %r" % (got[1],))
            elif fn is not None:
                row(name, False, "unusable result %r" % (got,))

    name = "worktree_own_root: no .git entry anywhere up the path returns (None, None)"
    got = call(name, plain)
    if fn is not None and not above:
        row(name, got is not None and tuple(got) == (None, None), "got %r" % (got,))
    elif fn is None:
        pass

    # (the simulated UNC share / mapped drive helper `unc_share` lives at the end of this file)
    unreadable = base / "unreadable" / "deep"
    unreadable.mkdir(parents=True, exist_ok=True)
    (unreadable.parent / ".git").write_bytes(b"\xff\xfe\x00\xd8 not text, not utf-8 \x80\x81\n")
    name = "worktree_own_root: an unreadable .git file returns (None, None)"
    got = call(name, unreadable)
    if fn is not None:
        row(name, got is not None and tuple(got) == (None, None), "got %r" % (got,))

    nolines = base / "nogitdirline" / "deep"
    nolines.mkdir(parents=True, exist_ok=True)
    (nolines.parent / ".git").write_text("this file is readable but has no pointer line\n", encoding="utf-8")
    name = "worktree_own_root: a readable .git file with no gitdir: line returns (folder, None), an undecidable tree"
    got = call(name, nolines)
    if fn is not None:
        row(name, got is not None and shape(got) == (canon(nolines.parent), None), "got %r" % (got,))
    return rows


# --------------------------------------------------------------------------------------------------------------
# A simulated UNC share and mapped drive (issue #259, review round 3). Nothing here touches a network: every path
# of the form \\<host>\<share>\... (or its \\?\UNC\ form) is answered from a LOCAL folder, and a path that merely
# names the host but is not under the share is answered "nothing there" without a probe.
# --------------------------------------------------------------------------------------------------------------
def unc_share(share_root, host: str, share: str = "team", resolve_local: bool = False, others: tuple = ()):
    """Context manager. ``\\\\<host>\\<share>\\rest`` reads, stats and opens ``<share_root>\\rest``.

    ``resolve_local=True`` also simulates a MAPPED DRIVE: ``os.path.realpath`` of a local path under ``share_root``
    returns its ``\\\\<host>\\<share>\\...`` form (what CPython does on Windows for a mapped network drive).
    ``others``: lower-case substrings (other fake hosts) that are NEVER answered here: such a call falls through to
    whatever was patched before (the suite's watcher), so a probe of them stays visible. Windows only."""
    from contextlib import contextmanager

    @contextmanager
    def _cm():
        import builtins
        import ntpath
        from contextlib import ExitStack
        from unittest import mock

        root = os.path.abspath(str(share_root))
        unc_root = "\\\\%s\\%s" % (host, share)
        low = unc_root.lower()
        foreign = tuple(o.lower() for o in others)
        real_rp, real_isdir, real_isfile, real_exists, real_open = (
            os.path.realpath, os.path.isdir, os.path.isfile, os.path.exists, builtins.open)

        def text_of(p):
            try:
                t = os.fspath(p)
            except TypeError:
                return None
            if isinstance(t, bytes):
                return None
            t = t.replace("/", "\\")
            if t[:8].lower() == "\\\\?\\unc\\":
                t = "\\\\" + t[8:]
            return t

        def classify(p):
            """('local', path) under the share, ('quiet', None) names the host elsewhere, (None, None) not ours."""
            t = text_of(p)
            if t is None:
                return None, None
            tl = t.lower()
            if any(o in tl for o in foreign):
                return None, None
            if tl == low or tl.startswith(low + "\\"):
                return "local", root + t[len(unc_root):]
            if host.lower() in tl:
                return "quiet", None
            return None, None

        def realpath(p, *a, **k):
            kind, _loc = classify(p)
            if kind == "local":
                return ntpath.normpath(text_of(p))
            if kind == "quiet":
                return p
            real = real_rp(p, *a, **k)
            if resolve_local:
                r = os.path.normcase(real)
                rr = os.path.normcase(root)
                if r == rr or r.startswith(rr + "\\"):
                    return unc_root + real[len(root):]
            return real

        def answering(real_fn):
            def inner(p, *a, **k):
                kind, loc = classify(p)
                if kind == "local":
                    return real_fn(loc, *a, **k)
                if kind == "quiet":
                    return False
                return real_fn(p, *a, **k)
            return inner

        def opened(p, *a, **k):
            kind, loc = classify(p)
            if kind == "local":
                return real_open(loc, *a, **k)
            if kind == "quiet":
                raise OSError("simulated share: nothing at %s" % (p,))
            return real_open(p, *a, **k)

        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(os.path, "realpath", realpath))
            stack.enter_context(mock.patch.object(os.path, "isdir", answering(real_isdir)))
            stack.enter_context(mock.patch.object(os.path, "isfile", answering(real_isfile)))
            stack.enter_context(mock.patch.object(os.path, "exists", answering(real_exists)))
            stack.enter_context(mock.patch.object(builtins, "open", opened))
            yield

    return _cm()
