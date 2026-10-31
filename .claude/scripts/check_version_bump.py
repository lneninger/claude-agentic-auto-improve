"""Fail when a change to shipped plugin files does not raise the plugin version (CLAUDE.md rule).

Usage: ``py -3 .claude/scripts/check_version_bump.py [--base origin/master] [--default-branch master]
[--head-ref task/<slug>/<id>]``, or ``--exact`` / ``--raise`` (the landing of a parent-branch contract).

Modes: default (today's check); parent (a ``task/<slug>/<id>`` head into a non-default base must NOT raise: its
version equals the base's, or the one at merge-base(origin/<default>, HEAD)); exact (minor + 1, patch 0,
relative to origin/<default>, all entries agree); ``--raise`` writes that exact version into every manifest and commits it.

A head that is not ``task/*`` into a non-default base is not checked (exit 0); default-branch bases keep the default rules.

Exit 0: no shipped file changed, or the version was raised and the five manifest entries agree.
Exit 1: shipped files changed without a higher version, or the manifests disagree.
Exit 2: the check could not run (never an allow).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import List, Optional, Tuple

MANIFESTS = ("plugin.json", ".claude-plugin/plugin.json", ".cursor-plugin/plugin.json",
             ".claude-plugin/marketplace.json")
# A file plugin_doctor copies into user projects is shipped, so it must not be listed here;
# enforced by test_check_version_bump.py.
EXEMPT_PREFIXES = (".claude/work-items/", ".claude/scripts/tests/", ".github/", ".claude/concepts/",
                   ".claude/north-stars/", ".claude/orchestrator/results/",
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


TASK_HEAD = re.compile(r"^task/[^/]+/.+")
VERSION_FIELD = re.compile(r'("version"\s*:\s*")[^"]*(")')


def evaluate_parent(head_versions: List[str], allowed_versions: List[str]) -> Tuple[int, str]:
    """A sub-task pull request into a parent branch never raises: head == base's or merge-base's version."""
    if len(set(head_versions)) != 1:
        return 1, "the manifests disagree on the version: %s" % ", ".join(head_versions)
    if head_versions[0] in allowed_versions:
        return 0, "sub-task pull request keeps version %s; the landing raises it" % head_versions[0]
    return 1, ("a sub-task pull request must not raise the plugin version (head %s, allowed %s); "
               "the landing raises it once" % (head_versions[0], ", ".join(sorted(set(allowed_versions)))))


def exact_version(default_versions: List[str]) -> Optional[str]:
    """The landing version for a default branch at ``default_versions``: minor + 1, patch 0."""
    parsed = [parse_version(v) for v in default_versions]
    if not parsed or any(p is None or len(p) != 3 for p in parsed):
        return None
    major, minor, _patch = max(parsed)
    return "%d.%d.0" % (major, minor + 1)


def evaluate_exact(default_versions: List[str], head_versions: List[str]) -> Tuple[int, str]:
    wanted = exact_version(default_versions)
    if wanted is None:
        return 2, "a version could not be read (default branch %s)" % default_versions
    if len(set(head_versions)) != 1:
        return 1, "the manifests disagree on the version: %s" % ", ".join(head_versions)
    if head_versions[0] != wanted:
        return 1, "the landing version must be exactly %s (minor + 1, patch 0), found %s" % (wanted, head_versions[0])
    return 0, "version is exactly %s" % wanted


def raise_manifests(wanted: str) -> bool:
    """Rewrite every ``"version"`` field of every manifest to ``wanted`` (byte-preserving otherwise) and commit
    it, so ``--exact`` and a later merge see it. Returns False, committing nothing, when already at ``wanted``."""
    changed = False
    for name in MANIFESTS:
        with open(name, encoding="utf-8", newline="") as handle:
            text = handle.read()
        updated = VERSION_FIELD.sub(lambda m: m.group(1) + wanted + m.group(2), text)
        if updated != text:
            changed = True
            with open(name, "w", encoding="utf-8", newline="") as handle:
                handle.write(updated)
    if changed:
        _git("add", "--", *MANIFESTS)
        _git("commit", "-q", "--no-verify", "-m", "chore: raise the plugin version to %s at the landing" % wanted, "--", *MANIFESTS)
    return changed


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="origin/master")
    parser.add_argument("--default-branch", default="master")
    parser.add_argument("--head-ref", default="")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--exact", action="store_true")
    modes.add_argument("--raise", dest="raise_version", action="store_true")
    args = parser.parse_args(argv)
    args.default_branch = args.default_branch.strip()  # one value for the ref and the check
    if not args.default_branch:
        # origin/ would make every base "non-default" and skip the check: the check could not run, never an allow.
        print("VERSION BUMP: the default branch is unknown (--default-branch is empty)")
        return 2
    default_ref = "origin/" + args.default_branch
    try:
        if args.exact or args.raise_version:
            default = {m: _git("show", "%s:%s" % (default_ref, m)) for m in MANIFESTS}
            if args.raise_version:
                wanted = exact_version(versions_in(default))
                if wanted is None:
                    code, message = 2, "a version could not be read (default branch %s)" % versions_in(default)
                else:
                    raised = raise_manifests(wanted)
                    code, message = 0, "manifests %s %s" % ("raised to" if raised else "already at", wanted)
            else:
                head = {m: _git("show", "HEAD:" + m) for m in MANIFESTS}
                code, message = evaluate_exact(versions_in(default), versions_in(head))
            print("VERSION BUMP: " + message)
            return code
        if args.head_ref and not TASK_HEAD.match(args.head_ref) and args.base != default_ref:
            print("VERSION BUMP: %s is not a task branch and its base is not %s; not checked" % (args.head_ref, default_ref))
            return 0
        if args.head_ref and TASK_HEAD.match(args.head_ref) and args.base != default_ref:
            merge_base = _git("merge-base", default_ref, "HEAD").strip()
            allowed: List[str] = []
            for ref in (args.base, merge_base):
                allowed += versions_in({m: _git("show", "%s:%s" % (ref, m)) for m in MANIFESTS})
            head = {m: _git("show", "HEAD:" + m) for m in MANIFESTS}
            code, message = evaluate_parent(versions_in(head), allowed)
            print("VERSION BUMP: " + message)
            return code
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
