"""
cross_area_scan.py -- contract -> top-3 adjacent areas surfaced by three signals.

Used by:
    - data-architect agent Step 4.5 (populates the `## Adjacent Areas` section)
    - /cross-impact skill (user-invocable exploration)
    - contract-critic checklist item 11 BLOCKER text (cites the script output)

Signals (weights are additive; final score per candidate area = sum of weights):
    - CodeGraph signal (weight 3 per affected file mapped to an area):
        Shells out to the `codegraph` CLI if available; otherwise emits a
        warning to stderr and skips the signal. Each Files-to-touch entry is
        sent through `codegraph impact <path>`; the affected file list is
        mapped through derive_area.py's area patterns. Areas other than the
        contract's primary set get +3 per affected file (capped at +6 per
        area to prevent a noisy hub file from dominating).
    - JOURNAL co-occurrence (weight 2 per matching entry):
        Greps JOURNAL.md for entries whose Tags / title / Source contract
        path matches the contract's primary area slug. For each match,
        derives the source contract's area set; areas other than the
        contract's primary set get +2.
    - MECHANISMS co-citation (weight 1 per matching mechanism):
        For each mechanism the contract reuses (Reused Mechanisms section),
        greps MECHANISMS.md for the mechanism name. File path tokens in the
        mechanism's description are matched against area patterns; areas
        other than the contract's primary set get +1.

Output: top-3 areas with score >= 2 (the noise floor). One line per area:
    <area-slug>\t<score>\t<signal-breakdown>

Cache: <project>/.claude/cache/cross-area-scans/<contract-sha>.json (falls back
to ~/.claude/cache/ when CLAUDE_PROJECT_DIR is unset). Invalidated by
content hash. Subsequent calls on an unchanged contract are sub-100ms.

CLI usage:
    py -3 cross_area_scan.py <contract-path>
    py -3 cross_area_scan.py --files <comma-separated-paths>
    py -3 cross_area_scan.py <contract-path> --no-cache  (force refresh)
    py -3 cross_area_scan.py <contract-path> --json      (machine-readable output)

Exit codes:
    0  -- scan completed (output may be empty if no signal above threshold)
    1  -- contract not found / unreadable
    2  -- CLI argument error
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Local import: same directory.
sys.path.insert(0, str(Path(__file__).parent))
from _contract_files import extract_files_from_contract, matches_path
from derive_area import FALLBACK_AREA, derive_areas, load_area_mapping

from _claude_paths import area_mapping_path, cache_dir as _cache_root, registry

# Windows consoles default to cp1252, which cannot encode the arrows and
# dashes that appear in titles and registry excerpts. Applied to the whole
# class of printing scripts, not just the two that crashed first (#35).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass


# Call-time resolvers, never module-level constants: a constant is evaluated
# at import, which is what left this scanner reading an emptied ~/.claude and
# reporting "no adjacent areas" as if it were a finding (work item #35, INV-2).


def journal_path() -> Path:
    """The engineering journal, project-local first."""
    return registry("JOURNAL.md")


def mechanisms_path() -> Path:
    """The mechanism registry, project-local first."""
    return registry("MECHANISMS.md")


def journal_repo_root() -> Path:
    """The checkout that owns the journal we are reading.

    Relative paths recorded inside ``JOURNAL.md`` are repo-relative, so they
    must be anchored on the journal's own checkout rather than on whatever
    directory the process happens to be started from.

    ``registry()`` returns either ``<checkout>/.claude/registries/JOURNAL.md``
    (repo layout) or ``<root>/.claude/JOURNAL.md`` (global layout), so the
    number of levels to climb differs between the two.
    """
    p = journal_path()
    if p.parent.name == "registries":
        return p.parent.parent.parent
    return p.parent.parent


def cache_dir() -> Path:
    """This scanner's derived-result cache.

    Entries are keyed on contract text alone, but the scan's RESULT depends on
    this checkout's ``area-mapping.json`` and ``JOURNAL.md`` -- so the cache
    must live beside those inputs, not in a machine-wide directory that can
    serve one checkout's answer to another.
    """
    return _cache_root() / "cross-area-scans"

WEIGHT_CODEGRAPH = 3
WEIGHT_CODEGRAPH_CAP_PER_AREA = 6
WEIGHT_JOURNAL = 2
WEIGHT_SEED_ADJACENCY = 2  # Phase 6: user-curated high-confidence adjacency.
WEIGHT_MECHANISMS = 1      # Weakest signal -- noisy by nature.
THRESHOLD = 2
TOP_N = 3


@dataclass
class AreaScore:
    area: str
    score: int = 0
    breakdown: list[str] = field(default_factory=list)

    def add(self, signal: str, weight: int) -> None:
        self.score += weight
        self.breakdown.append(f"{signal}({weight})")


def content_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def load_cache(contract_text: str) -> dict | None:
    if not cache_dir().exists():
        return None
    h = content_hash(contract_text)
    cache_file = cache_dir() / f"{h}.json"
    if not cache_file.exists():
        return None
    try:
        return json.loads(cache_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_cache(contract_text: str, result: dict) -> None:
    cache_dir().mkdir(parents=True, exist_ok=True)
    h = content_hash(contract_text)
    cache_file = cache_dir() / f"{h}.json"
    try:
        cache_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except OSError:
        pass  # cache write failure is non-fatal


def codegraph_impact_files(file_paths: list[str]) -> tuple[list[str] | None, str | None]:
    """
    Return (affected_files, warning) for the given inputs.

    affected_files is None when the codegraph CLI is unavailable, [] when the
    CLI ran but produced no impact data (every invocation returned non-zero
    or empty payload -- the warning surfaces this), and a sorted list of
    forward-slash lowercase paths otherwise.
    """
    cli = shutil.which("codegraph")
    if not cli:
        return (None, "codegraph CLI not on PATH; skipping codegraph signal")

    affected: set[str] = set()
    attempts = 0
    failures = 0
    for path in file_paths:
        attempts += 1
        try:
            proc = subprocess.run(
                [cli, "impact", path, "--json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, OSError):
            failures += 1
            continue
        if proc.returncode != 0:
            failures += 1
            continue
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            failures += 1
            continue
        # Defensive: codegraph CLI shapes vary across versions. Try the two
        # most common shapes and fall back gracefully.
        candidates = []
        if isinstance(data, dict):
            candidates = data.get("affected_files") or data.get("files") or []
        elif isinstance(data, list):
            candidates = data
        for entry in candidates:
            if isinstance(entry, str):
                affected.add(entry.replace("\\", "/").lower())
            elif isinstance(entry, dict):
                p = entry.get("path") or entry.get("file") or entry.get("location")
                if isinstance(p, str):
                    affected.add(p.replace("\\", "/").lower())

    if attempts > 0 and failures == attempts:
        return (
            [],
            "codegraph CLI present but `impact` subcommand failed on all inputs "
            "(likely missing/renamed in this CLI version); skipping codegraph signal",
        )
    return (sorted(affected), None)


def journal_signal(primary_areas: set[str], mapping: dict[str, list[str]]) -> list[tuple[str, int, str]]:
    """
    Grep JOURNAL.md for entries whose Tags / title / Source contract slug
    matches any primary area slug. For each match, derive the source contract's
    area set; areas not in primary_areas get +WEIGHT_JOURNAL.

    Returns list of (area_slug, weight_added, signal_label).
    """
    if not journal_path().exists():
        return []

    try:
        text = journal_path().read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    # Split into entries: each entry starts with `### YYYY-MM-DD`.
    entries = re.split(r"(?m)^### \d{4}-\d{2}-\d{2}", text)[1:]
    contributions: list[tuple[str, int, str]] = []

    for entry_body in entries:
        # Does this entry mention any primary area? (Tag line, title, or Source contract path.)
        lower = entry_body.lower()
        if not any(area in lower for area in primary_areas):
            continue

        # Resolve Source contract -> derived areas.
        match = re.search(r"\*\*Source contract:\*\*\s*`([^`]+)`", entry_body)
        if not match:
            continue
        source_path_raw = match.group(1).strip()
        if source_path_raw.lower() in ("n/a", "na"):
            # Manual entry -- honor optional `Areas:` line if present.
            areas_line = re.search(r"\*\*Areas:\*\*\s*([^\n]+)", entry_body)
            if not areas_line:
                continue
            entry_areas = [a.strip().lower() for a in areas_line.group(1).split(",") if a.strip()]
        else:
            # A relative path stored INSIDE a data file resolves against that
            # file's own location, never against the process working directory.
            # Every real `Source contract:` entry in JOURNAL.md is relative
            # (`.claude/concepts/<slug>.md`). Resolving those against os.getcwd()
            # made the whole journal signal vanish when the scanner ran from any
            # subdirectory -- and, because save_cache() keys on the contract text
            # alone, the journal-blind answer was then served to later runs from
            # the correct directory. Follow-up to work item #35.
            source_path = Path(source_path_raw).expanduser()
            if not source_path.is_absolute():
                source_path = journal_repo_root() / source_path_raw
            if not source_path.exists():
                continue
            entry_areas = derive_areas(source_path, mapping)

        for area in entry_areas:
            if area in primary_areas or area == FALLBACK_AREA:
                continue
            if area not in mapping:
                continue
            contributions.append((area, WEIGHT_JOURNAL, "journal"))

    return contributions


def mechanisms_signal(
    contract_text: str,
    primary_areas: set[str],
    mapping: dict[str, list[str]],
) -> list[tuple[str, int, str]]:
    """
    For each mechanism cited in the contract's `## Reused Mechanisms` section,
    grep MECHANISMS.md for that mechanism. Each matching mechanism's description
    contains file path tokens; map those paths through mapping. Areas other than
    primary_areas get +WEIGHT_MECHANISMS per matching mechanism.

    Returns list of (area_slug, weight_added, signal_label).
    """
    if not mechanisms_path().exists():
        return []

    # Extract Reused Mechanisms section.
    reused_match = re.search(
        r"(?im)^## reused mechanisms\s*$(.*?)(?=^## |\Z)",
        contract_text,
        re.DOTALL,
    )
    if not reused_match:
        return []
    reused_text = reused_match.group(1)

    # Pull backticked mechanism names out of the reused section.
    mechanism_names = set()
    for m in re.finditer(r"`([A-Z][A-Za-z0-9_]+(?:<[^>]+>)?)`", reused_text):
        name = m.group(1).strip()
        if name and len(name) >= 3:
            mechanism_names.add(name)
    if not mechanism_names:
        return []

    try:
        mech_text = mechanisms_path().read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    # Split mechanisms into bullet-blocks. Each block typically starts with `- **Name**` or `### Name`.
    contributions: list[tuple[str, int, str]] = []
    for name in mechanism_names:
        # Find each mention of this mechanism in MECHANISMS.md, take the surrounding
        # ~500-char window as the "description", grep paths from it.
        pattern = re.compile(rf"\b{re.escape(name)}\b")
        for match in pattern.finditer(mech_text):
            start = max(0, match.start() - 200)
            end = min(len(mech_text), match.end() + 500)
            window = mech_text[start:end].lower()
            # Crude path extraction: forward-slash sequences with at least one segment.
            path_tokens = re.findall(r"[a-z0-9_./*-]+/[a-z0-9_./*-]+", window)
            seen_areas_for_this_mention: set[str] = set()
            for token in path_tokens:
                token_norm = token.strip("`'\"<>").rstrip(",;.")
                for slug, patterns in mapping.items():
                    if slug in primary_areas or slug in seen_areas_for_this_mention:
                        continue
                    for pat in patterns:
                        if matches_path(pat.lower(), token_norm):
                            contributions.append((slug, WEIGHT_MECHANISMS, f"mechanism:{name}"))
                            seen_areas_for_this_mention.add(slug)
                            break

    return contributions


def codegraph_signal(
    files_to_touch: list[str],
    primary_areas: set[str],
    mapping: dict[str, list[str]],
) -> tuple[list[tuple[str, int, str]], str | None]:
    """
    Returns (contributions, warning_text). When the CLI is unavailable or the
    impact subcommand failed on every input, warning_text is set and
    contributions is empty.
    """
    impact, warning = codegraph_impact_files(files_to_touch)
    if impact is None or warning is not None:
        return ([], warning)

    contributions: list[tuple[str, int, str]] = []
    per_area_count: dict[str, int] = {}
    for affected in impact:
        for slug, patterns in mapping.items():
            if slug in primary_areas:
                continue
            for pat in patterns:
                if matches_path(pat.lower(), affected):
                    # Cap per area to prevent a hub file dominating.
                    current = per_area_count.get(slug, 0)
                    if current * WEIGHT_CODEGRAPH >= WEIGHT_CODEGRAPH_CAP_PER_AREA:
                        break
                    per_area_count[slug] = current + 1
                    contributions.append((slug, WEIGHT_CODEGRAPH, "codegraph"))
                    break

    return (contributions, None)


def seed_adjacency_signal(
    primary_areas: set[str],
    raw_mapping_json: dict,
) -> list[tuple[str, int, str]]:
    """
    Phase 6: read optional seed_adjacency per area in area-mapping.json.
    For each primary area, every seeded adjacent area gets +WEIGHT_SEED_ADJACENCY.
    """
    contributions: list[tuple[str, int, str]] = []
    areas_dict = raw_mapping_json.get("areas", {})
    for primary in primary_areas:
        body = areas_dict.get(primary)
        if not isinstance(body, dict):
            continue
        seeds = body.get("seed_adjacency", [])
        if not isinstance(seeds, list):
            continue
        for seed in seeds:
            if isinstance(seed, str) and seed in areas_dict and seed not in primary_areas:
                contributions.append((seed, WEIGHT_SEED_ADJACENCY, f"seed:{primary}"))
    return contributions


def aggregate(
    contributions: list[tuple[str, int, str]],
) -> list[AreaScore]:
    by_area: dict[str, AreaScore] = {}
    for area, weight, label in contributions:
        if area not in by_area:
            by_area[area] = AreaScore(area=area)
        by_area[area].add(label, weight)
    return list(by_area.values())


def rank(scores: list[AreaScore]) -> list[AreaScore]:
    above = [s for s in scores if s.score >= THRESHOLD]
    above.sort(key=lambda s: (-s.score, s.area))
    return above[:TOP_N]


def scan_contract(contract_path: Path, use_cache: bool = True) -> dict:
    try:
        contract_text = contract_path.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        return {"error": f"cannot read contract: {e}", "areas": [], "warnings": []}

    if use_cache:
        cached = load_cache(contract_text)
        if cached is not None:
            cached["from_cache"] = True
            return cached

    mapping = load_area_mapping()
    try:
        raw_mapping_json = json.loads(area_mapping_path().read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        raw_mapping_json = {"areas": {}}

    primary_areas = set(derive_areas(contract_path, mapping))
    primary_areas.discard(FALLBACK_AREA)

    files_to_touch = extract_files_from_contract(contract_path)

    contributions: list[tuple[str, int, str]] = []
    warnings: list[str] = []

    if files_to_touch:
        cg_contributions, cg_warning = codegraph_signal(files_to_touch, primary_areas, mapping)
        contributions.extend(cg_contributions)
        if cg_warning:
            warnings.append(cg_warning)

    contributions.extend(journal_signal(primary_areas, mapping))
    contributions.extend(mechanisms_signal(contract_text, primary_areas, mapping))
    contributions.extend(seed_adjacency_signal(primary_areas, raw_mapping_json))

    scores = aggregate(contributions)
    top = rank(scores)

    result = {
        "from_cache": False,
        "primary_areas": sorted(primary_areas),
        "areas": [
            {"area": s.area, "score": s.score, "breakdown": s.breakdown}
            for s in top
        ],
        "warnings": warnings,
    }

    if use_cache:
        save_cache(contract_text, result)

    return result


def scan_files(file_paths: list[str]) -> dict:
    """
    Variant entry point: scan a synthetic Files-to-touch list without a contract.
    Used by /cross-impact when the user wants to explore before writing a contract.
    """
    mapping = load_area_mapping()
    try:
        raw_mapping_json = json.loads(area_mapping_path().read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        raw_mapping_json = {"areas": {}}

    normalized = [p.strip().replace("\\", "/").lower() for p in file_paths if p.strip()]

    primary_areas: set[str] = set()
    for entry in normalized:
        for slug, patterns in mapping.items():
            for pat in patterns:
                if matches_path(pat.lower(), entry):
                    primary_areas.add(slug)
                    break

    contributions: list[tuple[str, int, str]] = []
    warnings: list[str] = []

    cg_contributions, cg_warning = codegraph_signal(normalized, primary_areas, mapping)
    contributions.extend(cg_contributions)
    if cg_warning:
        warnings.append(cg_warning)

    contributions.extend(journal_signal(primary_areas, mapping))
    contributions.extend(seed_adjacency_signal(primary_areas, raw_mapping_json))

    scores = aggregate(contributions)
    top = rank(scores)

    return {
        "from_cache": False,
        "primary_areas": sorted(primary_areas),
        "areas": [
            {"area": s.area, "score": s.score, "breakdown": s.breakdown}
            for s in top
        ],
        "warnings": warnings,
    }


def format_human(result: dict) -> str:
    lines: list[str] = []
    if result.get("warnings"):
        for w in result["warnings"]:
            lines.append(f"warning: {w}")
    primary = result.get("primary_areas") or []
    lines.append(f"primary: {', '.join(primary) if primary else '(none)'}")
    areas = result.get("areas") or []
    if not areas:
        lines.append("(no adjacent areas above threshold)")
    else:
        for entry in areas:
            breakdown = "+".join(entry["breakdown"])
            lines.append(f"{entry['area']}\t{entry['score']}\t{breakdown}")
    if result.get("from_cache"):
        lines.append("(from cache)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("contract", nargs="?", help="Path to a concept contract")
    p.add_argument(
        "--files",
        help="Comma-separated file paths (alternative to passing a contract path)",
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass cache and force a fresh scan",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human text",
    )
    args = p.parse_args(argv)

    if args.files:
        result = scan_files(args.files.split(","))
    elif args.contract:
        path = Path(args.contract).expanduser()
        if not path.exists():
            print(f"error: contract not found: {path}", file=sys.stderr)
            return 1
        result = scan_contract(path, use_cache=not args.no_cache)
    else:
        p.error("must pass a contract path or --files")
        return 2

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_human(result))

    return 0


if __name__ == "__main__":
    sys.exit(main())
