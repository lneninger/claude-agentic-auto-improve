#!/usr/bin/env python3
"""
auto_improve_finish_install.py — finish Quick start steps 4 and 5 of a consuming project.

Step 4 proposes and writes the project profile. Step 5 works out how the plugin reached
the project, then checks (plugin install) or merges (vendored copy) the hook registrations.

Two rules govern everything here:

  1. **Never overwrite an authored value.** Only a placeholder slot is ever written; a slot
     the team wrote is kept byte for byte.
  2. **Never change a file the operator was not shown.** Every write follows a preview, a
     SHA-256 of the previewed bytes, (for settings.json) a timestamped backup and an atomic
     replace. When nothing changes, nothing is written.

Every public function returns a dict. A refusal is a dict too, never an exception:
``{"status": "refused", "code": <REFUSAL_CODES>, "message": ..., "path": ...}``, and it always
means nothing was changed.

Usage:
  py -3 .claude/scripts/auto_improve_finish_install.py profile --project . [--json]
  py -3 .claude/scripts/auto_improve_finish_install.py profile --project . --apply \\
      --expect-sha256 <hash> --set slot=value[,value]
  py -3 .claude/scripts/auto_improve_finish_install.py hooks --project . [--json]
  py -3 .claude/scripts/auto_improve_finish_install.py hooks --project . --apply \\
      --expect-sha256 <hash> [--skip <hook>]
  py -3 .claude/scripts/auto_improve_finish_install.py addon --name <add-on> --project . [--json]
  py -3 .claude/scripts/auto_improve_finish_install.py addon --name <add-on> --project . --apply \\
      --expect-sha256 <plan hash>

The ``addon`` subcommand installs one opt-in add-on (a folder under ``.claude/addons/`` in the plugin)
into the project: it copies the add-on's hook files and the helper files its ``addon.json`` names, and
writes the manifest's registration rows into the project's settings.json in exec form, through the same
preview, plan hash, backup and atomic writer as ``hooks``. It never removes a row or a file and never
overwrites a file that differs.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

# A plan must leave a vendored consumer's tree byte-identical, and importing the sibling
# modules below would otherwise write __pycache__ beside this script.
sys.dont_write_bytecode = True
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from pr_merged import DEFAULT_IMPLEMENTERS, DEFAULT_REVIEW_GATES, load_slot  # noqa: E402
from plugin_doctor import find_plugin_root  # noqa: E402

Result = Dict[str, Any]

# --- Exit codes -----------------------------------------------------------------------

EXIT_OK: int = 0
EXIT_REFUSED: int = 2
EXIT_ENVIRONMENT: int = 3

# --- Closed set of refusal codes (contract: Data Shapes) --------------------------------

REFUSAL_CODES: Tuple[str, ...] = (
    "project-unreadable",
    "template-missing",
    "hooks-json-missing",
    "hook-file-missing",
    "interpreter-not-found",
    "malformed-settings",
    "unexpected-settings-shape",
    "install-mode-both",
    "install-mode-none",
    "install-record-unreadable",
    "plugin-source-checkout",
    "plugin-disabled",
    "provider-has-no-hooks",
    "unknown-slot",
    "slot-unanswered",
    "slot-already-authored",
    "invalid-slot-value",
    "unknown-agent",
    "changed-since-preview",
    "write-failed",
    "plugin-install-needs-no-registration",
    "addon-unknown",
    "addon-manifest-missing",
    "codegraph-mcp-not-configured",
    "addon-file-differs",
)

_ENVIRONMENT_CODES = ("project-unreadable", "template-missing", "hooks-json-missing",
                      "addon-manifest-missing")

# Refusal code -> process exit code (3 environment problem, 2 operator-correctable).
EXIT_CLASS: Dict[str, int] = {
    code: (EXIT_ENVIRONMENT if code in _ENVIRONMENT_CODES else EXIT_REFUSED)
    for code in REFUSAL_CODES
}

INSTALL_MODES: Tuple[str, ...] = ("plugin", "vendored", "both", "none", "plugin-source")
PROVIDERS: Tuple[str, ...] = ("claude", "cursor", "codex")

PLUGIN_NAME = "agentic-auto-improve"
RECORD_VERSION = 2
MAX_DEPTH = 6
PROFILE_REL = ".claude/project-profile.md"
EXCLUDED_DIRS = frozenset({".git", ".claude", "node_modules", "bin", "obj", "dist", "build",
                           "vendor", "venv", ".venv", "__pycache__"})
SOURCE_EXTENSIONS = frozenset({".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cs", ".go", ".java",
                               ".kt", ".rs", ".rb", ".php", ".swift", ".c", ".cpp", ".h", ".scala",
                               ".vue", ".svelte"})
TEST_CSPROJ_SUFFIXES = ("tests.csproj", ".test.csproj")
TEST_FOLDER_NAMES = frozenset({"tests", "test", "__tests__", "spec"})
AUTH_FOLDER_NAMES = frozenset({"Auth", "auth", "Authentication", "Identity"})
BUNDLER_CONFIGS = ("vite.config.", "next.config.", "nuxt.config.", "svelte.config.")
MIGRATION_SUFFIXES = ("alembic/versions", "prisma/migrations", "db/migrate",
                      "src/main/resources/db/migration")
REVIEW_DOCUMENTS = frozenset({"CLAUDE.md", "AGENTS.md", "CONTRIBUTING.md", "ARCHITECTURE.md"})
ROLE_SLOTS = {"implementers": DEFAULT_IMPLEMENTERS, "review-gates": DEFAULT_REVIEW_GATES}
TEMPLATE_DATABASES = frozenset({"AcmeApp", "AcmeApp_Testing"})

PROVENANCE_LINE = ("Filled in by `/auto-improve-finish-install` from this repository's own files; "
                   "every value was confirmed by the operator, and a slot the team wrote by hand "
                   "was left as written.")

NOT_VERIFIABLE: Tuple[str, ...] = (
    "That the running session loaded the hooks (a session started before the install or the "
    "enable runs without them).",
    "That a project-scope trust prompt was accepted.",
    "That a hook's imports of its sibling helpers succeed at run time.",
)

CODE_SEARCH_NOTE = (
    "The code-search-first guard is the codegraph add-on, and it is off by default: the plugin does "
    "not block a source Read, Grep or Glob. To turn it on, run /auto-improve-codegraph-install, which "
    "first checks that the CodeGraph MCP server is configured."
)

ADDONS_REL = ".claude/addons"
ADDON_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
ADDON_HELPER_ROOTS = (".claude/hooks/", ".claude/scripts/")
ADDON_ROW_KEYS = ("async", "statusMessage")
NEW_SESSION_NOTE = (
    "Claude Code reads the hook rows once, when a session starts. Start a new session for the "
    "installed add-on to take effect.")

PLATFORM_NOTE = (
    "On macOS and Linux the plugin's cached hooks.json launches 'py -3', which does not exist "
    "there, so no hook can start. This command cannot fix a plugin install: an edit to the cache "
    "is lost at the next update. Copy the hooks into the project instead (a vendored copy, which "
    "this command then registers with python3), or wait for a per-platform hooks format."
)

NOT_READ_NOTE = (
    "Enabled means switched on in the user, project or local settings that were read; a missing "
    "entry counts as not enabled. Managed settings and a --settings file are not read, so a "
    "plugin switched on only there is not seen.")

_ENV_READ = re.compile(
    r"""(?:environ\.get\(\s*|environ\[\s*|getenv\(\s*)["'](CLAUDE_[A-Z0-9_]+)["']""")
_ENV_EXCLUDED = frozenset({"CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT"})
_ROW = re.compile(r"^\|\s*`?([A-Za-z][\w.\-]*)`?\s*\|(.*?)\|\s*$")
_SEPARATOR_ROW = re.compile(r"^\|[\s:|\-]+\|\s*$")
_TOKEN = re.compile(r'"([^"]*)"|\'([^\']*)\'|(\S+)')
_PROJECT_HOOK_DIRS = ("${CLAUDE_PROJECT_DIR}/.claude/hooks", "$CLAUDE_PROJECT_DIR/.claude/hooks",
                      "%CLAUDE_PROJECT_DIR%/.claude/hooks", ".claude/hooks", "./.claude/hooks")


# =======================================================================================
# Shared helpers
# =======================================================================================

def refusal(code: str, message: str, path: Any) -> Result:
    """Build a Refusal: the code, a message naming the reason, and the path concerned."""
    return {"status": "refused", "code": code, "message": message, "path": str(path)}


def _is_refusal(result: Any) -> bool:
    return isinstance(result, dict) and result.get("status") == "refused"


def _fact(name: str, observed: Any, path: Any) -> Dict[str, Any]:
    return {"name": name, "observed": observed, "path": str(path)}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _plan_digest(*parts: bytes) -> str:
    """SHA-256 over the parts, each length-prefixed so neighbouring parts cannot run together."""
    digest = hashlib.sha256()
    for part in parts:
        digest.update(len(part).to_bytes(8, "big"))
        digest.update(part)
    return digest.hexdigest()


def _norm(path: Any) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _same_dir(a: Path, b: Path) -> bool:
    try:
        return _norm(a.resolve()) == _norm(b.resolve())
    except OSError:
        return _norm(a) == _norm(b)


def _is_within(child: Path, parent: Path) -> bool:
    try:
        Path(child).resolve().relative_to(Path(parent).resolve())
        return True
    except (ValueError, OSError):
        return False


def _load_json_lenient(path: Path) -> Any:
    """Parse a JSON file, tolerating a byte order mark; None when absent or unreadable."""
    try:
        return json.loads(path.read_bytes().decode("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _claude_home(claude_home: Optional[Path]) -> Path:
    """The Claude home: the argument, else CLAUDE_CONFIG_DIR, else ~/.claude."""
    if claude_home:
        return Path(claude_home)
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        return Path(env)
    return Path(os.path.expanduser("~")) / ".claude"


def _check_project(project: Path) -> Optional[Result]:
    if not project.is_dir():
        return refusal("project-unreadable", "the project is not a readable directory", project)
    try:
        os.listdir(project)
    except OSError as exc:
        return refusal("project-unreadable", "the project cannot be listed: %s" % exc, project)
    return None


def _manifest_names_plugin(root: Path) -> bool:
    data = _load_json_lenient(root / ".claude-plugin" / "plugin.json")
    return isinstance(data, dict) and data.get("name") == PLUGIN_NAME


def _version_key(path: Path) -> Tuple[Tuple[int, ...], str]:
    return tuple(int(n) for n in re.findall(r"\d+", path.name)), path.name


def _cache_roots(home: Optional[Path]) -> List[Path]:
    """Plugin copies in the provider cache of THE Claude home (the argument, CLAUDE_CONFIG_DIR,
    else ~/.claude), newest version first. No other home is searched."""
    found = [p for p in _claude_home(home).glob("plugins/cache/*/%s/*" % PLUGIN_NAME) if p.is_dir()]
    return sorted(found, key=_version_key, reverse=True)


def _separate_plugin_root(project: Path, plugin_root: Optional[Path], home: Optional[Path] = None,
                          needs: Optional[Callable[[Path], bool]] = None) -> Optional[Path]:
    """The plugin tree to read from; never the project itself.

    ``plugin_root`` is a hard override. Without it the candidates are tried in order:
    CLAUDE_PLUGIN_ROOT (Claude Code sets it for the install that is running), the copy this
    script lives in, then the provider cache under the Claude home (newest version first).
    A candidate equal to the project is rejected, and with ``needs`` the first candidate that
    really carries the needed file wins, so a vendored project (whose own tree has no
    template and no hooks.json) goes on to the next candidate. When none carries it, the first
    admissible candidate is returned so the plugin's agents can still be found. Every
    candidate, the override included, must be THIS plugin: ``.claude-plugin/plugin.json`` with
    ``name`` equal to PLUGIN_NAME; another plugin's tree or one with no manifest is skipped.
    """
    if plugin_root is not None:
        override = find_plugin_root(str(plugin_root))
        if override is None or _same_dir(override, project) or not _manifest_names_plugin(override):
            return None
        return override
    candidates: List[Path] = []
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        candidates.append(Path(env))
    candidates.append(Path(_SCRIPTS_DIR).parent.parent)
    candidates += _cache_roots(home)
    admissible = [c for c in candidates
                  if c.is_dir() and not _same_dir(c, project) and _manifest_names_plugin(c)]
    for candidate in admissible:
        if needs is None or needs(candidate):
            return candidate
    return admissible[0] if admissible else None


def _atomic_write(target: Path, data: bytes) -> Optional[str]:
    """Write via a temporary file and os.replace; return an error text, or None on success."""
    tmp = target.with_name("." + target.name + ".tmp-%d" % os.getpid())
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "wb") as handle:
            handle.write(data)
        os.replace(tmp, target)
    except OSError as exc:
        try:
            tmp.unlink()
        except OSError:
            pass
        return str(exc)
    return None


# =======================================================================================
# Step 4: the project profile
# =======================================================================================

def _table_bounds(lines: List[str]) -> Tuple[int, int]:
    for i, line in enumerate(lines):
        if re.match(r"^##\s+Slots\s*$", line.rstrip("\r")):
            end = next((j for j in range(i + 1, len(lines)) if lines[j].startswith("#")), len(lines))
            return i + 1, end
    return 0, len(lines)


def _slot_rows(lines: List[str]) -> List[Tuple[int, str, str]]:
    """(line index, slot, raw value) for every slot-table row, skipping the header and fences."""
    start, end = _table_bounds(lines)
    rows: List[Tuple[int, str, str]] = []
    in_fence = False
    for i in range(start, end):
        line = lines[i].rstrip("\r")
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        match = None if in_fence else _ROW.match(line)
        if not match:
            continue
        following = lines[i + 1].rstrip("\r") if i + 1 < len(lines) else ""
        if _SEPARATOR_ROW.match(following):
            continue  # the "| Slot | Value |" header row
        rows.append((i, match.group(1), match.group(2).strip()))
    return rows


def _is_placeholder(raw: str) -> bool:
    return raw.startswith("*(") or raw == ""


def _format_value(entries: Sequence[str]) -> str:
    return ", ".join("`%s`" % e for e in entries) if entries else "none"


def _parse_set_value(raw: str) -> List[str]:
    parts = [p.strip().strip("`").strip() for p in raw.split(",")]
    return [p for p in parts if p and p.lower() != "none"]


@dataclass
class _ProfileCtx:
    """Everything the profile commands read before deciding anything."""

    project: Path
    target: Path
    existed: bool
    source_sha: str
    old_text: str          # the profile text the preview read ("" when absent)
    base_text: str         # the text fills are applied to (the template when absent)
    template_slots: List[str]
    detection: str         # "available" | "unavailable"
    plugin_root: Optional[Path]
    rows: Dict[str, Tuple[int, str]] = field(default_factory=dict)

    def kind(self, slot: str) -> str:
        """placeholder | authored | missing."""
        row = self.rows.get(slot)
        if row is None:
            return "missing"
        return "placeholder" if _is_placeholder(row[1]) else "authored"


def _load_profile_ctx(project: Path, plugin_root: Optional[Path],
                      home: Optional[Path] = None) -> Tuple[Optional[Result], Optional[_ProfileCtx]]:
    bad = _check_project(project)
    if bad:
        return bad, None
    if _manifest_names_plugin(project):
        return refusal("plugin-source-checkout",
                       "this project is the plugin's own checkout; filling its profile would "
                       "overwrite the shipped template", project / ".claude-plugin" / "plugin.json"), None
    root = _separate_plugin_root(project, plugin_root, home, lambda r: (r / PROFILE_REL).is_file())
    target = project / PROFILE_REL
    existed = target.is_file()
    old_bytes = b""
    old_text = ""
    if target.exists() and not existed:
        return refusal("project-unreadable", "the profile path is not a file", target), None
    if existed:
        try:
            old_bytes = target.read_bytes()
            old_text = old_bytes.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return refusal("project-unreadable", "the profile cannot be read as UTF-8: %s" % exc, target), None
    template_text: Optional[str] = None
    if root is not None and (root / PROFILE_REL).is_file():
        try:
            template_text = (root / PROFILE_REL).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return refusal("template-missing", "the plugin template cannot be read: %s" % exc,
                           root / PROFILE_REL), None
    if template_text is None and not existed:
        return refusal("template-missing",
                       "no plugin template and no project profile were found", target), None
    base_text = old_text if existed else (template_text or "")
    rows = {slot: (i, raw) for i, slot, raw in _slot_rows(base_text.split("\n"))}
    if template_text is not None:
        slots = [s for _i, s, _r in _slot_rows(template_text.split("\n"))]
        detection = "available"
    else:
        slots = list(rows)
        detection = "unavailable"
    ctx = _ProfileCtx(project=project, target=target, existed=existed,
                      source_sha=_sha256(old_bytes) if existed else "absent",
                      old_text=old_text, base_text=base_text, template_slots=slots,
                      detection=detection, plugin_root=root, rows=rows)
    return None, ctx


def _apply_fills(ctx: _ProfileCtx, fills: Dict[str, List[str]]) -> str:
    """The profile text with the given slots filled; authored rows are never touched."""
    lines = ctx.base_text.split("\n")
    eol = "\r" if "\r\n" in ctx.base_text else ""
    rows = _slot_rows(lines)
    by_slot = {slot: i for i, slot, _raw in rows}
    last_row = max((i for i, _s, _r in rows), default=None)
    new_rows: List[str] = []
    for slot in ctx.template_slots:
        if slot not in fills:
            continue
        text = "| `%s` | %s |%s" % (slot, _format_value(fills[slot]), eol)
        if slot in by_slot:
            lines[by_slot[slot]] = text
        else:
            new_rows.append(text)
    if new_rows:
        if last_row is None:
            header = ["", "## Slots", "", "| Slot | Value |", "|---|---|"]
            lines += [h + eol for h in header] + new_rows
        else:
            lines[last_row + 1:last_row + 1] = new_rows
    for i, line in enumerate(lines):
        if line.lstrip().startswith("**TEMPLATE.**"):
            j = i
            while j < len(lines) and lines[j].strip() != "":
                j += 1
            lines[i:j] = [PROVENANCE_LINE + eol]
            break
    return "\n".join(lines)


# --- Inference -------------------------------------------------------------------------

def _join(rel: str, name: str) -> str:
    return rel + "/" + name if rel else name


def _evidence(path: str, reason: str) -> Dict[str, str]:
    return {"path": path, "reason": reason}


def _scan(project: Path) -> Dict[str, Tuple[List[str], List[str]]]:
    """Folder index {relative posix path: (sub-folders, files)}, depth-limited and sorted."""
    base = str(project)
    index: Dict[str, Tuple[List[str], List[str]]] = {}
    for dirpath, dirnames, filenames in os.walk(base):
        rel = os.path.relpath(dirpath, base).replace(os.sep, "/")
        rel = "" if rel == "." else rel
        depth = rel.count("/") + 1 if rel else 0
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS and depth + 1 <= MAX_DEPTH)
        index[rel] = (list(dirnames), sorted(filenames))
    return dict(sorted(index.items()))


def _git_output(project: Path, *args: str) -> str:
    try:
        done = subprocess.run(["git", "-C", str(project), *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


Finding = Tuple[List[str], str, List[Dict[str, str]], str]  # values, basis, evidence, note


def _roots_finding(roots: Dict[str, List[Dict[str, str]]]) -> Finding:
    if not roots:
        return ["none"], "none-found", [], ""
    evidence = sorted((e for evs in roots.values() for e in evs), key=lambda e: (e["path"], e["reason"]))
    return sorted(roots), "inferred", evidence, ""


class _Inferer:
    """One rule per slot, each looking only for evidence in the repository."""

    def __init__(self, project: Path, plugin_root: Optional[Path], authored_frontend: Optional[List[str]]):
        self.project = project
        self.index = _scan(project)
        self.authored_frontend = authored_frontend
        self.plugin_agents = _plugin_agent_names(plugin_root)
        self.local_agents = [a for a in _project_agent_names(project) if a not in self.plugin_agents]
        self.rules = {
            "project.name": self._project_name, "backend.roots": self._backend,
            "frontend.roots": self._frontend, "frontend.theme-polarity": self._polarity,
            "test.roots": self._tests, "migration.root": self._migration, "auth.roots": self._auth,
            "safety-critical.roots": self._safety, "review.documents": self._documents,
            "implementers": lambda: self._role(DEFAULT_IMPLEMENTERS),
            "review-gates": lambda: self._role(DEFAULT_REVIEW_GATES),
        }

    def infer(self, slot: str) -> Finding:
        """The proposal for one slot; slots with no rule are put to the operator."""
        rule = self.rules.get(slot)
        if rule is None:
            return [], "needs-answer", [], "no inference rule for this slot; ask the operator"
        return rule()

    def _project_name(self) -> Finding:
        url = _git_output(self.project, "config", "--get", "remote.origin.url")
        name = re.split(r"[/:\\]", url.rstrip("/"))[-1] if url else ""
        if name.endswith(".git"):
            name = name[:-4]
        if name:
            return [name], "inferred", [_evidence(".git/config", "git-remote")], ""
        common = _git_output(self.project, "rev-parse", "--git-common-dir")
        if common:
            common_dir = Path(common)
            if not common_dir.is_absolute():
                common_dir = self.project / common_dir
            common_dir = common_dir.resolve()
            name = common_dir.parent.name if common_dir.name == ".git" else common_dir.stem
            if name:
                return [name], "inferred", [_evidence(".git", "folder-name")], ""
        return [], "needs-answer", [], "no origin remote and no git checkout; ask for the name"

    def _backend(self) -> Finding:
        roots: Dict[str, List[Dict[str, str]]] = {}
        for rel, (_dirs, files) in self.index.items():
            for f in files:
                lower = f.lower()
                is_marker = ((lower.endswith(".csproj") and not lower.endswith(TEST_CSPROJ_SUFFIXES))
                             or f in ("go.mod", "pom.xml", "Cargo.toml") or f.startswith("build.gradle")
                             or (f in ("pyproject.toml", "setup.py") and rel != ""))
                if is_marker:
                    roots.setdefault(rel or ".", []).append(_evidence(_join(rel, f), "manifest"))
        return _roots_finding(roots)

    def _frontend(self) -> Finding:
        roots: Dict[str, List[Dict[str, str]]] = {}
        for rel, (_dirs, files) in self.index.items():
            for f in files:
                if f == "angular.json":
                    data = _load_json_lenient(self.project / rel / f)
                    projects = data.get("projects") if isinstance(data, dict) else None
                    for _name, cfg in sorted((projects or {}).items()):
                        value = cfg.get("root", "") if isinstance(cfg, dict) else None
                        if isinstance(value, str):
                            root = posixpath.normpath(posixpath.join(rel or ".", value.replace("\\", "/")))
                            roots.setdefault(root, []).append(_evidence(_join(rel, f), "config-entry"))
                elif f.startswith(BUNDLER_CONFIGS):
                    roots.setdefault(rel or ".", []).append(_evidence(_join(rel, f), "file-exists"))
        return _roots_finding(roots)

    def _polarity(self) -> Finding:
        if self.authored_frontend is not None:
            roots, evidence = [r for r in self.authored_frontend if r != "none"], []
        else:
            values, _basis, evidence, _note = self._frontend()
            roots = [r for r in values if r != "none"]
        if not roots:
            return ["none"], "none-found", [], "there is no frontend root to ask about"
        return roots, "needs-answer", evidence, \
            "never inferred; ask per root (light, dark or both) and write <root>=<polarity>"

    def _has_source(self, rel: str) -> Optional[str]:
        for folder, (_dirs, files) in self.index.items():
            if folder == rel or folder.startswith(rel + "/"):
                for f in files:
                    if os.path.splitext(f)[1] in SOURCE_EXTENSIONS:
                        return _join(folder, f)
        return None

    def _tests(self) -> Finding:
        roots: Dict[str, List[Dict[str, str]]] = {}
        for rel, (_dirs, files) in self.index.items():
            for f in files:
                if f.lower().endswith(TEST_CSPROJ_SUFFIXES):
                    roots.setdefault(rel or ".", []).append(_evidence(_join(rel, f), "manifest"))
                elif f == "pyproject.toml":
                    text = (self.project / rel / f).read_text(encoding="utf-8", errors="replace")
                    match = re.search(r"testpaths\s*=\s*\[(.*?)\]", text, re.S)
                    for entry in re.findall(r"""["']([^"']+)["']""", match.group(1) if match else ""):
                        root = posixpath.normpath(posixpath.join(rel or ".", entry))
                        if (self.project / root).is_dir():
                            roots.setdefault(root, []).append(_evidence(_join(rel, f), "config-entry"))
            if rel.rsplit("/", 1)[-1] in TEST_FOLDER_NAMES:
                source = self._has_source(rel)
                if source:
                    roots.setdefault(rel, []).append(_evidence(source, "folder-name"))
        for root in list(roots):
            if any(root != other and root.startswith(other + "/") for other in roots):
                del roots[root]
        return _roots_finding(roots)

    def _migration(self) -> Finding:
        roots: Dict[str, List[Dict[str, str]]] = {}
        for rel, (_dirs, files) in self.index.items():
            name = rel.rsplit("/", 1)[-1]
            parent = rel.rsplit("/", 1)[0] if "/" in rel else ""
            if rel and name == "Migrations" and any(f.endswith(".cs") for f in files):
                roots[rel] = [_evidence(rel, "folder-name")]
            if any(rel == s or rel.endswith("/" + s) for s in MIGRATION_SUFFIXES):
                roots[rel] = [_evidence(rel, "folder-name")]
            if rel and name == "migrations":
                beside = self.index.get(parent, ([], []))[1]
                marker = next((f for f in beside if f == "manage.py" or f.startswith("knexfile.")), None)
                if marker:
                    roots[rel] = [_evidence(_join(parent, marker), "file-exists")]
        values, basis, evidence, note = _roots_finding(roots)
        if len(values) > 1:
            return values, "needs-answer", evidence, "several candidates; the operator chooses"
        return values, basis, evidence, note

    def _auth(self) -> Finding:
        found = [rel for rel in self.index if rel and rel.rsplit("/", 1)[-1] in AUTH_FOLDER_NAMES]
        if not found:
            return ["none"], "none-found", [], ""
        return sorted(found), "needs-answer", [_evidence(r, "folder-name") for r in sorted(found)], \
            "a folder name is a guess; these are offered, never inferred"

    def _safety(self) -> Finding:
        return ["none"], "needs-answer", [], "never inferred; none if the operator names nothing"

    def _documents(self) -> Finding:
        files = self.index.get("", ([], []))[1]
        docs = sorted(f for f in files
                      if f in REVIEW_DOCUMENTS or (f.startswith("TESTING") and f.endswith(".md")))
        if not docs:
            return ["none"], "none-found", [], ""
        return docs, "inferred", [_evidence(d, "file-exists") for d in docs], ""

    def _role(self, defaults: Sequence[str]) -> Finding:
        if not self.local_agents:
            return ["none"], "none-found", [], "no agent outside the plugin set; the plugin's own are accepted"
        evidence = [_evidence(".claude/agents/%s.md" % a, "agent-file") for a in self.local_agents]
        return list(defaults) + self.local_agents, "needs-answer", evidence, \
            ("local agents have no role yet; filling a role slot REPLACES the plugin defaults, "
             "so they are kept in this proposal")


def _plugin_agent_names(root: Optional[Path]) -> Set[str]:
    names = set(DEFAULT_IMPLEMENTERS) | set(DEFAULT_REVIEW_GATES)
    if root is not None:
        for sub in ("agents", ".claude/agents"):
            names |= {p.stem for p in (root / sub).glob("*.md")}
    return names


def _project_agent_names(project: Path) -> List[str]:
    return sorted(p.stem for p in (project / ".claude" / "agents").glob("*.md"))


def _agent_exists(name: str, project: Path, root: Optional[Path]) -> bool:
    """True when an agent file's stem equals ``name`` exactly (is_file() is case-blind on Windows)."""
    if not re.match(r"^[A-Za-z0-9][\w.\-]*$", name):
        return False
    folders = [project / ".claude" / "agents"]
    if root is not None:
        folders += [root / "agents", root / ".claude" / "agents"]
    return any(name in {p.stem for p in folder.glob("*.md") if p.is_file()} for folder in folders)


def _profile_plan(ctx: _ProfileCtx) -> Tuple[Optional[Result], Dict[str, Any]]:
    """The inferred proposals and the planned output text, shared by the preview and the apply
    so both hash the same bytes."""
    project = ctx.project
    authored_frontend = None
    if ctx.kind("frontend.roots") == "authored":
        authored_frontend = list(load_slot(ctx.base_text, "frontend.roots")) or ["none"]
    try:
        inferer = _Inferer(project, ctx.plugin_root, authored_frontend)
        inferred = {slot: inferer.infer(slot) for slot in ctx.template_slots}
    except OSError as exc:
        return refusal("project-unreadable", "a project file cannot be read: %s" % exc,
                       getattr(exc, "filename", None) or project), {}
    proposals: List[Dict[str, Any]] = []
    fills: Dict[str, List[str]] = {}
    for slot in ctx.template_slots:
        values, basis, evidence, note = inferred[slot]
        if ctx.kind(slot) == "authored":
            authored = list(load_slot(ctx.base_text, slot)) or ["none"]
            if values and values != ["none"] and set(values) != set(authored):
                note = "inference found %s (advice only; the authored value is kept)" % ", ".join(values)
            else:
                note = ""
            proposals.append({"slot": slot, "values": authored, "basis": "kept-authored",
                              "evidence": [], "note": note})
            continue
        proposals.append({"slot": slot, "values": values, "basis": basis, "evidence": evidence, "note": note})
        if basis in ("inferred", "none-found"):
            fills[slot] = [] if values == ["none"] else values
    new_text = _apply_fills(ctx, fills)
    plan_sha = _plan_digest(ctx.old_text.encode("utf-8") if ctx.existed else b"absent",
                            new_text.encode("utf-8"))
    return None, {"proposals": proposals, "new-text": new_text, "plan-sha256": plan_sha,
                  "local-agents": inferer.local_agents}


def propose_profile(
    project: Path,
    claude_home: Optional[Path] = None,
    plugin_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Propose a value, with evidence, for every project-profile slot (ProfilePlan).

    Writes nothing. ``claude_home`` confines the provider-cache lookup of the plugin's template.
    ``plan-sha256`` binds the profile bytes and the planned output; the apply needs it.
    """
    project = Path(project)
    bad, ctx = _load_profile_ctx(project, plugin_root, claude_home)
    if bad or ctx is None:
        return bad or {}
    problem, planned = _profile_plan(ctx)
    if problem:
        return problem
    proposals, new_text = planned["proposals"], planned["new-text"]
    diff = "".join(difflib.unified_diff(
        ctx.old_text.splitlines(keepends=True), new_text.splitlines(keepends=True),
        fromfile=str(ctx.target), tofile=str(ctx.target)))
    return {
        "status": "plan", "target": str(ctx.target), "existed": ctx.existed,
        "source-sha256": ctx.source_sha, "plan-sha256": planned["plan-sha256"], "proposals": proposals,
        "rows-to-fill": [s for s in ctx.template_slots if ctx.kind(s) == "placeholder"],
        "rows-to-add": [s for s in ctx.template_slots if ctx.kind(s) == "missing"],
        "unified-diff": diff, "local-agents": planned["local-agents"],
        "missing-row-detection": ctx.detection,
        "plugin-root": str(ctx.plugin_root) if ctx.plugin_root else None,
    }


def apply_profile(
    project: Path,
    sets: Dict[str, str],
    expect_sha256: str,
    claude_home: Optional[Path] = None,
    plugin_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Write the confirmed values into placeholder slots only (one ``sets`` entry per slot).

    ``sets`` maps slot name to the raw ``v1,v2`` text. Refused (nothing written) when the
    profile changed since the preview, a slot is unknown or already authored, an agent does
    not exist, or a placeholder slot has no answer.
    """
    project = Path(project)
    bad, ctx = _load_profile_ctx(project, plugin_root, claude_home)
    if bad or ctx is None:
        return bad or {}
    problem, planned = _profile_plan(ctx)
    if problem:
        return problem
    if expect_sha256 != planned["plan-sha256"]:
        return refusal("changed-since-preview",
                       "the profile or the plugin template changed since it was previewed (or the "
                       "source-sha256 was passed instead of plan-sha256); run the preview again",
                       ctx.target)
    for slot in sets:
        if slot not in ctx.template_slots:
            return refusal("unknown-slot", "the template declares no slot named %s" % slot, ctx.target)
    for slot, raw in sets.items():
        if "\n" in raw or "\r" in raw or "|" in raw or "`" in raw:
            return refusal("invalid-slot-value",
                           "the value for %s contains a newline, a pipe or a backtick; the script adds the "
                           "backticks itself and a pipe or newline would break the table row" % slot,
                           ctx.target)
    for slot in sets:
        if ctx.kind(slot) == "authored":
            return refusal("slot-already-authored",
                           "%s already holds an authored value and is never changed" % slot, ctx.target)
    writable = [s for s in ctx.template_slots if ctx.kind(s) != "authored"]
    if not writable:
        return {"status": "nothing-to-do", "target": str(ctx.target)}
    for role in ROLE_SLOTS:
        for name in _parse_set_value(sets.get(role, "")):
            if not _agent_exists(name, project, ctx.plugin_root):
                return refusal("unknown-agent",
                               "no agent named %s exists in the project or the plugin" % name, ctx.target)
    unanswered = [s for s in writable if s not in sets]
    if unanswered:
        return refusal("slot-unanswered",
                       "no answer was given for: %s (pass `none` to leave a slot empty)" % ", ".join(unanswered),
                       ctx.target)
    fills = {slot: _parse_set_value(sets[slot]) for slot in writable}
    data = _apply_fills(ctx, fills).encode("utf-8")
    error = _atomic_write(ctx.target, data)
    if error:
        return refusal("write-failed", "the profile could not be written: %s" % error, ctx.target)
    return {"status": "applied", "target": str(ctx.target), "filled": list(fills)}


# =======================================================================================
# Step 5: how the plugin reached this project
# =======================================================================================

def _project_path_matches(recorded: Any, project: Path) -> bool:
    if not isinstance(recorded, str) or not recorded:
        return False
    return _norm(recorded) in (_norm(project), _norm(project.resolve()))


def _load_layers(project: Path, home: Path) -> Tuple[Optional[Result], List[Tuple[str, Path, Any]]]:
    """Every settings layer (user, project, local) read strictly: (refusal, [(layer, path, data)]).

    A layer that does not exist is skipped. One that exists but cannot be read is project-unreadable,
    one that is not valid JSON is malformed-settings, and one of the wrong shape is
    unexpected-settings-shape; each refusal names that file.
    """
    layers = (("user", home / "settings.json"), ("project", project / ".claude" / "settings.json"),
              ("local", project / ".claude" / "settings.local.json"))
    loaded: List[Tuple[str, Path, Any]] = []
    for layer, path in layers:
        if not path.is_file():
            continue
        try:
            raw = path.read_bytes()
        except OSError as exc:
            return refusal("project-unreadable", "%s cannot be read: %s" % (path.name, exc), path), []
        problem, data = _parse_settings(raw, path)
        if problem:
            problem["message"] = "%s (the %s settings layer): %s" % (path.name, layer, problem["message"])
            return problem, []
        loaded.append((layer, path, data))
    return None, loaded


def _enabled_flag(key: str, home: Path, layers: List[Tuple[str, Path, Any]]) -> Tuple[bool, Path]:
    """enabledPlugins[key] with the most specific layer winning; not set reads as False."""
    value, source = False, home / "settings.json"
    for _layer, path, data in layers:
        flags = data.get("enabledPlugins") if isinstance(data, dict) else None
        if isinstance(flags, dict) and isinstance(flags.get(key), bool):
            value, source = flags[key], path
    return value, source


def _find_install(project: Path, home: Path) -> Tuple[Optional[Result], Optional[Tuple[str, Dict[str, Any]]], List[Dict[str, Any]]]:
    """(refusal, (key, entry) of the applicable install, facts); only this plugin's entries count."""
    record = home / "plugins" / "installed_plugins.json"
    if not record.exists():
        return None, None, [_fact("installation-record", "absent", record)]
    try:
        data = json.loads(record.read_bytes().decode("utf-8-sig"))
    except (OSError, ValueError) as exc:
        return refusal("install-record-unreadable", "the installation record cannot be read: %s" % exc, record), None, []
    plugins = data.get("plugins") if isinstance(data, dict) else None
    if not isinstance(plugins, dict) or data.get("version", RECORD_VERSION) != RECORD_VERSION:
        return refusal("install-record-unreadable",
                       "the installation record is not the version-%d format" % RECORD_VERSION, record), None, []
    facts = [_fact("installation-record", "read", record)]
    rank = {"local": 0, "project": 1, "user": 2}
    candidates: List[Tuple[str, Dict[str, Any]]] = []
    for key, entries in plugins.items():
        if not key.startswith(PLUGIN_NAME + "@"):
            continue
        if not isinstance(entries, list):
            return refusal("install-record-unreadable", "the entries of %s are not a list" % key, record), None, []
        applicable = []
        for entry in entries:
            if (not isinstance(entry, dict) or not isinstance(entry.get("installPath"), str)
                    or not entry["installPath"].strip()):
                continue
            scope = entry.get("scope")
            covers = scope == "user" or (scope in ("project", "local")
                                         and _project_path_matches(entry.get("projectPath"), project))
            if covers and Path(entry["installPath"]).is_dir():
                applicable.append(entry)
        if applicable:
            best = sorted(applicable, key=lambda e: rank.get(e.get("scope"), 3))[0]
            candidates.append((key, best))
            facts.append(_fact("installation-entry", "%s scope=%s" % (key, best.get("scope")), record))
    if len(candidates) > 1:
        holding = [c for c in candidates if _is_within(Path(__file__), Path(c[1]["installPath"]))]
        if len(holding) != 1:
            return refusal("install-record-unreadable",
                           "this plugin is installed from several marketplaces (%s) and the running script "
                           "lies in none (or more than one) of them; remove an entry or run the script "
                           "from the intended copy" % ", ".join(sorted(k for k, _e in candidates)),
                           record), None, []
        candidates = holding
    return None, (candidates[0] if candidates else None), facts


def detect_install_mode(
    project: Path,
    claude_home: Optional[Path] = None,
    plugin_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Decide the install mode from files on disk (InstallModeVerdict).

    Precedence: plugin-source, then both, plugin, vendored, none. A present but unreadable
    installation record is returned as the install-record-unreadable refusal, never as a
    verdict. ``plugin_root`` is accepted for symmetry; the mode never depends on it.
    """
    project = Path(project)
    bad = _check_project(project)
    if bad:
        return bad
    home = _claude_home(claude_home)
    manifest = project / ".claude-plugin" / "plugin.json"
    is_source = _manifest_names_plugin(project)
    facts = [_fact("plugin-source", is_source, manifest)]
    if is_source:
        return {"mode": "plugin-source", "enabled": None, "facts": facts}
    problem, found, install_facts = _find_install(project, home)
    if problem:
        return problem
    facts += install_facts
    problem, layers = _load_layers(project, home)
    if problem:
        return problem
    gate = project / ".claude" / "hooks" / "concept-gate.py"
    vendored = gate.is_file()
    facts.append(_fact("vendored-hook", vendored, gate))
    verdict: Dict[str, Any] = {"enabled": None}
    installed = found is not None
    if found:
        key, entry = found
        enabled, source = _enabled_flag(key, home, layers)
        facts.append(_fact("enabled-flag", enabled, source))
        verdict.update({"enabled": enabled, "plugin-key": key, "install-path": entry["installPath"],
                        "installed-version": entry.get("version"), "installation-record": str(
                            home / "plugins" / "installed_plugins.json")})
    # A plugin that is not enabled runs no hook, so beside a vendored copy it cannot double them.
    # "Not enabled" includes no entry at all in any readable layer; managed settings and a
    # --settings file are not read (see NOT_READ_NOTE).
    running = installed and verdict.get("enabled") is True
    verdict["mode"] = ("both" if running and vendored else "plugin" if installed and not vendored
                       else "plugin" if running else "vendored" if vendored else "none")
    verdict["facts"] = facts
    return verdict


def _no_hooks_provider(provider: str, project: Path) -> Result:
    return refusal("provider-has-no-hooks",
                   "hooks are Claude-only in this release; %s has none to register" % provider, project)


def _mode_refusal(verdict: Result, project: Path) -> Optional[Result]:
    """The refusal for a mode that is neither a plugin install nor a vendored copy."""
    mode = verdict.get("mode")
    if mode == "plugin-source":
        return refusal("plugin-source-checkout",
                       "this project is the plugin's own checkout; there is nothing to register", project)
    if mode == "both":
        return refusal("install-mode-both",
                       "the plugin is installed (see the installation record installed_plugins.json and "
                       "enabledPlugins) AND the hooks are vendored (.claude/hooks/concept-gate.py), so "
                       "every hook would run twice; remove one of the two", project)
    if mode == "none":
        return refusal("install-mode-none",
                       "the plugin is not installed for this project and no hooks are vendored", project)
    return None


# --- hook registrations ----------------------------------------------------------------

def _split_command(command: str) -> List[str]:
    return [a or b or c for a, b, c in _TOKEN.findall(command)]


def _hook_tokens(hook: Dict[str, Any]) -> List[str]:
    command = hook.get("command")
    if isinstance(hook.get("args"), list):
        return [str(command)] + [str(a) for a in hook["args"]]
    return _split_command(command) if isinstance(command, str) else []


def _hook_key(hook: Dict[str, Any]) -> Optional[Tuple[str, Tuple[str, ...], str, str, str]]:
    """(hook file, arguments after it, folder, launcher, path token) of a registration, or None."""
    tokens = _hook_tokens(hook)
    for i, token in enumerate(tokens):
        if token.lower().endswith(".py"):
            path = token.replace("\\", "/")
            folder = path.rsplit("/", 1)[0] if "/" in path else ""
            return path.rsplit("/", 1)[-1], tuple(tokens[i + 1:]), folder, tokens[0], token
    return None


def _compare_extras(extras: Tuple[str, ...]) -> Tuple[str, ...]:
    """Comparison form of the arguments after a hook file: a ``.py`` path is reduced to its file name,
    so the gate launcher's gate argument matches whether it names the plugin's folder or the project's."""
    return tuple(a.replace("\\", "/").rsplit("/", 1)[-1] if a.lower().endswith(".py") else a for a in extras)


_PLUGIN_ROOT_PREFIXES = ("${CLAUDE_PLUGIN_ROOT}/", "$CLAUDE_PLUGIN_ROOT/")


def _is_plugin_script_arg(arg: str) -> bool:
    """True for an argument that is a ``.py`` path under the plugin root variable."""
    text = arg.replace("\\", "/")
    return text.lower().endswith(".py") and text.startswith(_PLUGIN_ROOT_PREFIXES)


@dataclass(frozen=True)
class _Registration:
    """One hook registration read from a hooks.json."""

    event: str
    matcher: Optional[str]
    file: str
    extras: Tuple[str, ...]
    launcher: str
    path_token: str
    hook_type: str
    other_keys: Tuple[Tuple[str, Any], ...]

    @property
    def compare_extras(self) -> Tuple[str, ...]:
        """The arguments after the hook file, each ``.py`` path reduced to its file name."""
        return _compare_extras(self.extras)

    @property
    def key(self) -> str:
        """The registration key: event, hook file and any argument after it (``.py`` paths by file name)."""
        return "|".join((self.event, self.file) + self.compare_extras)


def _iter_hooks(settings: Any):
    """Yield (event, matcher, hook dict) for every hook, ignoring any malformed part."""
    hooks = settings.get("hooks") if isinstance(settings, dict) else None
    if not isinstance(hooks, dict):
        return
    for event, groups in hooks.items():
        for group in groups if isinstance(groups, list) else []:
            if not isinstance(group, dict):
                continue
            for hook in group.get("hooks") if isinstance(group.get("hooks"), list) else []:
                if isinstance(hook, dict):
                    yield event, group.get("matcher"), hook


def _source_registrations(hooks_json: Path) -> Tuple[Optional[Result], List[_Registration]]:
    data = _load_json_lenient(hooks_json)
    if not isinstance(data, dict):
        return refusal("hooks-json-missing", "the hooks.json cannot be read", hooks_json), []
    regs: List[_Registration] = []
    for event, matcher, hook in _iter_hooks(data):
        parsed = _hook_key(hook)
        if parsed is None:
            continue
        file, extras, _folder, launcher, token = parsed
        other = tuple((k, v) for k, v in hook.items() if k not in ("type", "command", "args"))
        regs.append(_Registration(event, matcher, file, extras, launcher, token,
                                  str(hook.get("type", "command")), other))
    return None, regs


def _existing_registrations(project: Path, home: Path
                            ) -> Tuple[List[Dict[str, Any]], bool, Optional[Result]]:
    """Registrations in the user, project and local layers, whether any layer disables hooks,
    and the refusal for a layer that exists but cannot be read, parsed or has the wrong shape."""
    problem, layers = _load_layers(project, home)
    if problem:
        return [], False, problem
    found: List[Dict[str, Any]] = []
    disabled = False
    for layer, _path, data in layers:
        if isinstance(data, dict) and data.get("disableAllHooks") is True:
            disabled = True
        for event, matcher, hook in _iter_hooks(data):
            parsed = _hook_key(hook)
            if parsed:
                found.append({"layer": layer, "event": event, "matcher": matcher, "file": parsed[0],
                              "extras": _compare_extras(parsed[1]), "folder": parsed[2]})
    return found, disabled, None


def _is_project_folder(folder: str, project: Path) -> bool:
    if folder in _PROJECT_HOOK_DIRS:
        return True
    return _norm(folder) == _norm(project / ".claude" / "hooks")


# --- readiness (plugin install) --------------------------------------------------------

def _scan_env_vars(hooks_dir: Path) -> List[str]:
    found: Set[str] = set()
    for path in sorted(hooks_dir.glob("*.py")):
        try:
            found.update(_ENV_READ.findall(path.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue  # an unreadable hook only shortens the kill-switch list
    return sorted(found - _ENV_EXCLUDED)


def _db_rules_state(install: Path) -> str:
    data = _load_json_lenient(install / ".claude" / "hooks" / "db-destructive-guard.rules.json")
    names = data.get("protected_databases") if isinstance(data, dict) else None
    names = [n for n in names if isinstance(n, str) and n.strip()] if isinstance(names, list) else []
    if not names:
        return "absent-fail-closed"
    return "template-placeholders" if all(n in TEMPLATE_DATABASES for n in names) else "configured"


def _marketplace_version(home: Path, key: str) -> Optional[str]:
    marketplace = key.split("@", 1)[1] if "@" in key else ""
    data = _load_json_lenient(home / "plugins" / "marketplaces" / marketplace / ".claude-plugin" / "marketplace.json")
    for entry in (data.get("plugins") if isinstance(data, dict) else None) or []:
        if isinstance(entry, dict) and entry.get("name") == PLUGIN_NAME:
            return entry.get("version")
    return None


def _readiness(project: Path, home: Path, verdict: Result, platform: str) -> Result:
    install = Path(verdict["install-path"])
    manifest = _load_json_lenient(install / ".claude-plugin" / "plugin.json")
    field_value = manifest.get("hooks") if isinstance(manifest, dict) else None
    declared = install / field_value if isinstance(field_value, str) else None
    resolves = bool(declared and declared.is_file())
    hooks_json = declared if resolves else install / ".claude" / "hooks" / "hooks.json"
    regs: List[_Registration] = []
    if hooks_json.is_file():
        _problem, regs = _source_registrations(hooks_json)
    unresolved: List[str] = []
    resolved_files: Dict[str, Path] = {}
    def _expand(token: str) -> str:
        return token.replace("${CLAUDE_PLUGIN_ROOT}", str(install)).replace("$CLAUDE_PLUGIN_ROOT", str(install))

    for reg in regs:
        text = _expand(reg.path_token)
        if Path(text).is_file():
            resolved_files[reg.file] = Path(text)
            if reg.file == "gate-launch.py":
                # the launcher's body is imported by the stub: a syntax error there blocks every call
                body = Path(text).with_name("_gate_launch.py")
                if body.is_file():
                    resolved_files[body.name] = body
                else:
                    unresolved.append("%s %s" % (reg.event, body))
        else:
            unresolved.append("%s %s" % (reg.event, reg.path_token))
        for extra in reg.extras:
            if _is_plugin_script_arg(extra):
                extra_path = Path(_expand(extra))
                if extra_path.is_file():
                    resolved_files[extra_path.name] = extra_path
                else:
                    unresolved.append("%s %s" % (reg.event, extra))
    launchers = sorted({reg.launcher for reg in regs})
    found_launchers = [bool(shutil.which(name)) for name in launchers]
    interpreter_found = bool(launchers) and all(found_launchers)
    failures: List[str] = []
    for name, path in sorted(resolved_files.items()):
        try:
            compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
        except (SyntaxError, ValueError, OSError) as exc:
            failures.append("%s: %s" % (name, exc))
    existing, disabled, problem = _existing_registrations(project, home)
    if problem:
        return problem
    plugin_keys = {(r.event, r.file, r.compare_extras) for r in regs}
    duplicate = any(e["layer"] in ("project", "local") and (e["event"], e["file"], e["extras"]) in plugin_keys
                    for e in existing)
    installed_version = verdict.get("installed-version")
    marketplace_version = _marketplace_version(home, verdict["plugin-key"])
    version_ok = not (installed_version and marketplace_version and installed_version != marketplace_version)
    posix = platform != "win32"
    checks = [
        ("enabled", verdict.get("enabled") is True), ("manifest-hooks-resolves", resolves),
        ("hooks-registered", len(regs) > 0), ("commands-resolve", not unresolved),
        ("launcher-found", interpreter_found), ("hooks-compile", not failures),
        ("hooks-not-disabled", not disabled), ("no-duplicate-registration", not duplicate),
        ("version-matches-marketplace", version_ok), ("platform-launcher", not posix),
    ]
    ready = all(ok for _name, ok in checks)
    report: Result = {
        "status": "plan", "mode": "plugin", "ready": ready,
        "verdict": "ready to load (not proof the running session loaded them)" if ready else "not ready",
        "install-path": str(install), "installed-version": installed_version,
        "marketplace-version": marketplace_version, "enabled": verdict.get("enabled"),
        "hooks-registered": len(regs), "unresolved-commands": unresolved,
        "manifest-hooks-resolves": resolves, "interpreter-found": interpreter_found,
        "launchers": launchers, "hooks-compile": not failures, "compile-failures": failures,
        "disable-all-hooks": disabled, "duplicate-vendored-registration": duplicate,
        "checks": [{"name": n, "ok": ok} for n, ok in checks],
        "kill-switches": _scan_env_vars(install / ".claude" / "hooks"),
        "gates": sorted({r.file for r in regs if r.event == "PreToolUse"}),
        "database-guard-rules": _db_rules_state(install),
        "not-verifiable": list(NOT_VERIFIABLE), "code-search-first-note": CODE_SEARCH_NOTE,
        "add-ons": _addon_listing(install),
    }
    if posix:
        report["platform-note"] = PLATFORM_NOTE
    return report


def readiness_report(
    project: Path,
    claude_home: Optional[Path] = None,
    plugin_root: Optional[Path] = None,
    platform: Optional[str] = None,
) -> Dict[str, Any]:
    """Report whether an installed plugin's hooks are ready to load (ReadinessReport).

    Reads only; compiles in memory so no .pyc is written. "Ready to load" is never "live":
    the fixed ``not-verifiable`` list says what only a running session can show. Any
    other install mode is returned as its refusal.
    """
    project = Path(project)
    verdict = detect_install_mode(project, claude_home, plugin_root)
    if _is_refusal(verdict):
        return verdict
    if verdict["mode"] != "plugin":
        return _mode_refusal(verdict, project) or refusal(
            "install-mode-none", "this project is not a plugin install", project)
    return _readiness(project, _claude_home(claude_home), verdict, platform or sys.platform)


# --- vendored merge --------------------------------------------------------------------

class _DuplicateKey(ValueError):
    """A JSON object repeated a key; a standard parser would drop one silently."""


def _strict_pairs(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    seen: Set[str] = set()
    for key, _value in pairs:
        if key in seen:
            raise _DuplicateKey(key)
        seen.add(key)
    return dict(pairs)


def _parse_settings(data: bytes, target: Path) -> Tuple[Optional[Result], Any]:
    try:
        parsed = json.loads(data.decode("utf-8-sig"), object_pairs_hook=_strict_pairs)
    except _DuplicateKey as exc:
        return refusal("malformed-settings", "duplicate key %s in settings.json" % exc, target), None
    except json.JSONDecodeError as exc:
        return refusal("malformed-settings", "settings.json is not valid JSON: %s at line %d column %d"
                       % (exc.msg, exc.lineno, exc.colno), target), None
    except UnicodeDecodeError as exc:
        return refusal("malformed-settings", "settings.json is not UTF-8: %s" % exc, target), None
    shape = refusal("unexpected-settings-shape",
                    "settings.json must be an object whose hooks are event -> list of groups", target)
    if not isinstance(parsed, dict):
        return shape, None
    hooks = parsed.get("hooks", {})
    if not isinstance(hooks, dict):
        return shape, None
    for groups in hooks.values():
        if not isinstance(groups, list):
            return shape, None
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks", []), list):
                return shape, None
    return None, parsed


def _written_hook(reg: _Registration, platform: str) -> Dict[str, Any]:
    """The command + args form, with the project path variable, never the plugin one."""
    path = "${CLAUDE_PROJECT_DIR}/.claude/hooks/" + reg.file
    # An argument that is itself a plugin script (the gate launcher's gate) gets the same rewrite as the
    # first path; every other argument is copied unchanged.
    extras = ["${CLAUDE_PROJECT_DIR}/.claude/hooks/" + a.replace("\\", "/").rsplit("/", 1)[-1]
              if _is_plugin_script_arg(a) else a for a in reg.extras]
    if platform == "win32":
        command, args = "py", ["-3", path] + extras
    else:
        command, args = "python3", [path] + extras
    hook: Dict[str, Any] = {"type": reg.hook_type, "command": command, "args": args}
    hook.update(dict(reg.other_keys))
    return hook


def _plugin_hooks_json(root: Optional[Path]) -> Optional[Path]:
    if root is None:
        return None
    manifest = _load_json_lenient(root / ".claude-plugin" / "plugin.json")
    declared = manifest.get("hooks") if isinstance(manifest, dict) else None
    for candidate in ((root / declared) if isinstance(declared, str) else None,
                      root / ".claude" / "hooks" / "hooks.json"):
        if candidate is not None and candidate.is_file():
            return candidate
    return None


def _plan_settings_edit(project: Path, platform: str, home: Path, regs: List[_Registration]
                        ) -> Tuple[Optional[Result], Dict[str, Any]]:
    """The one settings.json merge both the vendored hooks step and an add-on install use.

    Reads the project's settings.json strictly, finds which of ``regs`` no layer registers yet, and
    renders the file with those rows appended in exec form (the existing text, indent, line ending and
    byte order mark are kept). Writes nothing. Returns (refusal, {}) or (None, edit) where edit carries
    the target, the old and new bytes, the rows to add, the rows already present, notes, whether any
    layer disables hooks, and the unified diff.
    """
    target = project / ".claude" / "settings.json"
    try:
        old_bytes = target.read_bytes() if target.is_file() else None
    except OSError as exc:
        return refusal("project-unreadable", "settings.json cannot be read: %s" % exc, target), {}
    settings: Any = {}
    if old_bytes is not None:
        problem, settings = _parse_settings(old_bytes, target)
        if problem:
            return problem, {}
    existing, disabled, problem = _existing_registrations(project, home)
    if problem:
        return problem, {}
    to_add: List[_Registration] = []
    present: List[Dict[str, Any]] = []
    notes: List[str] = []
    for reg in regs:
        matches = [e for e in existing if (e["event"], e["file"], e["extras"]) == (reg.event, reg.file, reg.compare_extras)]
        if not matches:
            to_add.append(reg)
        for match in matches:
            different = (match["matcher"] or None) != (reg.matcher or None)
            present.append({"registration-key": reg.key, "layer": match["layer"],
                            "different-matcher": different,
                            "foreign-path": not _is_project_folder(match["folder"], project)})
            if different:
                notes.append("%s is registered under matcher %r, the source uses %r; tools only the source "
                             "matcher names are not covered" % (reg.key, match["matcher"], reg.matcher))
    text = old_bytes.decode("utf-8-sig") if old_bytes is not None else ""
    newline = "\r\n" if "\r\n" in text else "\n"
    indent_match = re.search(r"\n([ \t]+)\S", text)
    indent = indent_match.group(1) if indent_match else "  "
    new_settings = settings
    for reg in to_add:
        groups = new_settings.setdefault("hooks", {}).setdefault(reg.event, [])
        group = next((g for g in groups if g.get("matcher") == reg.matcher), None)
        if group is None:
            group = {"matcher": reg.matcher, "hooks": []} if reg.matcher is not None else {"hooks": []}
            groups.append(group)
        group.setdefault("hooks", []).append(_written_hook(reg, platform))
    new_text = ""
    if to_add:
        new_text = json.dumps(new_settings, indent=indent, ensure_ascii=False).replace("\n", newline) + newline
    bom = b"\xef\xbb\xbf" if old_bytes is not None and old_bytes.startswith(b"\xef\xbb\xbf") else b""
    diff = "".join(difflib.unified_diff(text.splitlines(keepends=True), new_text.splitlines(keepends=True),
                                        fromfile=str(target), tofile=str(target))) if to_add else ""
    return None, {"target": target, "old-bytes": old_bytes, "new-bytes": bom + new_text.encode("utf-8"),
                  "to-add": to_add, "present": present, "notes": notes, "disabled": disabled, "diff": diff}


def _plan_vendored(project: Path, platform: str, home: Path, plugin_root: Optional[Path],
                   skip: Optional[List[str]]) -> Tuple[Result, Dict[str, Any]]:
    """The SettingsPlan (or a refusal) plus the bytes the apply needs."""
    own = project / ".claude" / "hooks" / "hooks.json"
    chosen_root: Optional[Path] = None
    source: Optional[Path] = own
    if not own.is_file():
        chosen_root = _separate_plugin_root(project, plugin_root, home,
                                            lambda r: _plugin_hooks_json(r) is not None)
        source = _plugin_hooks_json(chosen_root)
    if source is None:
        return refusal("hooks-json-missing", "neither the project nor the plugin has a hooks.json to read",
                       own), {}
    problem, regs = _source_registrations(source)
    if problem:
        return problem, {}
    skipped = set(skip or [])
    regs = [r for r in regs if r.file not in skipped]
    problem, edit = _plan_settings_edit(project, platform, home, regs)
    if problem:
        return problem, {}
    target, old_bytes, new_bytes = edit["target"], edit["old-bytes"], edit["new-bytes"]
    to_add, present, notes = edit["to-add"], edit["present"], edit["notes"]
    disabled, diff = edit["disabled"], edit["diff"]
    if platform == "win32" and any(r.file == "db-destructive-guard.py" and "PowerShell" not in (r.matcher or "")
                                   for r in regs):
        notes.append("the database guard's matcher names no PowerShell tool, so a PowerShell command is not checked")
    skip_list = "\n".join(sorted(skipped)).encode("utf-8")
    plan: Result = {
        "status": "plan", "install-mode": "vendored", "target": str(target), "hooks-json": str(source),
        "plugin-root": str(chosen_root) if chosen_root else None,
        "source-sha256": _sha256(old_bytes) if old_bytes is not None else "absent",
        "plan-sha256": _plan_digest(old_bytes if old_bytes is not None else b"absent", new_bytes, skip_list),
        "to-add": [{"event": r.event, "matcher": r.matcher, "command": _written_hook(r, platform)["command"],
                    "args": _written_hook(r, platform)["args"], "registration-key": r.key} for r in to_add],
        "already-present": present, "interpreter": "py -3" if platform == "win32" else "python3",
        "disable-all-hooks": disabled, "unified-diff": diff, "notes": notes, "skipped": sorted(skipped),
    }
    return plan, {"old-bytes": old_bytes, "new-bytes": new_bytes, "to-add": to_add}


def plan_hooks(
    project: Path,
    platform: str,
    provider: str = "claude",
    claude_home: Optional[Path] = None,
    plugin_root: Optional[Path] = None,
    skip: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Plan the hook step: SettingsPlan (vendored) or ReadinessReport (plugin), or a Refusal.

    Writes nothing. ``skip`` leaves the named hook files out of a vendored plan.
    """
    project = Path(project)
    if provider != "claude":
        return _no_hooks_provider(provider, project)
    verdict = detect_install_mode(project, claude_home, plugin_root)
    if _is_refusal(verdict):
        return verdict
    gate = _mode_refusal(verdict, project)
    if gate:
        return gate
    home = _claude_home(claude_home)
    if verdict["mode"] == "plugin":
        if verdict.get("enabled") is not True:
            return refusal("plugin-disabled", "the plugin is installed but is not enabled in enabledPlugins, "
                           "so none of its hooks run. " + NOT_READ_NOTE,
                           verdict.get("installation-record", project))
        return _readiness(project, home, verdict, platform or sys.platform)
    plan, _payload = _plan_vendored(project, platform or sys.platform, home, plugin_root, skip)
    if plan.get("status") == "plan" and verdict.get("install-path"):
        plan["notes"] = list(plan.get("notes", [])) + [
            "the plugin is installed but not enabled, so the vendored copy is the only one that runs. "
            + NOT_READ_NOTE]
    return plan


def _backup_write(target: Path, data: bytes) -> Path:
    """Create settings.json.bak-<UTC stamp> without ever overwriting an existing backup."""
    base = target.name + ".bak-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    n = 0
    while True:
        path = target.with_name(base if n == 0 else "%s-%d" % (base, n))
        try:
            with open(path, "xb") as handle:
                try:
                    handle.write(data)
                except OSError:
                    handle.close()
                    path.unlink()  # never leave a half-written backup this run created
                    raise
            return path
        except FileExistsError:
            n += 1


def apply_hooks(
    project: Path,
    expect_sha256: str,
    skip: Optional[List[str]] = None,
    platform: Optional[str] = None,
    provider: str = "claude",
    claude_home: Optional[Path] = None,
    plugin_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Merge the missing registrations into the vendored project's settings.json.

    Only a ``vendored`` project is ever written. The previewed hash must still match, every
    referenced hook file must exist and the interpreter must be on PATH; then a backup is
    taken and the file is replaced atomically. Nothing missing means nothing written.
    """
    project = Path(project)
    platform = platform or sys.platform
    if provider != "claude":
        return _no_hooks_provider(provider, project)
    verdict = detect_install_mode(project, claude_home, plugin_root)
    if _is_refusal(verdict):
        return verdict
    if verdict["mode"] == "plugin":
        return refusal("plugin-install-needs-no-registration",
                       "the plugin is installed as a plugin; its hooks register themselves, so nothing is "
                       "written to settings.json", project / ".claude" / "settings.json")
    gate = _mode_refusal(verdict, project)
    if gate:
        return gate
    plan, payload = _plan_vendored(project, platform, _claude_home(claude_home), plugin_root, skip)
    if _is_refusal(plan):
        return plan
    target = Path(plan["target"])
    if expect_sha256 != plan["plan-sha256"]:
        return refusal("changed-since-preview",
                       "what would be written changed since it was previewed (the settings files, the source "
                       "hooks.json, the platform or the --skip list differ); run the preview again with the "
                       "same flags", target)
    if not payload["to-add"]:
        return {"status": "nothing-to-do", "target": str(target)}
    for reg in payload["to-add"]:
        hook_path = project / ".claude" / "hooks" / reg.file
        if not hook_path.is_file():
            return refusal("hook-file-missing", "%s does not exist; a missing hook script exits 2 and blocks "
                           "every tool call" % reg.file, hook_path)
    launcher = "py" if platform == "win32" else "python3"
    if not shutil.which(launcher):
        return refusal("interpreter-not-found", "%s is not on PATH; a missing program fails open silently"
                       % launcher, target)
    if os.path.islink(str(target)):
        return refusal("write-failed", "%s is a symbolic link; the apply would replace the link or write "
                       "through it, so nothing was written. Edit the file it points to by hand" % target.name,
                       target)
    old_bytes = payload["old-bytes"]
    try:
        current = target.read_bytes() if target.is_file() else None
    except OSError as exc:
        return refusal("project-unreadable", "settings.json cannot be read: %s" % exc, target)
    if current != old_bytes:
        return refusal("changed-since-preview", "settings.json changed while the apply was running", target)
    backup: Optional[Path] = None
    try:
        if old_bytes is not None:
            backup = _backup_write(target, old_bytes)
    except OSError as exc:
        return refusal("write-failed", "the backup could not be written: %s" % exc, target)
    error = _atomic_write(target, payload["new-bytes"])
    if error:
        if backup is not None:
            try:
                backup.unlink()  # the original is untouched, so the tree must be byte-identical
            except OSError:
                pass
        return refusal("write-failed", "settings.json could not be replaced: %s" % error, target)
    return {"status": "applied", "target": str(target), "backup": str(backup) if backup else None,
            "added": len(payload["to-add"]),
            "rollback": ("copy %s over %s" % (backup, target)) if backup else "delete %s" % target,
            "gitignore-hint": ".claude/settings.json.bak-*"}


# --- add-ons ---------------------------------------------------------------------------

def _plain_name(value: Any) -> bool:
    """A bare file name: no separator, no parent reference, not empty."""
    return (isinstance(value, str) and value not in ("", ".", "..")
            and "/" not in value and "\\" not in value and not value.startswith("."))


def _addon_manifest_problem(path: Path, why: str) -> Result:
    return refusal("addon-manifest-missing", "the add-on manifest %s is unusable: %s" % (path.name, why), path)


def _read_addon_manifest(folder: Path) -> Tuple[Optional[Result], Dict[str, Any]]:
    """The parsed, shape-checked addon.json of an add-on folder, or a refusal (exit 3)."""
    path = folder / "addon.json"
    if not path.is_file():
        return refusal("addon-manifest-missing",
                       "the add-on %s has no addon.json in the plugin" % folder.name, path), {}
    data = _load_json_lenient(path)
    if not isinstance(data, dict):
        return _addon_manifest_problem(path, "it is not a JSON object"), {}
    hooks, helpers = data.get("hooks"), data.get("helpers")
    rows, prerequisites = data.get("registrations"), data.get("prerequisites")
    if not (isinstance(hooks, list) and hooks and all(_plain_name(h) and str(h).endswith(".py") for h in hooks)):
        return _addon_manifest_problem(path, "hooks must be a non-empty list of hook file names"), {}
    if not (isinstance(helpers, list) and all(
            isinstance(h, str) and h.startswith(ADDON_HELPER_ROOTS) and ".." not in h.split("/")
            and "\\" not in h for h in helpers)):
        return _addon_manifest_problem(path, "helpers must be paths under .claude/hooks/ or .claude/scripts/"), {}
    if not (isinstance(rows, list) and rows and all(
            isinstance(r, dict) and r.get("hook") in hooks and isinstance(r.get("event"), str) and r["event"]
            and isinstance(r.get("args", []), list) and all(isinstance(a, str) for a in r.get("args", []))
            and isinstance(r.get("matcher", ""), str) for r in rows)):
        return _addon_manifest_problem(path, "registrations must be rows naming an event and one of the hooks"), {}
    if not (isinstance(prerequisites, list) and all(
            isinstance(p, dict) and p.get("kind") == "mcp-server" and isinstance(p.get("name"), str) and p["name"]
            for p in prerequisites)):
        return _addon_manifest_problem(path, "prerequisites must be a list of mcp-server entries"), {}
    return None, data


def _addon_listing(root: Path) -> List[Dict[str, Any]]:
    """Every add-on folder of a plugin tree with its install skill, for the readiness report."""
    found: List[Dict[str, Any]] = []
    base = Path(root) / ADDONS_REL
    try:
        folders = sorted(p for p in base.iterdir() if p.is_dir())
    except OSError:
        return found
    for folder in folders:
        data = _load_json_lenient(folder / "addon.json")
        if isinstance(data, dict) and isinstance(data.get("install_skill"), str):
            found.append({"name": folder.name, "install-skill": data["install_skill"],
                          "hooks": [h for h in data.get("hooks", []) if isinstance(h, str)]})
    return found


def _mcp_servers_in(data: Any) -> Set[str]:
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    return set(servers) if isinstance(servers, dict) else set()


def _mcp_server_configured(server: str, project: Path, claude_home: Optional[Path]) -> bool:
    """True when ``server`` is configured in the project's .mcp.json, in the user's Claude configuration
    file (``.claude.json``, in the home directory or the Claude config directory), or in that file's entry
    for this project. An entry under another project's path does not count."""
    if server in _mcp_servers_in(_load_json_lenient(project / ".mcp.json")):
        return True
    user_files = {Path(os.path.expanduser("~")) / ".claude.json", _claude_home(claude_home) / ".claude.json"}
    wanted = {_norm(project), _norm(project.resolve()), project.as_posix()}
    for path in sorted(user_files):
        data = _load_json_lenient(path)
        if server in _mcp_servers_in(data):
            return True
        projects = data.get("projects") if isinstance(data, dict) else None
        for key, entry in (projects.items() if isinstance(projects, dict) else []):
            if (_norm(key) in wanted or str(key).replace("\\", "/") in wanted) and server in _mcp_servers_in(entry):
                return True
    return False


def _fold_text_bytes(data: bytes) -> bytes:
    """Line endings folded and a leading byte order mark stripped, the drift check's comparison form."""
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.replace(b"\r\n", b"\n")


def _addon_file_ops(project: Path, root: Path, folder: Path, manifest: Dict[str, Any]
                    ) -> Tuple[Optional[Result], List[Dict[str, Any]]]:
    """What the install does to each file: copy it, find it already identical, or leave a helper alone.

    A hook file that exists in the project and differs from the plugin's is refused (addon-file-differs):
    nothing is overwritten. A helper that exists is kept as it is, whatever it holds.
    """
    ops: List[Dict[str, Any]] = []
    entries = [("hook", ".claude/hooks/" + h, folder / "hooks" / h) for h in manifest["hooks"]]
    entries += [("helper", h, root / h) for h in manifest["helpers"]]
    for kind, rel, src in entries:
        if not src.is_file():
            return refusal("hook-file-missing", "%s is not in the plugin (%s); the install would leave a row "
                           "pointing at nothing" % (rel, src), src), []
        try:
            wanted = src.read_bytes()
        except OSError as exc:
            return refusal("hook-file-missing", "%s cannot be read: %s" % (src, exc), src), []
        dest = project / Path(rel)
        action = "copy"
        if os.path.lexists(str(dest)):
            if kind == "helper":
                action = "keep-existing"
            else:
                try:
                    have = dest.read_bytes() if dest.is_file() and not os.path.islink(str(dest)) else None
                except OSError:
                    have = None
                if have is None or _fold_text_bytes(have) != _fold_text_bytes(wanted):
                    return refusal("addon-file-differs",
                                   "%s exists in the project and differs from the plugin's add-on file, so it "
                                   "is left as it is and nothing was written. Compare it with %s, then rename "
                                   "or remove it by hand if you want the add-on's copy" % (rel, src), dest), []
                action = "present"
        ops.append({"path": rel, "kind": kind, "action": action, "dest": dest, "data": wanted,
                    "sha256": _sha256(wanted)})
    return None, ops


def _plan_addon(project: Path, name: str, platform: str, claude_home: Optional[Path],
                plugin_root: Optional[Path], provider: str = "claude") -> Tuple[Result, Dict[str, Any]]:
    """The AddonPlan (or a refusal) plus the bytes the apply needs. Writes nothing."""
    if provider != "claude":
        return _no_hooks_provider(provider, project), {}
    bad = _check_project(project)
    if bad:
        return bad, {}
    if _manifest_names_plugin(project):
        return refusal("plugin-source-checkout",
                       "this project is the plugin's own checkout; an add-on is installed into a project "
                       "that uses the plugin", project), {}
    if not ADDON_NAME_RE.match(name or ""):
        return refusal("addon-unknown", "%r is not an add-on name" % name, project), {}
    home = _claude_home(claude_home)
    root = _separate_plugin_root(project, plugin_root, home, lambda r: (r / ADDONS_REL / name).is_dir())
    if root is None:
        return refusal("addon-manifest-missing",
                       "no copy of the plugin with an add-ons folder was found to install from", project), {}
    folder = root / ADDONS_REL / name
    if not folder.is_dir():
        known = sorted(a["name"] for a in _addon_listing(root))
        return refusal("addon-unknown", "there is no add-on %r under %s; the add-ons are: %s"
                       % (name, root / ADDONS_REL, ", ".join(known) or "none"), folder), {}
    problem, manifest = _read_addon_manifest(folder)
    if problem:
        return problem, {}
    for need in manifest["prerequisites"]:
        if not _mcp_server_configured(need["name"], project, claude_home):
            return refusal(
                "codegraph-mcp-not-configured",
                "the %s MCP server is not configured, so the %s add-on is not installed. Looked in the "
                "project's .mcp.json, in the user's Claude configuration file (.claude.json) and in that "
                "file's entry for this project. A gate installed without the server blocks every source read "
                "and gives the agent no way past it. Configure the server first, then run this again."
                % (need["name"], name), project / ".mcp.json"), {}
    problem, ops = _addon_file_ops(project, root, folder, manifest)
    if problem:
        return problem, {}
    regs = [_Registration(r["event"], r.get("matcher") or None, r["hook"], tuple(r.get("args", [])),
                          "py", r["hook"], "command",
                          tuple((k, r[k]) for k in ADDON_ROW_KEYS if k in r))
            for r in manifest["registrations"]]
    problem, edit = _plan_settings_edit(project, platform, home, regs)
    if problem:
        return problem, {}
    ops_digest = "\n".join("%s|%s|%s" % (o["action"], o["path"], o["sha256"]) for o in ops).encode("utf-8")
    old_bytes, new_bytes, to_add = edit["old-bytes"], edit["new-bytes"], edit["to-add"]
    plan: Result = {
        "status": "plan", "add-on": name, "install-skill": manifest.get("install_skill"),
        "target": str(edit["target"]), "plugin-root": str(root),
        "files": [{"path": o["path"], "kind": o["kind"], "action": o["action"]} for o in ops],
        "source-sha256": _sha256(old_bytes) if old_bytes is not None else "absent",
        "plan-sha256": _plan_digest(old_bytes if old_bytes is not None else b"absent", new_bytes, ops_digest),
        "to-add": [{"event": r.event, "matcher": r.matcher, "command": _written_hook(r, platform)["command"],
                    "args": _written_hook(r, platform)["args"], "registration-key": r.key} for r in to_add],
        "already-present": edit["present"], "interpreter": "py -3" if platform == "win32" else "python3",
        "disable-all-hooks": edit["disabled"], "unified-diff": edit["diff"], "notes": edit["notes"],
        "kill-switches": [k for k in manifest.get("kill_switches", []) if isinstance(k, str)],
        "new-session-note": NEW_SESSION_NOTE,
    }
    return plan, {"old-bytes": old_bytes, "new-bytes": new_bytes, "to-add": to_add, "ops": ops}


def plan_addon(
    project: Path,
    name: str,
    platform: Optional[str] = None,
    claude_home: Optional[Path] = None,
    plugin_root: Optional[Path] = None,
    provider: str = "claude",
) -> Dict[str, Any]:
    """Preview installing one add-on (AddonPlan) or return a Refusal. Writes nothing."""
    plan, _payload = _plan_addon(Path(project), name, platform or sys.platform, claude_home, plugin_root,
                                 provider)
    return plan


def apply_addon(
    project: Path,
    name: str,
    expect_sha256: str,
    platform: Optional[str] = None,
    claude_home: Optional[Path] = None,
    plugin_root: Optional[Path] = None,
    provider: str = "claude",
) -> Dict[str, Any]:
    """Install one add-on: copy its missing files, then merge its rows into the project's settings.json.

    The previewed plan hash must still match. Every check runs before the first write. The hook files are
    copied before the rows are written, so a row never points at a file that is not there. A backup of
    settings.json is taken and the file is replaced atomically. Nothing is ever removed or overwritten.
    """
    project = Path(project)
    platform = platform or sys.platform
    plan, payload = _plan_addon(project, name, platform, claude_home, plugin_root, provider)
    if _is_refusal(plan):
        return plan
    target = Path(plan["target"])
    if expect_sha256 != plan["plan-sha256"]:
        return refusal("changed-since-preview",
                       "what would be written changed since it was previewed (settings.json, the add-on's "
                       "files in the project or in the plugin differ); run the preview again", target)
    copies = [o for o in payload["ops"] if o["action"] == "copy"]
    if not copies and not payload["to-add"]:
        return {"status": "nothing-to-do", "target": str(target), "add-on": name}
    if payload["to-add"]:
        launcher = "py" if platform == "win32" else "python3"
        if not shutil.which(launcher):
            return refusal("interpreter-not-found", "%s is not on PATH; a missing program fails open silently"
                           % launcher, target)
        if os.path.islink(str(target)):
            return refusal("write-failed", "%s is a symbolic link; the apply would replace the link or write "
                           "through it, so nothing was written. Edit the file it points to by hand" % target.name,
                           target)
        try:
            current = target.read_bytes() if target.is_file() else None
        except OSError as exc:
            return refusal("project-unreadable", "settings.json cannot be read: %s" % exc, target)
        if current != payload["old-bytes"]:
            return refusal("changed-since-preview", "settings.json changed while the apply was running", target)
    for op in copies:
        if os.path.lexists(str(op["dest"])):
            return refusal("changed-since-preview", "%s appeared while the apply was running; nothing more "
                           "was written" % op["path"], op["dest"])
    copied: List[str] = []
    for op in copies:
        error = _atomic_write(op["dest"], op["data"])
        if error:
            return refusal("write-failed", "%s could not be written: %s (copied so far: %s)"
                           % (op["path"], error, ", ".join(copied) or "none"), op["dest"])
        copied.append(op["path"])
    result: Dict[str, Any] = {"status": "applied", "target": str(target), "add-on": name,
                              "copied": copied, "added": len(payload["to-add"]), "backup": None,
                              "new-session-note": NEW_SESSION_NOTE}
    if not payload["to-add"]:
        return result
    old_bytes = payload["old-bytes"]
    backup: Optional[Path] = None
    try:
        if old_bytes is not None:
            backup = _backup_write(target, old_bytes)
    except OSError as exc:
        return refusal("write-failed", "the backup could not be written: %s (files copied: %s)"
                       % (exc, ", ".join(copied) or "none"), target)
    error = _atomic_write(target, payload["new-bytes"])
    if error:
        if backup is not None:
            try:
                backup.unlink()  # the original is untouched, so the backup would only be clutter
            except OSError:
                pass
        return refusal("write-failed", "settings.json could not be replaced: %s (files copied: %s)"
                       % (error, ", ".join(copied) or "none"), target)
    result.update({"backup": str(backup) if backup else None,
                   "rollback": ("copy %s over %s" % (backup, target)) if backup else "delete %s" % target,
                   "gitignore-hint": ".claude/settings.json.bak-*"})
    return result


# =======================================================================================
# Command line
# =======================================================================================

def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the ``profile``, ``hooks`` and ``addon`` subcommands."""
    parser = argparse.ArgumentParser(
        prog="auto_improve_finish_install.py",
        description="Finish Quick start steps 4 (profile) and 5 (hooks), or install an opt-in add-on.",
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project", default=".", help="project root (default: .)")
    common.add_argument("--json", action="store_true", help="machine-readable output")
    common.add_argument("--apply", action="store_true", help="write instead of preview")
    common.add_argument("--expect-sha256", default=None, help="profile: source-sha256 of the preview; hooks: its plan-sha256")
    common.add_argument("--claude-home", default=None, help="Claude home (default: ~/.claude)")

    sub = parser.add_subparsers(dest="command", required=True)

    profile = sub.add_parser("profile", parents=[common], help="step 4: project profile")
    profile.add_argument(
        "--set", action="append", default=[], metavar="SLOT=VALUE[,VALUE]",
        help="confirmed value for one placeholder slot (repeatable)",
    )

    hooks = sub.add_parser("hooks", parents=[common], help="step 5: hook registrations")
    hooks.add_argument("--skip", action="append", default=[], metavar="HOOK",
                       help="leave this hook out (repeatable)")
    hooks.add_argument("--platform", default=None, help="override sys.platform (tests)")
    hooks.add_argument("--provider", choices=PROVIDERS, default="claude")

    addon = sub.add_parser("addon", parents=[common], help="install one opt-in add-on")
    addon.add_argument("--name", required=True, help="the add-on to install (a folder under .claude/addons/)")
    addon.add_argument("--platform", default=None, help="override sys.platform (tests)")
    addon.add_argument("--provider", choices=PROVIDERS, default="claude")
    return parser


def _render_text(result: Result) -> str:
    """A short human rendering of a result."""
    if _is_refusal(result):
        return "REFUSED %s: %s\n  path: %s" % (result["code"], result["message"], result["path"])
    out = ["status: %s" % result.get("status")]
    for p in result.get("proposals", []):
        out.append("  %-26s %-14s %s" % (p["slot"], p["basis"], ", ".join(p["values"])))
    if "ready" in result:
        out.append("ready: %s  (%s)" % (result["ready"], result.get("verdict")))
        out += ["  %s: %s" % (c["name"], "ok" if c["ok"] else "FAILED") for c in result.get("checks", [])]
    for item in result.get("files", []):
        out.append("  file %-60s %s" % (item["path"], item["action"]))
    if "copied" in result:
        out.append("copied: %s" % (", ".join(result["copied"]) or "none"))
    if "to-add" in result:
        out.append("to add: %d, already present: %d" % (len(result["to-add"]), len(result["already-present"])))
    out += ["note: " + n for n in result.get("notes", [])]
    if result.get("unified-diff"):
        out.append(result["unified-diff"])
    if result.get("new-session-note"):
        out.append(result["new-session-note"])
    return "\n".join(out)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run a subcommand, print its result, and return 0, 2 (correctable) or 3 (environment)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    project = Path(args.project)
    home = Path(args.claude_home) if args.claude_home else None
    if args.command == "profile":
        if args.apply:
            sets: Dict[str, str] = {}
            for item in args.set:
                slot, sep, value = item.partition("=")
                if not sep:
                    parser.error("--set needs SLOT=VALUE, got %r" % item)
                sets[slot.strip()] = value
            result = apply_profile(project, sets, args.expect_sha256 or "", home)
        else:
            result = propose_profile(project, home)
    elif args.command == "addon":
        if args.apply:
            result = apply_addon(project, args.name, args.expect_sha256 or "", args.platform, home,
                                 provider=args.provider)
        else:
            result = plan_addon(project, args.name, args.platform, home, provider=args.provider)
    elif args.apply:
        result = apply_hooks(project, args.expect_sha256 or "", args.skip, args.platform, args.provider, home)
    else:
        result = plan_hooks(project, args.platform or sys.platform, args.provider, home, skip=args.skip)
    print(json.dumps(result, indent=2) if args.json else _render_text(result))
    return EXIT_CLASS[result["code"]] if _is_refusal(result) else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
