#!/usr/bin/env python3
"""
registry_migrate.py -- the registry layout gate and the numbered registry migrations.

    registry_migrate.py --check   --project <root>
    registry_migrate.py --dry-run --project <root> [--plugin-root <path>]
    registry_migrate.py --apply   --project <root> --expect-sha256 <hash> [--plugin-root <path>]

``--check`` prints the layout state as JSON and exits 0 (current, absent), 6 (pending, stale-sync) or 2 (unknown, or
the registries could not be read). It is the gate the sync tool calls.

``--dry-run`` plans the next migration (0001: layout 1 or a stale sync -> layout 2), checks that it loses nothing
(I-12) and prints the plan hash and the report; it writes nothing under ``.claude/registries/``. ``--apply`` recomputes
the plan and writes only when its hash equals ``--expect-sha256``.

Order of checks (contract "Preview / apply migration"):
  (1) arguments and project; (2) layout state -- on ``current`` the plan is empty, the report is printed and the exit
  is 0, before any git check; (3) ``not-a-git-tree``, then ``uncommitted-registry-changes`` (git status of
  ``.claude/registries/`` only); (4) the plan, I-12, ``symlink-target``, and for ``--apply`` the hash compare;
  (5) stage every file, back it up under the report folder, replace, and restore everything on a failure.

A refusal (exit 3) leaves every registry file byte-identical and still writes the report. The report goes to
``<project>/.claude/cache/registry-migrations/0001-<UTC>/`` (``registry-migration-report.md``, ``report.json``,
``backup/``) and to standard output as JSON. ``--project`` is required: the script never guesses the project.

Refusal codes (exit 3): project-undetermined, not-a-git-tree, uncommitted-registry-changes, conflicting-entry,
unknown-layout, changed-since-preview, content-loss-detected, symlink-target, write-failed. Bad arguments exit 2, and
so does ``plan-build-failed`` (an exception while building the plan): the report is written with mode ``refused``,
the refusal code ``plan-build-failed`` and ``error`` set, and no registry file is touched.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))          # append: the scripts' own folder keeps its priority
TEMPLATES_DIR = SCRIPTS_DIR.parent / "templates" / "registries"

EXIT_OK = 0
EXIT_BAD = 2
EXIT_REFUSED = 3
EXIT_PENDING = 6
NUMBER = "0001"
REPORT_ROOT = Path(".claude") / "cache" / "registry-migrations"
REGISTRIES_REL = Path(".claude") / "registries"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def plan_hash(files: List[Any]) -> str:
    """``_plan_digest`` over b"registry-migration", b"0001", then per file in sorted POSIX path order: the path, the
    input bytes (or b"absent"), the planned output bytes."""
    from _preview_apply import _plan_digest
    parts: List[bytes] = [b"registry-migration", NUMBER.encode("ascii")]
    for f in sorted(files, key=lambda x: x.rel):
        parts += [f.rel.encode("utf-8"), f.before if f.before is not None else b"absent", f.after]
    return _plan_digest(*parts)


def _git(project: Path, *args: str) -> Tuple[int, str]:
    try:
        done = subprocess.run(["git", "-c", "core.quotepath=false", "-C", str(project), *args],
                              capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, str(exc)
    return done.returncode, done.stdout.decode("utf-8", "replace")


def _report_dir(project: Path) -> Path:
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = project / REPORT_ROOT
    folder = base / ("%s-%s" % (NUMBER, stamp))
    n = 1
    while folder.exists():
        n += 1
        folder = base / ("%s-%s-%d" % (NUMBER, stamp, n))
    return folder


def _resolve_plugin_root(project: Path, override: Optional[str]) -> Tuple[Optional[Path], str]:
    """(plugin root, "") or (None, reason) with the reason one of same-as-project, no-manifest, not-found."""
    import _plugin_root
    import _registry_layout as rl

    def needs(candidate: Path) -> bool:
        return all((candidate / ".claude" / "registries" / ("%s.md" % n)).is_file() for n in rl.REGISTRIES)

    root = _plugin_root.separate_plugin_root(project, Path(override) if override else None, needs=needs)
    if root is not None:
        return root, ""
    if override:
        candidates = [Path(override)]
    else:
        candidates = ([Path(os.environ["CLAUDE_PLUGIN_ROOT"])] if os.environ.get("CLAUDE_PLUGIN_ROOT") else [])
        candidates.append(Path(_plugin_root._SCRIPTS_DIR).parent.parent)
    for c in candidates:
        if c.is_dir() and _plugin_root._same_dir(c, project):
            return None, "same-as-project"
    for c in candidates:
        if c.is_dir() and not _plugin_root._manifest_names_plugin(c):
            return None, "no-manifest"
    return None, "not-found"


def _new_report(project: Path, state: Any) -> Dict[str, Any]:
    return {"number": NUMBER, "project": str(project), "mode": "dry-run", "refusal_code": "", "refusal_message": "",
            "plan_hash": "", "error": "", "plugin_root": "not-needed", "plugin_root_reason": "",
            "plugin_root_hint": "",
            "layout_state": state.as_dict(),
            "files": [], "report_dir": "", "registries": {}, "conflicts": []}


def render_markdown(report: Dict[str, Any]) -> str:
    out = ["# Registry migration %s" % report["number"], "",
           "- Project: `%s`" % report["project"], "- Mode: %s" % report["mode"],
           "- Layout state: %s" % report["layout_state"]["state"], "- Plan hash: `%s`" % report["plan_hash"],
           "- Plugin root: %s%s" % (report["plugin_root"],
                                    " (%s)" % report["plugin_root_reason"] if report["plugin_root_reason"] else "")]
    if report["refusal_code"]:
        out += ["- Refusal: **%s** -- %s" % (report["refusal_code"], report["refusal_message"])]
    if report.get("error"):
        out += ["- Error: %s" % report["error"]]
    if report.get("plugin_root_hint"):
        out += ["- Note: %s" % report["plugin_root_hint"]]
    out += ["", "## Files to write", ""] + (["- `%s`" % f for f in report["files"]] or ["- none"])
    for name, reg in report["registries"].items():
        c = reg["counts"]
        out += ["", "## %s" % name, "",
                "- Entries: %d in, %d kept, %d moved, %d merged away, %d out" % (
                    c["in"], c["kept"], c["moved"], c["merged_away"], c["out"])]
        for key, label in (("moved", "Moved"), ("merged_duplicates", "Merged duplicates"),
                           ("appended_merge_lines", "Appended merge lines"), ("unclassified", "Unclassified (to general)"),
                           ("token_entries_moved", "Token entries moved"),
                           ("plugin_owned_token_entries", "Plugin-owned token entries (kept)"),
                           ("unverified_token_entries", "Unverified token entries (kept; re-run with --plugin-root)"),
                           ("universal_candidates", "Universal candidates (kept)"),
                           ("unmovable_token_lines", "Unmovable token lines (kept)"), ("legacy_entries", "Legacy entries"),
                           ("leftovers", "Leftovers"), ("removed_lines", "Removed lines"), ("conflicts", "Conflicts")):
            items = reg[key]
            if items:
                out += ["", "### %s (%d)" % (label, len(items))]
                for item in items:
                    out.append("- %s" % (json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else item))
        if reg["bodiless_orphans"]:
            out += ["", "### Bodiless orphans (%d)" % len(reg["bodiless_orphans"]), ""]
            for o in reg["bodiless_orphans"]:
                out += ["- `%s` at %s: %s" % (o["key"], o["location"], o["hint"]), "  `%s`" % o["command"]]
    return "\n".join(out) + "\n"


class Run:
    """One invocation: the report, where it goes, and how it ends."""

    def __init__(self, project: Path, state: Any):
        self.project = project
        self.report = _new_report(project, state)
        self.folder = _report_dir(project)
        self.report["report_dir"] = str(self.folder)

    def finish(self, code: int, refusal: Optional[Tuple[str, str]] = None) -> int:
        if refusal is not None:
            self.report["mode"] = "refused"
            self.report["refusal_code"], self.report["refusal_message"] = refusal
        self._write_report()
        sys.stdout.write(json.dumps(self.report, indent=2, ensure_ascii=False) + "\n")
        if refusal is not None:
            sys.stderr.write("registry_migrate: %s: %s\n" % refusal)
        return code

    def _write_report(self) -> None:
        try:
            from _preview_apply import _atomic_write
            problems = [_atomic_write(self.folder / "report.json",
                                      (json.dumps(self.report, indent=2, ensure_ascii=False) + "\n").encode("utf-8")),
                        _atomic_write(self.folder / "registry-migration-report.md",
                                      render_markdown(self.report).encode("utf-8"))]
            for problem in problems:
                if problem:
                    sys.stderr.write("registry_migrate: the report could not be written: %s\n" % problem)
        except Exception as exc:  # the report never changes the outcome
            sys.stderr.write("registry_migrate: the report could not be written: %s\n" % exc)


def _is_symlinked(path: Path, project: Path) -> bool:
    p = Path(path)
    while True:
        try:
            if p.is_symlink():
                return True
        except OSError:
            return True
        if p == project or p.parent == p:
            return False
        p = p.parent


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="registry_migrate.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project", help="the project root (the folder holding .claude/); required")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="print the layout state; exit 0 / 6 / 2")
    mode.add_argument("--dry-run", action="store_true", help="plan the next migration and print the plan hash")
    mode.add_argument("--apply", action="store_true", help="apply the plan whose hash is --expect-sha256")
    p.add_argument("--expect-sha256", help="the plan hash of the dry-run (with --apply)")
    p.add_argument("--plugin-root", help="the installed plugin tree to read the plugin's Universal entries from")
    return p


def run(args: argparse.Namespace) -> int:
    if args.apply and not args.expect_sha256:
        build_parser().error("--apply needs --expect-sha256 (the plan hash a --dry-run printed)")
    if not args.project or not Path(args.project).is_dir():
        sys.stderr.write("registry_migrate: project-undetermined: --project must name an existing project folder "
                         "(got %r); the script never guesses the project\n" % (args.project or ""))
        return EXIT_REFUSED
    project = Path(args.project).resolve()
    os.environ["CLAUDE_PROJECT_DIR"] = str(project)
    try:
        import _registry_layout as rl
        import _preview_apply  # noqa: F401  (named here so a missing module is reported by name)
        import _plugin_root  # noqa: F401
        import registry_migrations
    except ImportError as exc:
        sys.stderr.write("registry_migrate: a module this script needs is missing: %s (%s)\n"
                         % (getattr(exc, "name", None) or exc, exc))
        return EXIT_BAD

    registries_dir = project / REGISTRIES_REL
    try:
        state = rl.layout_state(registries_dir)
    except Exception as exc:  # unreadable registries: could not check
        sys.stderr.write("registry_migrate: the registries could not be read: %s\n" % exc)
        return EXIT_BAD

    if args.check:
        sys.stdout.write(json.dumps(state.as_dict(), indent=2) + "\n")
        if state.state in ("current", "absent"):
            return EXIT_OK
        return EXIT_PENDING if state.state in ("pending", "stale-sync") else EXIT_BAD

    mode = "apply" if args.apply else "dry-run"
    job = Run(project, state)
    job.report["mode"] = mode

    # (2) layout state
    if state.state in ("unknown", "absent"):
        why = ", ".join(state.reasons) or state.state
        return job.finish(EXIT_REFUSED, ("unknown-layout", "the registry layout is %s (%s); %s" % (
            state.state, why, state.remedy)))
    if state.state == "current":
        job.report["plan_hash"] = plan_hash([])
        return job.finish(EXIT_OK)

    # plan (computed now so that every refusal can still report it; it writes nothing)
    migration = registry_migrations.migration_for(state.state)
    if migration is None:
        return job.finish(EXIT_REFUSED, ("unknown-layout", "no migration applies to the layout state %s" % state.state))
    plugin_root, reason = _resolve_plugin_root(project, args.plugin_root)
    tokens, allowed = rl.load_project_tokens(project)
    plugin_keys = rl.plugin_universal_keys(plugin_root) if plugin_root is not None else None
    job.report["plugin_root"] = str(plugin_root) if plugin_root is not None else "unverified"
    job.report["plugin_root_reason"] = reason
    if plugin_root is None:
        job.report["plugin_root_hint"] = ("no separate plugin root was found (%s): every project-token entry stays as "
                                          "unverified; re-run with --plugin-root <the installed plugin folder>" % reason)
    ctx = migration.Context(project=project, registries_dir=registries_dir, templates_dir=TEMPLATES_DIR,
                            plugin_keys=plugin_keys, tokens=tokens, allowed=allowed)
    try:
        plan = migration.build_plan(ctx)
    except Exception as exc:
        # N2: the report is still written; no registry file has been touched (the plan only reads).
        job.report.update({"files": [], "conflicts": [], "registries": {}, "plan_hash": "none",
                           "error": "%s: %s" % (type(exc).__name__, exc)})
        return job.finish(EXIT_BAD, ("plan-build-failed", "the plan could not be built: %s: %s"
                                     % (type(exc).__name__, exc)))
    job.report["registries"] = plan.registries
    job.report["conflicts"] = plan.conflicts
    job.report["files"] = [f.rel for f in plan.files]
    job.report["plan_hash"] = plan_hash(plan.files)

    # (3) git
    code, inside = _git(project, "rev-parse", "--is-inside-work-tree")
    if code != 0 or inside.strip() != "true":
        return job.finish(EXIT_REFUSED, ("not-a-git-tree", "%s is not inside a git work tree, so uncommitted registry "
                                         "changes cannot be ruled out" % project))
    code, status = _git(project, "status", "--porcelain", "--untracked-files=all", "--", str(REGISTRIES_REL).replace("\\", "/"))
    if code != 0:
        return job.finish(EXIT_REFUSED, ("not-a-git-tree", "git status failed: %s" % status.strip()))
    if status.strip():
        return job.finish(EXIT_REFUSED, ("uncommitted-registry-changes", "commit or stash these changes under "
                                         ".claude/registries/ first: %s" % "; ".join(status.strip().splitlines()[:8])))

    # (4) the plan, I-12, symlinks, the hash
    if plan.refusal is not None:
        return job.finish(EXIT_REFUSED, plan.refusal)
    lost = migration.verify_plan(plan)
    if lost is not None:
        return job.finish(EXIT_REFUSED, (getattr(lost, "code", "content-loss-detected"), str(lost)))
    for f in plan.files:
        if _is_symlinked(f.path, project):
            return job.finish(EXIT_REFUSED, ("symlink-target", "%s is, or sits below, a symbolic link; nothing was "
                                             "written" % f.rel))
    if mode == "dry-run":
        return job.finish(EXIT_OK)
    if job.report["plan_hash"] != args.expect_sha256.strip().lower():
        return job.finish(EXIT_REFUSED, ("changed-since-preview", "the plan hash is now %s, not the %s the dry-run printed; "
                                         "run --dry-run again" % (job.report["plan_hash"], args.expect_sha256)))

    # (5) stage, back up, replace
    from _preview_apply import stage_and_replace
    # base = the project root, so a backup lands at backup/.claude/registries/... (short, W2)
    result = stage_and_replace([(f.path, f.after) for f in plan.files], job.folder / "backup", base=project)
    if result.get("status") != "applied":
        return job.finish(EXIT_REFUSED, ("write-failed", str(result.get("message", "write failed"))))
    return job.finish(EXIT_OK)


def main(argv: Optional[list] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
