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

from _claude_paths import concepts_roots, first_populated_dir, project_dir, registry, registry_files

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


def registry_file_list(name: str) -> list[Path]:
    """Every file of one registry (root, then ``<STEM>/*.md``), or the preferred root path when none exists.

    The default mode reads the domain files of a layout-2 project through the resolver (same root as the root
    file, I-3). The fallback keeps the "[SKIP] ... not found" line for a registry that is not there at all.
    """
    return registry_files(name) or [registry(name)]


#: The heading that opens the migration leftovers of a domain file. Every line from it on is prose kept verbatim,
#: never an entry, so the default mode does not scan it. (Spelled here, not imported: the default mode must keep
#: working on a copy that lacks ``_registry_layout``.)
LEFTOVERS_HEADING = "## Migration 0001 leftovers (not parsed as entries)"

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
        if not in_fence and line.rstrip() == LEFTOVERS_HEADING:
            break
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


def file_label(source: Path, registry_name: str) -> str:
    """``MECHANISMS.md`` for the root file, ``MECHANISMS/backend.md`` for a domain file."""
    stem = registry_name[:-3] if registry_name.endswith(".md") else registry_name
    return registry_name if source.name == registry_name else f"{stem}/{source.name}"


def validate_all(registry_name: str, roots: list[Path]) -> list[dict[str, Any]]:
    """One ``validate`` block per file of a registry, in ``registry_files`` order, each tagged with its registry."""
    blocks: list[dict[str, Any]] = []
    for source in registry_file_list(registry_name):
        block = validate(source, roots)
        block["registry"] = registry_name
        blocks.append(block)
    return blocks


def aggregate(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """The pre-split JSON shape of one registry, summed over its files (``file`` is the first, the root file)."""
    return {
        "file": blocks[0]["file"],
        "total": sum(b["total"] for b in blocks),
        "alive": sum(b["alive"] for b in blocks),
        "dead": sum(b["dead"] for b in blocks),
        "dead_entries": [d for b in blocks for d in b["dead_entries"]],
    }


def print_report(mechanisms: list[dict[str, Any]], vocabulary: list[dict[str, Any]], roots: list[Path]) -> None:
    bar = "=" * 72
    print()
    print(bar)
    print("  Registry Validation Report")
    print(bar)
    print("  Candidate repo roots checked:")
    for r in roots:
        print(f"    - {r}")
    print()

    for registry_name, blocks in (("MECHANISMS.md", mechanisms), ("VOCABULARY.md", vocabulary)):
        for report in blocks:
            _print_block(file_label(Path(report["file"]), registry_name), report, Path(report["file"]))
    print(bar)
    print()


def _print_block(label: str, report: dict[str, Any], source: Path) -> None:
    """One file's block of the default report."""
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
        return
    status_icon = "OK" if dead == 0 else "FAIL"
    print(f"  [{status_icon}] {label}: {alive}/{total} references resolve, {dead} dead")
    print(f"         source: {source}")
    if dead:
        print()
        for entry in report["dead_entries"]:
            print(f"    * line {entry['line']:>4}: {entry['reference']}")
            print(f"      context: {entry['context']}")
        print()


def check_structure(args: argparse.Namespace) -> int:
    """``--check-structure``: the section 3.4 lint of the registry layout (R1-R6, A1).

    Exit 0 = nothing blocking (or the tree is not on layout 2 yet, where every finding is advisory),
    1 = a finding on a ``current`` tree, 2 = the check could not run (a new module is missing, or
    the project folder does not exist). The rules live in ``_registry_layout``; this function only
    resolves the folders, the project tokens and the plugin root.
    """
    try:
        import _registry_layout as layout
    except ImportError as exc:
        print(f"[validate-registries] --check-structure needs the module '_registry_layout', which is "
              f"missing or cannot be imported ({exc}). Copy the new registry modules from the plugin.",
              file=sys.stderr)
        return 2

    if args.project:
        project_root = Path(os.path.expanduser(args.project)).resolve()
        if not project_root.is_dir():
            print(f"[validate-registries] --project {args.project} is not a directory", file=sys.stderr)
            return 2
        registries_dir = project_root / ".claude" / "registries"
    else:
        registries_dir = mechanisms_file().parent
        project_root = registries_dir.parent.parent

    plugin_root = None
    try:
        from _plugin_root import _manifest_names_plugin, separate_plugin_root
        override = Path(os.path.expanduser(args.plugin_root)) if args.plugin_root else None
        plugin_root = separate_plugin_root(
            project_root, override,
            needs=lambda cand: all((cand / ".claude" / "registries" / f"{n}.md").is_file()
                                   for n in layout.REGISTRIES))
    except ImportError as exc:
        print(f"[validate-registries] --check-structure needs the module '_plugin_root' and the plugin "
              f"doctor to find the plugin root ({exc}).", file=sys.stderr)
        return 2

    tokens, allowed = layout.load_project_tokens(project_root)
    plugin_keys = layout.plugin_universal_keys(plugin_root) if plugin_root is not None else None
    report = layout.check_structure(registries_dir, project_root=project_root, plugin_root=plugin_root,
                                    plugin_keys=plugin_keys, tokens=tokens, allowed=allowed)
    # Q19 (a): a project that holds this plugin's own manifest IS the plugin source, and the installed copy that
    # resolves as "the plugin root" may be an older release that lacks its newest Universal entries. Drop only the
    # R3 universal-candidate advisories, and say so once. Token findings, plugin-owned, unverified and every other
    # result stay as they are (a vendored client that copied the manifest loses an advisory, never a finding).
    skipped = 0
    if _manifest_names_plugin(project_root):
        kept = [f for f in report.findings if not (f.rule == "R3" and f.variant == "universal-candidate")]
        skipped = len(report.findings) - len(kept)
        report.findings = kept
    lines = report.lines(strict=args.strict)
    if skipped:
        note = (f"advisory: R3 universal-candidate skipped: {skipped} entries; "
                "this project holds the plugin's own manifest")
        # before the notices (legacy / leftover) and the digest line, after the findings
        at = next((i for i, ln in enumerate(lines)
                   if ln.startswith(("advisory: legacy ", "advisory: leftover ", "digest:"))), len(lines))
        lines.insert(at, note)
    for line in lines:
        print(line)
    return report.exit_code(strict=args.strict)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate MECHANISMS.md and VOCABULARY.md references.")
    parser.add_argument("--root", action="append", default=[], help="Extra repo root to resolve paths under")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--check-structure", action="store_true",
                        help="Lint the registry layout (R1-R6, A1) instead of checking dead references")
    parser.add_argument("--project", help="With --check-structure: the project root (the folder holding .claude)")
    parser.add_argument("--strict", action="store_true",
                        help="With --check-structure: dead file references (R4) also fail a current tree")
    parser.add_argument("--plugin-root", help="With --check-structure: the plugin tree to read Universal keys from")
    args = parser.parse_args()

    if args.check_structure:
        return check_structure(args)

    roots = find_candidate_roots(args.root)

    # Every file of each registry: the root, then the domain files of a layout-2 project (W4).
    mechanisms_blocks = validate_all("MECHANISMS.md", roots)
    vocabulary_blocks = validate_all("VOCABULARY.md", roots)

    if args.json:
        print(json.dumps({
            "roots": [str(r) for r in roots],
            "mechanisms": aggregate(mechanisms_blocks),
            "vocabulary": aggregate(vocabulary_blocks),
            "files": mechanisms_blocks + vocabulary_blocks,
        }, indent=2))
    else:
        print_report(mechanisms_blocks, vocabulary_blocks, roots)

    # Exit 1 if any dead references found
    dead_total = sum(b["dead"] for b in mechanisms_blocks + vocabulary_blocks)
    return 1 if dead_total > 0 else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print(f"[validate-registries] error: {e}", file=sys.stderr)
        sys.exit(2)
