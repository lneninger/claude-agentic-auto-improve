"""
derive_area.py -- contract -> sentinel-path bucket derivation.

Used by:
    - /design-first Step 2.5a (skip-eligibility check)
    - critic-verdict-tracker hook (update which buckets get a clean run credit)
    - accuracy_update.py (resolve buckets when a bad-plan signal fires)

Bucket semantics: a contract's area set is the UNION of every match across
its 'Files to touch' entries. Skip is offered only when ALL areas in the
union are skip-eligible.

CLI usage:
    py -3 derive_area.py <contract-path>
        -> prints one bucket per line (empty output = "uncategorized")
    py -3 derive_area.py --dump-mapping
        -> prints the loaded area-mapping.json (debug)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Local import: same directory.
sys.path.insert(0, str(Path(__file__).parent))
from _contract_files import extract_files_from_contract, matches_path

from _claude_paths import area_mapping_path

FALLBACK_AREA = "uncategorized"


def load_area_mapping(path: Path | None = None) -> dict[str, list[str]]:
    """
    Load area-mapping.json and return a flat {area_slug: [patterns]} dict.

    Returns an empty dict if the file is missing or unparseable -- callers
    must treat empty mapping as "no buckets known" (critic always runs).

    ``path`` is resolved at CALL time, never bound as a default argument: a
    default is evaluated at import, which is what made this unfixable from a
    test and blind to the repo layout (work item #35, INV-2).
    """
    if path is None:
        path = area_mapping_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    raw_areas = data.get("areas", {})
    flat: dict[str, list[str]] = {}
    for slug, body in raw_areas.items():
        if not isinstance(body, dict):
            continue
        patterns = body.get("patterns", [])
        if not isinstance(patterns, list):
            continue
        flat[slug] = [p for p in patterns if isinstance(p, str) and p]
    return flat


def derive_areas(contract_path: Path, mapping: dict[str, list[str]] | None = None) -> list[str]:
    """
    Return the sorted list of area slugs the contract belongs to.

    - Reads 'Files to touch' via the shared _contract_files parser.
    - Each entry is matched against every bucket's patterns; ALL matching
      buckets are collected (union semantics).
    - If no entry matches any bucket: returns [FALLBACK_AREA].
    - If the contract has no 'Files to touch' section at all: returns [].
      (Callers treat [] as 'unknown -- critic always runs', distinct from
      [FALLBACK_AREA] which means 'known to be uncategorized'.)
    """
    if mapping is None:
        mapping = load_area_mapping()

    entries = extract_files_from_contract(contract_path)
    if not entries:
        return []

    matched: set[str] = set()
    for entry in entries:
        for slug, patterns in mapping.items():
            if slug in matched:
                continue
            for pat in patterns:
                # Patterns in area-mapping.json are already lowercase; entries
                # come pre-normalized from extract_files_from_contract.
                if matches_path(pat.lower(), entry):
                    matched.add(slug)
                    break

    if not matched:
        return [FALLBACK_AREA]
    return sorted(matched)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("contract", nargs="?", help="Path to a concept contract")
    p.add_argument("--dump-mapping", action="store_true", help="Print the loaded area-mapping.json")
    args = p.parse_args(argv)

    if args.dump_mapping:
        mapping = load_area_mapping()
        print(json.dumps(mapping, indent=2))
        return 0

    if not args.contract:
        p.error("contract path required (or --dump-mapping)")
        return 2

    path = Path(args.contract).expanduser()
    if not path.exists():
        print(f"error: contract not found: {path}", file=sys.stderr)
        return 1

    areas = derive_areas(path)
    for a in areas:
        print(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
