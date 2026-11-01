#!/usr/bin/env python3
"""
plugin_doctor.py — create what a consuming project is missing, and say what it cannot.

The plugin delivers skills, agents, hooks and scripts. It cannot deliver the files
that describe *your* repository, and it must never guess at them. This script closes
the gap it can close and names the rest.

Two rules govern everything here:

  1. **Never overwrite.** A file that exists is yours, whatever it contains.
  2. **Never invent an authored value.** A scaffold keeps the template's placeholders
     visible, so the machinery reads the slot as unfilled rather than as a wrong answer.
     A confidently wrong profile is worse than an obviously empty one.

Usage:
  py -3 .claude/scripts/plugin_doctor.py                 # report only
  py -3 .claude/scripts/plugin_doctor.py --fix           # create what is safe
  py -3 .claude/scripts/plugin_doctor.py --fix --json    # machine-readable
  py -3 .claude/scripts/plugin_doctor.py --drift         # compare this project with the installed plugin

--drift reads and never writes: see the section of this file that carries it.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import posixpath
import re
import shlex
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Requirement:
    """One thing a consuming project needs, and how it is satisfied.

    kind:
      ``dir``      — an empty directory; safe to create
      ``copy``     — copied verbatim from the plugin
      ``scaffold`` — written from a stub here, placeholders intact
      ``manual``   — only a human may create it; reported, never written
    """

    path: str
    kind: str
    why: str
    source: Optional[str] = None
    authored: bool = False


REQUIREMENTS: List[Requirement] = [
    Requirement(".claude/concepts", "dir", "where concept contracts live"),
    Requirement(".claude/work-items", "dir", "where work item briefs live"),
    Requirement(".claude/north-stars", "dir", "the direction register read at intake and design"),
    Requirement(".claude/orchestrator/results", "dir",
                "completion records, the durable evidence a sub-task finished"),
    Requirement(".claude/templates/concept-contract.md", "copy",
                "every contract is a copy of this",
                source=".claude/templates/concept-contract.md"),
    Requirement(".claude/registries/MECHANISMS.md", "copy",
                "reusable mechanisms; add your own project section below the Universal tier",
                source=".claude/registries/MECHANISMS.md"),
    Requirement(".claude/registries/VOCABULARY.md", "copy",
                "domain vocabulary; same two-tier shape",
                source=".claude/registries/VOCABULARY.md"),
    Requirement(".claude/registries/JOURNAL.md", "copy",
                "lessons the design agent and the critic read on every run",
                source=".claude/registries/JOURNAL.md"),
    Requirement(".claude/project-profile.md", "scaffold",
                "the only file you must author; the loop reads its implementers and review-gates slots; /auto-improve-finish-install fills the slots it can",
                source=".claude/project-profile.md", authored=True),
    Requirement(".claude/area-mapping.json", "scaffold",
                "maps changed paths to areas, for the contract-critic accuracy system",
                authored=True),
    Requirement(".claude/work-item-conventions.json", "scaffold",
                "issue and pull request title conventions, shared by /task and /ship",
                authored=True),
    Requirement(".claude/settings.json", "manual",
                "registering the hooks turns enforcement on; that is your decision, not this script's; /auto-improve-finish-install registers them once you agree"),
]

SCAFFOLDS: Dict[str, str] = {
    ".claude/area-mapping.json": json.dumps({
        "$comment": "Maps changed paths to named areas. Add one entry per area of your "
                    "repository. An empty map makes every contract derive 'uncategorized', "
                    "which is honest but costs you the accuracy system.",
        "areas": {}
    }, indent=2) + "\n",
    ".claude/work-item-conventions.json": json.dumps({
        "$comment": "Single source of truth for title conventions. Read by the intake and "
                    "ship skills. Duplicating these lists into a skill is how the two drift.",
        "issueTitle": {
            "format": "[<EFFORT>] <Title>",
            "pattern": "^\\[(FEATURE|BUG|IMPROVEMENT|REFACTOR|PERF|SECURITY|DOCS|CHORE|SPIKE)\\] .+",
            "exactlyOne": True,
            "effortTypes": [],
            "subIssue": {
                "$comment": "Sub-issue title format, read by compose_subissue_title.py. "
                            "The effort list and pattern stay in the outer issueTitle block.",
                "legend": "P = parent issue, ST = sub-task (its position in the parent's plan)",
                "format": "[<EFFORT>] P:#<parent> ST:<subtask> - <Title>"
            }
        },
        "prTitle": {"map": [], "order": []},
        "issueLink": {
            "closingKeyword": "Closes",
            "referenceKeyword": "Refs",
            "sameRepoFormat": "#<n>",
            "absentIdTokens": ["none"],
            "unresolvedIdTokens": ["unknown", "tbd"],
            "verdicts": [
                "unverifiable", "malformed-id", "unresolved-id", "not-applicable",
                "issue-unreachable", "issue-already-closed", "pr-not-open",
                "foreign-closing-ref", "unexpected-closing-ref", "exempt-partial",
                "deferred-close", "linked", "undeclared-target", "refs-without-partial",
                "absent-repairable", "still-absent",
                "offer-declined", "offer-unavailable", "offer-unrecorded"
            ],
            "requireRecordedOffer": False,
            "offerOutcomeField": "issue_offer",
            "offerOutcomes": ["pending", "opened", "declined", "unavailable"],
            "offerReasonField": "issue_offer_reason",
            "offerReasons": ["gh-missing", "gh-unauthenticated", "create-failed",
                             "no-problem-statement"],
            "maxRepairAttempts": 1
        }
    }, indent=2) + "\n",
}


def scaffold_for(path: str) -> Optional[str]:
    """The stub content for a scaffolded requirement, or None when it is copied."""
    if path in SCAFFOLDS:
        return SCAFFOLDS[path]
    if path == ".claude/project-profile.md":
        # Deliberately no content of our own: the plugin's template is the stub,
        # placeholders and all. Returning a marker keeps the contract that every
        # scaffold has something to write.
        return "<copied from the plugin template, placeholders intact>"
    return None


def _installed_plugin_root(project: Optional[Path] = None) -> Optional[Path]:
    """The plugin version this project runs, from the one resolver (``installed_plugin_root``).

    ``_claude_paths`` is imported here, not at the top, so a missing hooks folder next to a copy of
    this script gives "not found" instead of a crash at import time.
    """
    try:
        from _claude_paths import installed_plugin_root
    except ImportError:
        return None
    return installed_plugin_root(project)


def find_plugin_root(explicit: Optional[str] = None) -> Optional[Path]:
    """Where the plugin's own tree is, under either install mode.

    The same order the skills use: an explicit path, then the vendored copy, then
    the environment's plugin root, then the installed plugin root (the recorded
    install path, then the newest provider cache folder by version number).
    """
    if explicit:
        p = Path(explicit)
        return p if p.is_dir() else None
    here = Path(__file__).resolve().parent.parent.parent   # .../<root>
    candidates = [here]
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        candidates.append(Path(env))
    installed = _installed_plugin_root()
    if installed is not None:
        candidates.append(installed)
    for c in candidates:
        if (c / ".claude/templates/concept-contract.md").is_file():
            return c
    return None


def check(project_root: Path) -> List[Requirement]:
    """Every requirement this project has not satisfied yet."""
    missing = []
    for r in REQUIREMENTS:
        target = project_root / r.path
        if r.kind == "dir":
            if not target.is_dir():
                missing.append(r)
        elif not target.exists():
            missing.append(r)
    return missing


def apply_fixes(project_root: Path, missing: List[Requirement],
                plugin_root: Optional[Path]) -> Dict[str, Any]:
    """Create what is safe to create. Report the rest.

    Returns four lists: what was created, what still needs a human to author it,
    what could not be resolved, and what was deliberately left alone.
    """
    report: Dict[str, Any] = {"created": [], "needs_authoring": [],
                              "unresolved": [], "left_to_you": []}

    for r in missing:
        target = project_root / r.path

        if r.kind == "manual":
            report["left_to_you"].append(r.path)
            continue

        if target.exists():          # belt and braces: never overwrite
            continue

        if r.kind == "dir":
            target.mkdir(parents=True, exist_ok=True)
            report["created"].append(r.path)
            continue

        if r.kind == "copy" or r.path == ".claude/project-profile.md":
            src = (plugin_root / r.source) if (plugin_root and r.source) else None
            if not src or not src.is_file():
                report["unresolved"].append(
                    f"{r.path} (no source at {r.source or 'unknown'} in the plugin tree)")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
            report["created"].append(r.path)
            if r.authored:
                report["needs_authoring"].append(r.path)
            continue

        if r.kind == "scaffold":
            content = scaffold_for(r.path)
            if content is None:
                report["unresolved"].append(f"{r.path} (scaffolded but no stub defined)")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            report["created"].append(r.path)
            if r.authored:
                report["needs_authoring"].append(r.path)

    return report


# ===========================================================================
# --drift: does the project agree with the plugin it runs?
#
# Contract 2026-10-12-dedupe-claude-config, Commands "Check plugin drift" and the sections that
# follow it ("What the drift check compares", "compared"). A project that vendors files from the
# plugin must keep them equal, and a hook must not be registered by both sides (it would run
# twice). The check reads, never writes.
#
# Finding kinds (a closed set; at most one finding per kind and path):
#   content-differs          a file a vendored tree DECLARES, on both sides, whose text differs
#                            after line endings are folded and a byte order mark is dropped
#   one-sided                a file a declared list NAMES that exists on one side only
#   listed-twice             a file under a plugin-delivered root that both sides carry
#   registered-twice         an Effective hook registered by the project and by the plugin
#   unreadable-registration  a dispatcher's member list that cannot be read as a literal
#
# Add-on files (Revision 3): the sync config's ``addons`` object maps an add-on name to the add-on hook
# files this project carries in ``.claude/hooks/``. Each is compared with
# ``<plugin>/.claude/addons/<add-on>/hooks/<file>`` by the content-differs rule, and a listed file missing
# on either side is one-sided (owner: plugin). These files count in ``compared_addons``, never in
# ``compared``. A listed add-on whose plugin folder or addon.json is missing is exit 4. A project with no
# sync config is read by presence instead: an add-on counts as installed when any hook file its
# manifest names is in ``.claude/hooks/``. The helpers an installed add-on copied are compared with the
# plugin's default-tree copy only when no vendored tree already declares them.
#
# Exit codes: 0 only when the comparison ran and nothing counted; 1 for any counted finding;
# 4 when it could not compare. It never exits 0 when it could not compare.
# ===========================================================================

EXIT_FINDINGS = 1
EXIT_CANNOT_COMPARE = 4
FINDING_KINDS = ("content-differs", "one-sided", "listed-twice", "registered-twice",
                 "unreadable-registration", "disabled-hook-installed")
OWNER_PLUGIN = "plugin"
OWNER_REPO = "repo"
SYNC_CONFIG = ".claude/.sync-config.json"
#: The database guards the project registers on purpose; the plugin's copies defer to them.
DEFAULT_PROJECT_ENFORCED_HOOKS = ("db-destructive-guard.py", "db-research-readonly-guard.py")
#: The layout used when a project has no sync config: the plugin delivers agents and skills,
#: and hooks and scripts are compared for the files both sides carry.
DEFAULT_PLUGIN_DELIVERED = ({"path": ".claude/agents", "plugin_path": "agents"},
                            {"path": ".claude/skills", "plugin_path": "skills"})
DEFAULT_PRESENCE_TREES = (".claude/hooks", ".claude/scripts")
GATE_LAUNCHER = "gate-launch.py"
#: Where an add-on's documents land in the project. Equals ``auto_improve_finish_install.ADDON_DOCUMENTS_REL``
#: (a test checks it); the doctor does not import the installer.
ADDON_DOCUMENTS_REL = ".claude/references"
PROJECT_SETTINGS_LAYERS = ("settings.json", "settings.local.json")
SKIPPED_DIRS = frozenset({"__pycache__", ".git", "node_modules"})


class DriftError(Exception):
    """The comparison could not run. The message goes to the report's ``error`` field."""


@dataclass(frozen=True)
class DriftFinding:
    """One output line of the drift check."""

    kind: str
    path: str
    owner: str


def _rel(path: Any) -> str:
    """A path from a root, with forward slashes and no leading or trailing slash."""
    return str(path).replace("\\", "/").strip("/")


def _read_json(path: Path, what: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise DriftError("%s does not parse (%s): %s" % (what, path, exc))


def _folded_bytes(path: Path) -> bytes:
    """File content with a leading byte order mark dropped and CRLF turned into LF."""
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.replace(b"\r\n", b"\n")


def _string_list(value: Any) -> List[str]:
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def _root_pair(entry: Any) -> Optional[Tuple[str, str]]:
    """``(project path, plugin path)`` of a ``synced_trees`` or ``plugin_delivered`` entry."""
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
        return None
    plugin_path = entry.get("plugin_path")
    return _rel(entry["path"]), _rel(plugin_path if isinstance(plugin_path, str) else entry["path"])


class DriftConfig:
    """The project's sync config, read once. ``from_file`` is False for the default layout."""

    def __init__(self, data: Optional[dict]):
        self.from_file = data is not None
        data = data or {}
        raw_delivered = data.get("plugin_delivered") if self.from_file else list(DEFAULT_PLUGIN_DELIVERED)
        self.delivered: List[Tuple[str, str]] = [p for p in map(_root_pair, raw_delivered or []) if p]
        self.trees: List[dict] = []
        for entry in data.get("synced_trees") or []:
            pair = _root_pair(entry)
            if pair is None:
                continue
            self.trees.append({"name": entry.get("name") or pair[0], "path": pair[0], "plugin_path": pair[1],
                               "files": [_rel(f) for f in _string_list(entry.get("files"))],
                               "section_scoped": bool(entry.get("section_scoped"))})
        self.templated = {_rel(e["path"]) for e in data.get("templated_in_plugin") or []
                          if isinstance(e, dict) and isinstance(e.get("path"), str)}
        self.excluded: set = set()
        for entry in data.get("excluded") or []:
            if isinstance(entry, dict):
                for key in ("examples", "paths", "path"):
                    value = entry.get(key)
                    self.excluded.update(_rel(v) for v in ([value] if isinstance(value, str) else _string_list(value)))
        enforced = data.get("project_enforced_hooks") if "project_enforced_hooks" in data \
            else list(DEFAULT_PROJECT_ENFORCED_HOOKS)
        self.enforced = {h.casefold() for h in _string_list(enforced)}
        self.repo_owned = {_rel(p) for p in _string_list(data.get("repo_owned"))}
        raw_addons = data.get("addons")
        self.addons: Dict[str, List[str]] = {}
        if isinstance(raw_addons, dict):
            for addon_name, addon_files in raw_addons.items():
                self.addons[str(addon_name)] = _string_list(addon_files)

    def is_exempt(self, project_rel: str, tree_rel: str) -> bool:
        """Named by ``templated_in_plugin`` or by an ``excluded`` entry: never compared."""
        if project_rel in self.templated:
            return True
        return bool({project_rel, tree_rel, posixpath.basename(tree_rel)} & self.excluded)

    def owner_of(self, project_rel: str) -> str:
        return OWNER_REPO if project_rel in self.repo_owned else OWNER_PLUGIN


def load_drift_config(project: Path) -> DriftConfig:
    path = project / SYNC_CONFIG
    if not path.is_file():
        return DriftConfig(None)
    data = _read_json(path, "the sync config")
    if not isinstance(data, dict):
        raise DriftError("the sync config (%s) does not hold a JSON object" % path)
    return DriftConfig(data)


# ----------------------------------------------------------------------------- registrations
def _launch_tokens(entry: dict) -> List[str]:
    """The words a hook row launches: ``args`` (exec form) or the shell command split into tokens."""
    args = entry.get("args")
    if isinstance(args, list):
        return [a for a in args if isinstance(a, str)]
    command = entry.get("command")
    if not isinstance(command, str):
        return []
    try:
        tokens = shlex.split(command, posix=False)
    except ValueError:
        return []
    return [t.strip("\"'") for t in tokens[1:]]


def _launcher_row_parts(entry: dict) -> Optional[Tuple[str, str, List[str]]]:
    """``(class, script, extra arguments)`` when the row is a Project hook launcher row, else ``None``.
    The reader lives in ``_project_paths`` beside the launcher text it compares to; ``_claude_paths`` is
    imported here, not at the top, so a copy of this script without a hooks folder still loads."""
    try:
        from _claude_paths import project_hook_launcher_parts
    except ImportError:
        return None
    return project_hook_launcher_parts(entry)


def _launched_and_first_argument(entry: dict) -> Tuple[Optional[str], Optional[str]]:
    """The launched script file name and the argument that follows it. Exec form launches the first
    ``args`` element that does not start with ``-``; shell form the first token ending in ``.py``.
    A Project hook launcher row launches its script (the argument after the class), and the argument
    after that is the first extra, so a ``gate-launch.py`` launcher row is the gate it names."""
    launcher = _launcher_row_parts(entry)
    if launcher is not None:
        _hook_class, script, extras = launcher
        return script, (posixpath.basename(_rel(extras[0])) if extras else None)
    tokens = _launch_tokens(entry)
    isolated = isinstance(entry.get("args"), list)
    for index, token in enumerate(tokens):
        if (isolated and token and not token.startswith("-")) or (not isolated and token.lower().endswith(".py")):
            following = tokens[index + 1] if index + 1 < len(tokens) else None
            return posixpath.basename(_rel(token)), (posixpath.basename(_rel(following)) if following else None)
    return None, None


def _dispatcher_members(path: Path) -> Optional[List[str]]:
    """Members of the literal ``CHECKS`` list a hook module declares, read from its SOURCE (never
    imported). ``None`` when the module declares no ``CHECKS``; ``DriftError`` when it cannot be read."""
    try:
        source = path.read_text(encoding="utf-8-sig")
    except OSError:
        return None
    declares = re.search(r"^\s*CHECKS\s*[:=]", source, re.MULTILINE) is not None
    if not declares:
        return None
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        raise DriftError("cannot read the CHECKS list of %s" % path)
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == "CHECKS" for t in targets):
            value = getattr(node, "value", None)
            if isinstance(value, (ast.List, ast.Tuple)) and all(
                    isinstance(e, ast.Constant) and isinstance(e.value, str) for e in value.elts):
                return [e.value for e in value.elts]
            raise DriftError("the CHECKS list of %s is not a literal list of names" % path)
    return None


def _effective_hooks(bodies: List[dict], hooks_dir: Path) -> Tuple[set, List[str]]:
    """The Effective hooks of one side: ``(event, hook file)`` pairs, plus the registrations that
    could not be read. A ``gate-launch.py`` row is the gate it names; a dispatcher is each of its
    ``CHECKS`` members; any other row is the launched file."""
    found: set = set()
    unreadable: List[str] = []
    for body in bodies:
        hooks = body.get("hooks") if isinstance(body, dict) else None
        if not isinstance(hooks, dict):
            continue
        for event, groups in hooks.items():
            for group in groups if isinstance(groups, list) else []:
                entries = group.get("hooks") if isinstance(group, dict) else None
                for entry in entries if isinstance(entries, list) else []:
                    if not isinstance(entry, dict):
                        continue
                    launched, gate = _launched_and_first_argument(entry)
                    if launched is None:
                        continue
                    if launched == GATE_LAUNCHER:
                        if gate:
                            found.add((event, gate))
                        continue
                    try:
                        members = _dispatcher_members(hooks_dir / launched)
                    except DriftError:
                        unreadable.append("%s:%s" % (event, launched))
                        continue
                    for member in members if members is not None else [launched]:
                        found.add((event, member))
    return found, unreadable


# ----------------------------------------------------------------------------- the comparison
def _walk_files(base: Path) -> List[str]:
    """Every regular file under ``base`` as a path relative to it, forward slashes, sorted."""
    out: List[str] = []
    for current, dirs, files in os.walk(str(base)):
        dirs[:] = sorted(d for d in dirs if d not in SKIPPED_DIRS)
        for name in files:
            out.append(Path(current, name).relative_to(base).as_posix())
    return sorted(out)


def _plain_file_name(value: str) -> bool:
    return value not in ("", ".", "..") and "/" not in value and "\\" not in value


def _plugin_addon(plugin: Path, name: str) -> Dict[str, Any]:
    """The plugin's folder, hook file names and helper paths of one add-on. ``DriftError`` when the
    folder or its addon.json is missing or unreadable: a listed add-on that cannot be compared must
    never read as clean."""
    if not _plain_file_name(name):
        raise DriftError("'%s' is not an add-on name (the sync config's addons object)" % name)
    folder = plugin / ".claude" / "addons" / name
    if not folder.is_dir():
        raise DriftError("the plugin has no add-on folder '.claude/addons/%s'; the add-on '%s' cannot be compared"
                         % (name, name))
    manifest = folder / "addon.json"
    if not manifest.is_file():
        raise DriftError("the plugin's add-on '%s' has no addon.json (%s); it cannot be compared" % (name, manifest))
    data = _read_json(manifest, "the add-on manifest of '%s'" % name)
    if not isinstance(data, dict):
        raise DriftError("the add-on manifest of '%s' (%s) does not hold a JSON object" % (name, manifest))
    disabled: List[Tuple[str, List[str]]] = []
    for entry in data.get("disabled") or []:
        if isinstance(entry, dict) and isinstance(entry.get("hook"), str) and _plain_file_name(entry["hook"]):
            disabled.append((entry["hook"], [n for n in _string_list(entry.get("former_names"))
                                             if _plain_file_name(n)]))
    return {"folder": folder,
            "hooks": [h for h in _string_list(data.get("hooks")) if _plain_file_name(h)],
            "helpers": [_rel(h) for h in _string_list(data.get("helpers"))],
            "documents": [d for d in _string_list(data.get("documents")) if _plain_file_name(d)],
            "disabled": disabled}


def _all_plugin_addons(plugin: Path) -> List[Tuple[str, Dict[str, Any]]]:
    """Every add-on folder of the plugin that has a manifest, as ``(name, info)``, sorted by name."""
    base = plugin / ".claude" / "addons"
    names = sorted(p.name for p in base.iterdir() if p.is_dir() and (p / "addon.json").is_file()) \
        if base.is_dir() else []
    return [(name, _plugin_addon(plugin, name)) for name in names]


def _addon_jobs(config: DriftConfig, project: Path, plugin: Path) -> List[Tuple[str, List[str], Dict[str, Any]]]:
    """Which add-ons to compare, as ``(name, project file names, plugin info)``. With a sync config, the
    ones its ``addons`` object lists; without one, the ones installed by presence."""
    jobs: List[Tuple[str, List[str], Dict[str, Any]]] = []
    if config.from_file:
        for name, files in sorted(config.addons.items()):
            if not all(_plain_file_name(f) for f in files):
                raise DriftError("the sync config lists a file for the add-on '%s' that is not a plain file name" % name)
            jobs.append((name, files, _plugin_addon(plugin, name)))
        return jobs
    base = plugin / ".claude" / "addons"
    folders = sorted(p.name for p in base.iterdir() if p.is_dir()) if base.is_dir() else []
    for name in folders:
        info = _plugin_addon(plugin, name)
        if any((project / ".claude" / "hooks" / h).is_file() for h in info["hooks"]):
            jobs.append((name, info["hooks"], info))
    return jobs


def compute_drift(project: Path, plugin: Path) -> Dict[str, Any]:
    """Compare ``project`` with ``plugin``. Returns ``{"findings", "compared", "compared_addons"}``
    (findings as ``DriftFinding`` objects). Raises ``DriftError`` when it cannot compare, and that
    includes any ``OSError`` while reading: an unreadable file is a failed comparison, not a crash."""
    try:
        return _compute_drift(project, plugin)
    except OSError as exc:
        raise DriftError("a file or folder could not be read (%s)" % exc)


def _compute_drift(project: Path, plugin: Path) -> Dict[str, Any]:
    if os.path.normcase(os.path.realpath(project)) == os.path.normcase(os.path.realpath(plugin)):
        raise DriftError("the plugin root is the project root (%s); comparing a tree with itself "
                         "would always look clean" % project)
    config = load_drift_config(project)

    settings_bodies: List[dict] = []
    settings_layers: List[Tuple[str, dict]] = []
    for name in PROJECT_SETTINGS_LAYERS:
        path = project / ".claude" / name
        if path.is_file():
            body = _read_json(path, "the project's " + name)
            settings_bodies.append(body if isinstance(body, dict) else {})
            settings_layers.append((name, body if isinstance(body, dict) else {}))
    plugin_hooks_json = plugin / ".claude" / "hooks" / "hooks.json"
    plugin_bodies: List[dict] = []
    if plugin_hooks_json.is_file():
        body = _read_json(plugin_hooks_json, "the plugin's hooks.json")
        plugin_bodies.append(body if isinstance(body, dict) else {})

    delivered_pairs = set(config.delivered)
    trees = list(config.trees)
    if not config.from_file:
        for rel in DEFAULT_PRESENCE_TREES:
            plugin_dir, project_dir_ = plugin / rel, project / rel
            files = [n for n in sorted(os.listdir(plugin_dir))
                     if (plugin_dir / n).is_file() and (project_dir_ / n).is_file()] if plugin_dir.is_dir() else []
            trees.append({"name": rel, "path": rel, "plugin_path": rel, "files": files, "section_scoped": False})

    # A missing plugin-side folder of ANY root pair is an environment error, not a pile of
    # one-sided files; an empty folder is not missing.
    for project_path, plugin_path in [(t["path"], t["plugin_path"]) for t in trees] + list(config.delivered):
        if not (plugin / plugin_path).is_dir():
            raise DriftError("the plugin has no folder '%s' (root pair %s <-> %s); nothing under it "
                             "can be compared" % (plugin_path, project_path, plugin_path))

    addon_jobs = _addon_jobs(config, project, plugin)

    found: Dict[Tuple[str, str], DriftFinding] = {}

    def add(kind: str, path: str, owner: Optional[str] = None) -> None:
        found.setdefault((kind, path), DriftFinding(kind, path, owner or config.owner_of(path)))

    compared = 0
    declared: List[Tuple[str, str]] = []   # (project-relative path, plugin-relative path) named by a list
    for tree in trees:
        pair = (tree["path"], tree["plugin_path"])
        if tree["section_scoped"]:
            continue
        for name in tree["files"]:
            project_rel, plugin_rel = "%s/%s" % (tree["path"], name), "%s/%s" % (tree["plugin_path"], name)
            if pair in delivered_pairs:
                # Still declared although the plugin delivers the pair: only the skill-subfolder
                # case below applies, and it needs a nested file name.
                if "/" in name and (project / project_rel).is_file() and not (plugin / plugin_rel).is_file() \
                        and (plugin / plugin_rel).parent.is_dir() and not config.is_exempt(project_rel, name):
                    add("one-sided", project_rel)
                continue
            declared.append((project_rel, plugin_rel))
            if config.is_exempt(project_rel, name):
                continue
            here, there = project / project_rel, plugin / plugin_rel
            if here.is_file() and there.is_file():
                compared += 1
                if _folded_bytes(here) != _folded_bytes(there):
                    add("content-differs", project_rel)
            elif here.is_file() != there.is_file():
                add("one-sided", project_rel)

    # repo_owned names files the repository keeps whatever the plugin says: a one-sided one is still a finding.
    for owned in sorted(config.repo_owned):
        for tree in trees:
            prefix = tree["path"] + "/"
            if owned.startswith(prefix) and not tree["section_scoped"] \
                    and (tree["path"], tree["plugin_path"]) not in delivered_pairs:
                plugin_rel = "%s/%s" % (tree["plugin_path"], owned[len(prefix):])
                here, there = project / owned, plugin / plugin_rel
                if here.is_file() != there.is_file() and not config.is_exempt(owned, owned[len(prefix):]):
                    add("one-sided", owned)
                break

    # listed-twice: any file under a plugin-delivered root that both sides carry, identical or not.
    for project_path, plugin_path in config.delivered:
        base = project / project_path
        if not base.is_dir():
            continue
        for rel in _walk_files(base):
            project_rel = "%s/%s" % (project_path, rel)
            if (plugin / plugin_path / rel).is_file() and project_rel not in config.templated:
                add("listed-twice", project_rel)

    # registered-twice: an Effective hook that both sides register, apart from the project-enforced ones.
    project_hooks, project_unreadable = _effective_hooks(settings_bodies, project / ".claude" / "hooks")
    plugin_hooks, plugin_unreadable = _effective_hooks(plugin_bodies, plugin / ".claude" / "hooks")
    for event, hook in sorted(project_hooks & plugin_hooks):
        if hook.casefold() not in config.enforced:
            add("registered-twice", "%s:%s" % (event, hook), OWNER_PLUGIN)
    for label in project_unreadable + plugin_unreadable:
        add("unreadable-registration", label, OWNER_PLUGIN)

    compared_addons = 0
    vendored_declared = {project_rel for project_rel, _plugin_rel in declared}
    helpers_seen: set = set()
    for name, files, info in addon_jobs:
        for file_name in files:
            project_rel = ".claude/hooks/" + file_name
            here, there = project / project_rel, info["folder"] / "hooks" / file_name
            if here.is_file() and there.is_file():
                compared_addons += 1
                if _folded_bytes(here) != _folded_bytes(there):
                    add("content-differs", project_rel)
            elif here.is_file() != there.is_file():
                add("one-sided", project_rel)
        # The helpers the install copied: compared only when no vendored tree already declares them.
        for helper in info["helpers"]:
            if helper in vendored_declared or helper in helpers_seen:
                continue
            here, there = project / helper, plugin / helper
            if here.is_file() and there.is_file():
                helpers_seen.add(helper)
                compared_addons += 1
                if _folded_bytes(here) != _folded_bytes(there):
                    add("content-differs", helper)

    # D-3: a disabled add-on hook that is still installed, for every add-on the plugin ships.
    plugin_addons = _all_plugin_addons(plugin)
    hooks_dir = project / ".claude" / "hooks"
    for _addon_name, info in plugin_addons:
        names = {n.casefold() for hook, former in info["disabled"] for n in [hook] + former}
        if not names:
            continue
        if hooks_dir.is_dir():
            for candidate in sorted(os.listdir(hooks_dir)):
                if candidate.casefold() in names and (hooks_dir / candidate).is_file():
                    add("disabled-hook-installed", ".claude/hooks/" + candidate, OWNER_PLUGIN)
        for layer, body in settings_layers:   # one layer at a time, so the finding names its layer
            rows, _unreadable = _effective_hooks([body], hooks_dir)
            for event, hook in sorted(rows):
                if hook.casefold() in names:
                    add("disabled-hook-installed", "%s:%s:%s" % (layer, event, hook), OWNER_PLUGIN)

    # D-4: add-on documents, compared when the config lists the add-on or any document is in the project.
    for name, info in plugin_addons:
        if not info["documents"]:
            continue
        project_docs = {d: project / ADDON_DOCUMENTS_REL / name / d for d in info["documents"]}
        if not (config.from_file and name in config.addons) and not any(p.is_file() for p in project_docs.values()):
            continue
        for doc, here in project_docs.items():
            project_rel = "%s/%s/%s" % (ADDON_DOCUMENTS_REL, name, doc)
            there = info["folder"] / "documents" / doc
            if here.is_file() and there.is_file():
                compared_addons += 1
                if _folded_bytes(here) != _folded_bytes(there):
                    add("content-differs", project_rel, OWNER_PLUGIN)
            elif here.is_file() != there.is_file():
                add("one-sided", project_rel, OWNER_PLUGIN)

    if compared == 0:
        raise DriftError("the comparison covered zero file pairs; a run that compared nothing "
                         "must not read as clean")
    findings = sorted(found.values(), key=lambda f: (f.kind, f.path))
    return {"findings": findings, "compared": compared, "compared_addons": compared_addons}


def drift_report(result: Dict[str, Any], error: Optional[str] = None) -> Dict[str, Any]:
    """The ``--json`` document: ``findings``, ``compared``, ``compared_addons`` (plus ``error`` on a failed run)."""
    report: Dict[str, Any] = {
        "findings": [{"kind": f.kind, "path": f.path, "owner": f.owner} for f in result["findings"]],
        "compared": result["compared"],
        "compared_addons": result["compared_addons"],
    }
    if error is not None:
        report["error"] = error
    return report


def run_drift(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    result: Dict[str, Any] = {"findings": [], "compared": 0, "compared_addons": 0}
    plugin: Optional[Path] = None
    try:
        if args.plugin:
            plugin = find_plugin_root(args.plugin)
        else:
            # Not find_plugin_root(): this checkout's own tree is a plugin only by accident here.
            plugin = _installed_plugin_root(project)
        if plugin is None:
            raise DriftError("no plugin found; pass --plugin or install the plugin")
        result = compute_drift(project, plugin)
    except DriftError as exc:
        report = drift_report({"findings": [], "compared": 0, "compared_addons": 0}, str(exc))
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print("project: %s" % project)
            print("plugin:  %s" % (plugin or "NOT FOUND"))
            print("  cannot compare: %s" % exc)
        return EXIT_CANNOT_COMPARE

    findings: List[DriftFinding] = result["findings"]
    counted = [f for f in findings if not (args.ignore_repo_owned and f.owner == OWNER_REPO)]
    if args.json:
        print(json.dumps(drift_report(result), indent=2))
    else:
        print("project: %s" % project)
        print("plugin:  %s" % plugin)
        for f in findings:
            reported = args.ignore_repo_owned and f.owner == OWNER_REPO
            print("  %s%-24s %s  [owner: %s]" % ("reported  " if reported else "", f.kind, f.path, f.owner))
        print("compared %d file pair(s) and %d add-on file(s); %d finding(s), %d counted"
              % (result["compared"], result["compared_addons"], len(findings), len(counted)))
    return EXIT_FINDINGS if counted else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Create what this project is missing for the plugin.")
    ap.add_argument("--fix", action="store_true", help="create what is safe; without it, report only")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--project", default=".", help="the project root (default: here)")
    ap.add_argument("--plugin", default=None, help="the plugin root, if it cannot be found")
    ap.add_argument("--drift", action="store_true",
                    help="compare the project with the installed plugin and print the drift findings (read only)")
    ap.add_argument("--ignore-repo-owned", action="store_true",
                    help="with --drift: a finding on a repo-owned file is printed as 'reported' and does not count")
    args = ap.parse_args()

    if args.drift:
        return run_drift(args)

    project = Path(args.project).resolve()
    plugin = find_plugin_root(args.plugin)
    missing = check(project)

    if not args.fix:
        out = {"project": str(project), "plugin_root": str(plugin) if plugin else None,
               "missing": [{"path": r.path, "kind": r.kind, "why": r.why} for r in missing]}
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(f"project: {project}")
            print(f"plugin:  {plugin or 'NOT FOUND - pass --plugin'}")
            if not missing:
                print("  nothing missing")
            for r in missing:
                print(f"  missing  {r.path:<44} [{r.kind}] {r.why}")
            print("\nrun again with --fix to create what is safe")
        return 0

    report = apply_fixes(project, missing, plugin)
    report["project"] = str(project)
    report["plugin_root"] = str(plugin) if plugin else None

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for p in report["created"]:
            print(f"  created        {p}")
        for p in report["needs_authoring"]:
            print(f"  NEEDS YOU      {p}  - it describes your repository; nothing can guess it")
        for p in report["left_to_you"]:
            print(f"  left alone     {p}  - writing it would change behaviour without asking; run /auto-improve-finish-install to register the hooks")
        for p in report["unresolved"]:
            print(f"  UNRESOLVED     {p}")
        if not any(report[k] for k in ("created", "needs_authoring", "left_to_you", "unresolved")):
            print("  nothing to do")
    return 0


if __name__ == "__main__":
    sys.exit(main())
