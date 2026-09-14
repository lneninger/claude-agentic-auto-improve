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
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass
from glob import glob
from pathlib import Path
from typing import Any, Dict, List, Optional


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
                "the only file you must author; the loop reads its implementers and review-gates slots",
                source=".claude/project-profile.md", authored=True),
    Requirement(".claude/area-mapping.json", "scaffold",
                "maps changed paths to areas, for the contract-critic accuracy system",
                authored=True),
    Requirement(".claude/work-item-conventions.json", "scaffold",
                "issue and pull request title conventions, shared by /task and /ship",
                authored=True),
    Requirement(".claude/settings.json", "manual",
                "registering the hooks turns enforcement on; that is your decision, not this script's"),
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
            "effortTypes": []
        },
        "prTitle": {"map": [], "order": []},
        "issueLink": {
            "closingKeyword": "Closes",
            "referenceKeyword": "Refs",
            "sameRepoFormat": "#<n>",
            "absentIdTokens": ["none"],
            "unresolvedIdTokens": ["unknown", "tbd"],
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


def find_plugin_root(explicit: Optional[str] = None) -> Optional[Path]:
    """Where the plugin's own tree is, under either install mode.

    The same order the skills use: an explicit path, then the vendored copy, then
    the environment's plugin root, then the provider cache.
    """
    if explicit:
        p = Path(explicit)
        return p if p.is_dir() else None
    here = Path(__file__).resolve().parent.parent.parent   # .../<root>
    candidates = [here]
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        candidates.append(Path(env))
    candidates += [Path(p) for p in
                   glob(str(Path.home() / ".claude/plugins/cache/*/agentic-auto-improve/*"))]
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


def main() -> int:
    ap = argparse.ArgumentParser(description="Create what this project is missing for the plugin.")
    ap.add_argument("--fix", action="store_true", help="create what is safe; without it, report only")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--project", default=".", help="the project root (default: here)")
    ap.add_argument("--plugin", default=None, help="the plugin root, if it cannot be found")
    args = ap.parse_args()

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
            print(f"  left alone     {p}  - writing it would change behaviour without asking")
        for p in report["unresolved"]:
            print(f"  UNRESOLVED     {p}")
        if not any(report[k] for k in ("created", "needs_authoring", "left_to_you", "unresolved")):
            print("  nothing to do")
    return 0


if __name__ == "__main__":
    sys.exit(main())
