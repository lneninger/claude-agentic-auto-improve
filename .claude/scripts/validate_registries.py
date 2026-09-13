#!/usr/bin/env python3
"""
validate_registries.py -- scan MECHANISMS.md and VOCABULARY.md for dead links.

Walks each entry, extracts `src/...` and `path/to/file.ext` references,
and reports entries whose referenced files no longer exist. Helps keep
the reusable mechanism registry from rotting as the codebase evolves.

Resolution rules:
    * Backticked paths inside an entry are extracted verbatim.
    * Paths are resolved against a set of candidate roots:
        - cwd (the repo you're currently in)
        - every sibling of .claude/concepts that looks like
          a repo root (has a CLAUDE.md or .sln file)
        - any explicit --root passed on the command line
    * A path is considered "alive" if it resolves under any candidate root.

Usage:
    py -3 validate_registries.py [--root <repo-path>] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from _claude_paths import concepts_roots, first_populated_dir, project_dir, registry

# See the note in list_contracts.py: cp1252 consoles cannot encode the arrows
# and em-dashes quoted from registry context lines. Latent until this script
# actually resolved a populated registry (#35).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass


def mechanisms_file() -> Path:
    return registry("MECHANISMS.md")


def vocabulary_file() -> Path:
    return registry("VOCABULARY.md")


def concepts_root() -> Path:
    return first_populated_dir(concepts_roots(), "*.md")

# Regex for backticked paths that look like file paths (contain / or \ and a file extension).
BACKTICK_PATH = re.compile(r"`([^`]+?\.[a-zA-Z0-9]{1,8})`")


def find_candidate_roots(extra_roots: list[str]) -> list[Path]:
    """Build a list of candidate repo roots to resolve registry paths against."""
    roots: list[Path] = []

    # cwd
    roots.append(Path.cwd())

    # Each folder under .claude/concepts implies a repo named <project>.
    # The resolved project root is an explicit FIRST candidate. Under the flat
    # repo layout the old "every child of concepts/ is a project name"
    # inference is degenerate -- it yielded no usable root at all (#35).
    # Seed with the checkout the RESOLVER actually selected, not only with
    # $CLAUDE_PROJECT_DIR. That variable is unset in every plain shell, which
    # is exactly how /validate-registries is invoked -- so this used to fall
    # back to Path.cwd() alone and report every reference dead from any
    # subdirectory (118/144 resolving from the repo root, 0/144 from src),
    # exit 1 in both cases. concepts_root() is <checkout>/.claude/concepts,
    # so the checkout is two levels up. Follow-up to work item #35.
    concepts = concepts_root()
    for anchor in (project_dir(), concepts.parent.parent):
        if anchor is not None and anchor.is_dir() and anchor not in roots:
            roots.append(anchor)
    if concepts.exists():
        for project_dir_entry in concepts.iterdir():
            if not project_dir_entry.is_dir():
                continue
            # Common install locations on Windows
            for parent_hint in [
                Path("d:/Dev/HIPALANET") / project_dir_entry.name,
                Path("c:/Dev") / project_dir_entry.name,
                Path.home() / "Dev" / project_dir_entry.name,
                Path.home() / "src" / project_dir_entry.name,
                Path.home() / "code" / project_dir_entry.name,
            ]:
                if parent_hint.exists():
                    roots.append(parent_hint)

    for r in extra_roots:
        p = Path(os.path.expanduser(r))
        if p.exists():
            roots.append(p)

    # Drop any candidate that sits INSIDE another candidate. A registry
    # reference is repo-relative, so resolving `.claude/hooks/x.py` against
    # `<repo>/src` would look for `<repo>/src/.claude/hooks/x.py` -- never
    # correct, and it only ever appears here because the process happened to
    # start in a subdirectory. Removing it also makes this report reproducible:
    # the same command from the repo root and from a subdirectory now prints
    # the same candidate list, which is what the cross-directory test asserts.
    pruned: list[Path] = []
    for candidate in roots:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if any(
            resolved != other and resolved.is_relative_to(other)
            for other in (o.resolve() for o in roots if o is not candidate)
        ):
            continue
        if resolved not in pruned:
            pruned.append(resolved)
    roots = pruned

    # Deduplicate while preserving order
    seen: set[Path] = set()
    deduped: list[Path] = []
    for r in roots:
        try:
            resolved = r.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(resolved)
    return deduped


def resolve_path(entry: str, roots: list[Path]) -> Path | None:
    """Return the first existing resolution of `entry` under any candidate root."""
    candidate = Path(os.path.expanduser(entry))
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    for root in roots:
        full = root / candidate
        if full.exists():
            return full
    return None


def extract_entries(file_path: Path) -> list[tuple[int, str, str]]:
    """
    Return (line_number, referenced_path, entry_text) for every backticked
    file-like path in the registry file. Markdown code fences are skipped.
    """
    entries: list[tuple[int, str, str]] = []
    if not file_path.exists():
        return entries
    in_fence = False
    for i, line in enumerate(file_path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for m in BACKTICK_PATH.finditer(line):
            candidate = m.group(1).strip()
            # Filter out obvious non-paths: no slash or dot without directory, purely
            # code-ish stuff like `Result<T>` or `.Success(data)`.
            if "/" not in candidate and "\\" not in candidate:
                continue
            # Skip type-signature-looking things
            if candidate.startswith(".") or candidate.endswith("."):
                continue
            entries.append((i, candidate, stripped))
    return entries


def validate(registry_file: Path, roots: list[Path]) -> dict[str, Any]:
    entries = extract_entries(registry_file)
    alive: list[dict[str, Any]] = []
    dead: list[dict[str, Any]] = []
    for lineno, ref, context in entries:
        resolved = resolve_path(ref, roots)
        record = {
            "line": lineno,
            "reference": ref,
            "context": context[:120],
        }
        if resolved is not None:
            record["resolved"] = str(resolved)
            alive.append(record)
        else:
            dead.append(record)
    return {
        "file": str(registry_file),
        "total": len(entries),
        "alive": len(alive),
        "dead": len(dead),
        "dead_entries": dead,
    }


def print_report(mechanisms: dict[str, Any], vocabulary: dict[str, Any], roots: list[Path]) -> None:
    bar = "=" * 72
    print()
    print(bar)
    print("  Registry Validation Report")
    print(bar)
    print("  Candidate repo roots checked:")
    for r in roots:
        print(f"    - {r}")
    print()

    for label, report, source in [
        ("MECHANISMS.md", mechanisms, mechanisms_file()),
        ("VOCABULARY.md", vocabulary, vocabulary_file()),
    ]:
        total = report["total"]
        dead = report["dead"]
        alive = report["alive"]
        # A registry we could not read is UNKNOWN, never OK. Fail-open means a
        # NEUTRAL result, not an affirmative pass: "[OK] 0/0 references resolve,
        # 0 dead" is a health claim for work that never happened, and it is
        # indistinguishable from a genuinely clean run. That false green is how
        # this script reported everything fine for a year while resolving
        # nothing at all (work item #35, INV-3).
        if not source.is_file():
            print(f"  [SKIP] {label}: not found at any Claude data root -- nothing validated")
            print(f"         preferred candidate was {source}")
            continue
        status_icon = "OK" if dead == 0 else "FAIL"
        print(f"  [{status_icon}] {label}: {alive}/{total} references resolve, {dead} dead")
        print(f"         source: {source}")
        if dead:
            print()
            for entry in report["dead_entries"]:
                print(f"    * line {entry['line']:>4}: {entry['reference']}")
                print(f"      context: {entry['context']}")
            print()
    print(bar)
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate MECHANISMS.md and VOCABULARY.md references.")
    parser.add_argument("--root", action="append", default=[], help="Extra repo root to resolve paths under")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    roots = find_candidate_roots(args.root)

    mechanisms = validate(mechanisms_file(), roots)
    vocabulary = validate(vocabulary_file(), roots)

    if args.json:
        print(json.dumps({
            "roots": [str(r) for r in roots],
            "mechanisms": mechanisms,
            "vocabulary": vocabulary,
        }, indent=2))
    else:
        print_report(mechanisms, vocabulary, roots)

    # Exit 1 if any dead references found
    return 1 if (mechanisms["dead"] + vocabulary["dead"]) > 0 else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print(f"[validate-registries] error: {e}", file=sys.stderr)
        sys.exit(2)
