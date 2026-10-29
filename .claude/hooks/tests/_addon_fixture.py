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
