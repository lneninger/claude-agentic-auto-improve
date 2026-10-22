"""Fail when a change to shipped plugin files does not raise the plugin version (CLAUDE.md rule).

Usage: ``py -3 .claude/scripts/check_version_bump.py [--base origin/master]``

Exit 0: no shipped file changed, or the version was raised and the five manifest entries agree.
Exit 1: shipped files changed without a higher version, or the manifests disagree.
Exit 2: the check could not run (never an allow).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import List, Optional, Tuple

MANIFESTS = ("plugin.json", ".claude-plugin/plugin.json", ".cursor-plugin/plugin.json",
             ".claude-plugin/marketplace.json")
EXEMPT_PREFIXES = (".claude/work-items/", ".claude/scripts/tests/", ".github/", ".claude/concepts/",
                   ".claude/north-stars/", ".claude/registries/", ".claude/orchestrator/results/",
                   ".claude/reviews/")
EXEMPT_NAMES = ("CLAUDE.md", "README.md", "CONTRIBUTING.md", "LICENSE", ".gitignore")


def is_shipped(path: str) -> bool:
    """True when ``path`` is a file the plugin ships, so changing it needs a version bump."""
    if path in MANIFESTS or path in EXEMPT_NAMES or path.endswith(".md") and "/" not in path:
        return False
    return not path.startswith(EXEMPT_PREFIXES)


def parse_version(text: str) -> Optional[Tuple[int, ...]]:
    try:
        return tuple(int(p) for p in text.split("."))
    except (ValueError, AttributeError):
        return None


def versions_in(manifests: dict) -> List[str]:
    """Every version string in the manifests, in file order (marketplace holds two)."""
    found: List[str] = []
    for name in MANIFESTS:
        data = json.loads(manifests[name])
        if "version" in data:
            found.append(data["version"])
        for entry in data.get("plugins", []) if isinstance(data.get("plugins"), list) else []:
            if "version" in entry:
                found.append(entry["version"])
    return found


def evaluate(changed: List[str], base_versions: List[str], head_versions: List[str]) -> Tuple[int, str]:
    shipped = [p for p in changed if is_shipped(p)]
    if not shipped:
        return 0, "no shipped plugin file changed; no version bump needed"
    if len(set(head_versions)) != 1:
        return 1, "the manifests disagree on the version: %s" % ", ".join(head_versions)
    head, base = parse_version(head_versions[0]), parse_version(base_versions[0] if base_versions else "")
    if head is None or base is None:
        return 2, "a version could not be read (base %s, head %s)" % (base_versions, head_versions)
    if head <= base:
        return 1, ("shipped files changed (%s) but the plugin version is still %s; raise it in all manifests"
                   % (", ".join(shipped[:3]), head_versions[0]))
    return 0, "version raised to %s" % head_versions[0]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="origin/master")
    args = parser.parse_args(argv)
    try:
        changed = [ln for ln in _git("diff", "--name-only", args.base + "...HEAD").splitlines() if ln]
        base = {m: _git("show", "%s:%s" % (args.base, m)) for m in MANIFESTS}
        head = {m: _git("show", "HEAD:" + m) for m in MANIFESTS}
        code, message = evaluate(changed, versions_in(base), versions_in(head))
    except (subprocess.CalledProcessError, OSError, ValueError, KeyError) as exc:
        code, message = 2, "the version check could not run: %s" % exc
    print("VERSION BUMP: " + message)
    return code


if __name__ == "__main__":
    sys.exit(main())
