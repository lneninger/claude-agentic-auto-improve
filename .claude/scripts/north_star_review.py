"""
north_star_review.py -- read active north-stars and emit suggestions.

A north star is an aspirational direction-setting file at
.claude/north-stars/<YYYY-MM-DD>-<slug>.md. This script:

1. Discovers every active north-star (Status: active) under the matching
   project directory.
2. For each, extracts the anti-patterns and computes a current-gap signal
   by grepping the codebase for anti-pattern hits.
3. Cross-references the project's MECHANISMS.md, JOURNAL.md, and recent
   concept contracts to identify what's already moving toward the
   aspiration vs what would move it backward.
4. Emits a ranked list of suggested next-step contracts.

CLI usage:
    py -3 north_star_review.py [--project <name>] [--repo-root <path>]
        [--update]            (write updated `Current gap` + `Suggested next steps`)
        [--json]              (machine-readable output)
        [--single <slug>]     (review one thought only)

When --update is set, the script REWRITES the `Current gap` and
`Suggested next steps` sections of each reviewed thought in place,
preserving every other section verbatim. Without --update it only prints.

Discovery rules:
    - North-stars without `Status: active` are skipped silently.
    - Status `achieved` / `superseded` / `abandoned` count as terminal --
      they are excluded from suggestion ranking.
    - Multiple projects are supported; --project filters to one.

Anti-pattern signal (current gap):
    Each line under `## Anti-patterns` is treated as a heuristic match
    target. If the anti-pattern text contains a quoted snippet, that
    snippet is grepped against the repo. Counts above 0 surface as a gap.

Suggestion ranking:
    Each north-star gets up to 3 suggested next-step contracts. A
    suggestion is a one-liner: `/design-first <task-title>`. The script
    does NOT invent task titles -- it reads the `Suggested next steps`
    section as the human-curated source and only AUGMENTS it when an
    anti-pattern is hit (proposing a contract to remediate the hit).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from _claude_paths import first_populated_dir, north_stars_roots, project_matches, registry

# Windows consoles default to cp1252, which cannot encode the arrows and
# dashes that appear in titles and registry excerpts. Applied to the whole
# class of printing scripts, not just the two that crashed first (#35).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass



def north_stars_root() -> Path:
    """The north-stars root actually holding thoughts, project-local first."""
    return first_populated_dir(north_stars_roots(), "*.md")


def journal_path() -> Path:
    return registry("JOURNAL.md")


def mechanisms_path() -> Path:
    return registry("MECHANISMS.md")
def default_repo_root(project: str) -> Path:
    """Repo root to scan for a project's anti-patterns.

    Was a hardcoded ``d:/Dev/HIPALANET/StockToolScalpingMachine``, which
    resolves to the PARENT repo even when this script runs inside a worktree --
    so a gap analysis silently scanned the wrong tree. Resolved from the
    project root instead, falling back to cwd (#35).
    """
    root = north_stars_root()
    candidate = root.parent.parent if root.parent.parent else None
    if candidate is not None and candidate.name == project and candidate.is_dir():
        return candidate
    return Path.cwd()

ACTIVE_STATUS = "active"
TERMINAL_STATUSES = {"achieved", "superseded", "abandoned"}


@dataclass
class NorthStar:
    path: Path
    slug: str
    project: str
    title: str
    status: str
    aspiration: str
    anti_patterns: list[str] = field(default_factory=list)
    current_gap: str = ""
    suggested_next_steps: str = ""
    raw_text: str = ""


def parse_north_star(path: Path, project_override: str | None = None) -> NorthStar | None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    # Title (first `# ` heading).
    title_match = re.search(r"^# (.+?)$", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem

    # Status.
    status_match = re.search(r"\*\*Status:\*\*\s*([a-zA-Z]+)", text)
    status = status_match.group(1).lower().strip() if status_match else "unknown"

    # Slug.
    slug_match = re.search(r"\*\*Slug:\*\*\s*([a-z0-9-]+)", text)
    slug = slug_match.group(1).strip() if slug_match else path.stem.split("-", 3)[-1] if "-" in path.stem else path.stem

    # Project (folder name).
    project = project_override if project_override is not None else path.parent.name

    # Section extractors.
    def extract_section(header: str) -> str:
        # Match `## <header>` up to next `## ` or end of file.
        pattern = re.compile(
            rf"(?ims)^## {re.escape(header)}\s*$\s*(.+?)(?=^## |\Z)",
            re.MULTILINE,
        )
        m = pattern.search(text)
        return m.group(1).strip() if m else ""

    aspiration = extract_section("Aspiration")

    # Anti-patterns: bullet list lines under ## Anti-patterns ... section.
    anti_section = extract_section("Anti-patterns (what would BLOCK us getting there)")
    anti_patterns: list[str] = []
    if anti_section:
        for line in anti_section.splitlines():
            stripped = line.strip()
            if stripped.startswith(("-", "*", "+")):
                content = stripped.lstrip("-*+ ").strip()
                if content and not content.startswith("("):
                    anti_patterns.append(content)

    current_gap = extract_section("Current gap (Claude-maintained)")
    suggested = extract_section("Suggested next steps (Claude-maintained)")

    return NorthStar(
        path=path,
        slug=slug,
        project=project,
        title=title,
        status=status,
        aspiration=aspiration,
        anti_patterns=anti_patterns,
        current_gap=current_gap,
        suggested_next_steps=suggested,
        raw_text=text,
    )


def discover(project: str | None) -> list[NorthStar]:
    root = north_stars_root()
    if not root.exists():
        return []
    # Repo layout is FLAT: north-stars/*.md, not north-stars/<project>/*.md.
    # The old per-project walk found nothing here even once the root resolved
    # correctly -- that second defect axis is why a constant swap alone was
    # not a fix (#35, INV-8).
    proj_name = root.parent.parent.name
    # Alias-based (see list_contracts): the checkout name is the branch slug
    # in a worktree, so an exact match against the documented
    # `--project StockToolScalpingMachine` silently returned zero (#35).
    if not project_matches(root, project):
        return []
    out: list[NorthStar] = []
    for md in sorted(root.glob("*.md")):
        if md.name.startswith("_"):
            continue
        ns = parse_north_star(md, project_override=proj_name)
        if ns:
            out.append(ns)
    return out


def extract_quoted_snippets(anti_pattern: str) -> list[str]:
    """
    Pull double-backtick / single-backtick / "quoted" snippets from an
    anti-pattern bullet. Those are the grep targets.
    """
    out: list[str] = []
    for m in re.finditer(r"`([^`]+)`", anti_pattern):
        snippet = m.group(1).strip()
        if snippet:
            out.append(snippet)
    for m in re.finditer(r'"([^"]{3,})"', anti_pattern):
        snippet = m.group(1).strip()
        if snippet and not snippet.startswith("System."):
            out.append(snippet)
    return out


SKIP_DIRS = {".git", "node_modules", "bin", "obj", "dist", ".vs", ".angular", ".codegraph"}
CODE_SUFFIXES = (".cs", ".ts", ".py", ".json", ".yaml", ".yml", ".scss", ".html")


def grep_repo_multi(
    repo_root: Path, snippets: list[str], max_files: int = 5
) -> dict[str, list[str]]:
    """Search for MANY snippets in ONE pass over the repository.

    Returns ``{snippet: [relative paths]}``, each capped at ``max_files``.
    Uses python ``re`` rather than shelling out to grep so this stays
    portable on Windows.

    **Why this exists.** The original ``grep_repo`` searched for a single
    snippet and re-walked the entire tree for each one. That was free while
    it was unreachable -- ``discover()`` returned zero north-stars, so the
    loop never ran. Repairing discovery (#35) made it hot: 11 north-stars x
    ~103 snippets over ~2,500 candidate files, measured at **302 seconds**,
    past the 120s agent tool timeout, so any agent invoking
    ``/north-star-review`` reported a failure. Inverting the loops -- walk
    once, read each file once, test every still-unsatisfied snippet against
    it -- collapses 103 walks into 1 without changing a single result.
    """
    if not repo_root.exists() or not snippets:
        return {}

    # Every pattern was `re.escape`d and searched with IGNORECASE -- i.e. a
    # literal, case-insensitive substring test. `in` on a pre-lowered string
    # is exactly equivalent and far cheaper than running ~100 compiled
    # patterns over every file. Lowering each file once and reusing it is
    # what takes the run from minutes to seconds; the results are identical.
    lowered = [(s, s.lower()) for s in snippets if s]
    found: dict[str, list[str]] = {s: [] for s, _ in lowered}
    pending = {s for s, _ in lowered}

    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fname in filenames:
            if not fname.endswith(CODE_SUFFIXES):
                continue
            if not pending:
                return {s: v for s, v in found.items() if v}
            fpath = Path(dirpath) / fname
            try:
                text_low = fpath.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                continue
            rel = None
            # One read, one lower, every outstanding snippet tested against it.
            for snippet, needle in lowered:
                if snippet not in pending:
                    continue
                if needle in text_low:
                    if rel is None:
                        rel = fpath.relative_to(repo_root).as_posix()
                    found[snippet].append(rel)
                    if len(found[snippet]) >= max_files:
                        pending.discard(snippet)
    return {s: v for s, v in found.items() if v}


def grep_repo(repo_root: Path, snippet: str, max_files: int = 5) -> list[str]:
    """Single-snippet search. Thin wrapper over :func:`grep_repo_multi`.

    Kept so any external caller keeps working; prefer the batched form for
    more than one snippet -- see its docstring for why that matters.
    """
    return grep_repo_multi(repo_root, [snippet], max_files).get(snippet, [])


def compute_gap(
    ns: NorthStar,
    repo_root: Path,
    hits_by_snippet: dict[str, list[str]] | None = None,
) -> list[str]:
    """
    For each anti-pattern, extract grep-able snippets and search the repo.
    Hits become gap entries (concrete files that violate this aspiration).
    """
    # Collect every snippet across every anti-pattern FIRST, then make a
    # single pass over the repo. Previously this grepped per snippet, which
    # meant one full-tree walk each -- 302s for 11 north-stars once discovery
    # was repaired. Ordering of the emitted gaps is unchanged.
    per_pattern = [(ap, extract_quoted_snippets(ap)) for ap in ns.anti_patterns]

    if hits_by_snippet is None:
        # Standalone call -- walk for this north-star's snippets alone.
        # `main()` passes a shared result instead, so the whole run costs one
        # walk rather than one per north-star (11 walks was still 150s).
        all_snippets: list[str] = []
        for _, snippets in per_pattern:
            for snippet in snippets:
                if snippet not in all_snippets:
                    all_snippets.append(snippet)
        hits_by_snippet = grep_repo_multi(repo_root, all_snippets, max_files=3)

    gaps: list[str] = []
    for ap, snippets in per_pattern:
        for snippet in snippets:
            hits = hits_by_snippet.get(snippet)
            if hits:
                hit_list = ", ".join(f"`{h}`" for h in hits)
                gaps.append(
                    f"Anti-pattern hit: `{snippet}` found in {hit_list} "
                    f"(from rule: {ap[:80]}{'...' if len(ap) > 80 else ''})"
                )
    return gaps


def compute_suggestions(ns: NorthStar, gaps: list[str]) -> list[str]:
    """
    Convert gaps into runnable `/design-first` invocations.
    """
    suggestions: list[str] = []
    for gap in gaps[:3]:  # Cap at 3 suggestions per north-star.
        # Extract the anti-pattern snippet for a slug.
        m = re.search(r"`([^`]+)`", gap)
        snippet = m.group(1) if m else "remediate-anti-pattern"
        # Suggest a remediation contract.
        slug = re.sub(r"[^a-z0-9]+", "-", snippet.lower())[:40].strip("-")
        suggestions.append(
            f"`/design-first \"Remediate {snippet} usage to align with {ns.slug}\"` "
            f"-- removes the anti-pattern from the files cited in the gap above. "
            f"Proposed slug: `<date>-remove-{slug}-from-codebase.md`."
        )
    if not suggestions and not gaps:
        suggestions.append(
            f"No anti-pattern hits found in the codebase. Aspiration appears unblocked at the "
            f"file-grep level -- next step is feature work that ACTIVELY advances `{ns.slug}` "
            f"rather than remediation. Run `/north-star-review` again after the next contract "
            f"to re-check."
        )
    return suggestions


def update_north_star(ns: NorthStar, gaps: list[str], suggestions: list[str]) -> None:
    today = dt.date.today().isoformat()
    new_gap_section = (
        f"_Last updated: {today}_\n\n"
        + ("\n".join(f"- {g}" for g in gaps) if gaps else "- (no anti-pattern hits detected; verify by hand if gap should be richer)")
    )
    new_suggestions_section = (
        f"_Last updated: {today}_\n\n"
        + ("\n".join(f"{i+1}. {s}" for i, s in enumerate(suggestions)) if suggestions else "1. (no suggestions auto-generated)")
    )

    text = ns.raw_text

    # Replace Current gap section.
    text = re.sub(
        r"(?ims)(^## Current gap \(Claude-maintained\)\s*\n).*?(?=^## )",
        rf"\1\n> Populated and updated by `/north-star-review`. Describes what currently exists that contradicts or doesn't yet support this aspiration. Cite file paths and mechanism names so the next reviewer can verify.\n\n{new_gap_section}\n\n",
        text,
    )

    # Replace Suggested next steps section.
    text = re.sub(
        r"(?ims)(^## Suggested next steps \(Claude-maintained\)\s*\n).*?(?=^## )",
        rf"\1\n> Populated and updated by `/north-star-review`. Ordered list of concrete contracts to draft next. Each line is a directly runnable `/design-first` invocation.\n\n{new_suggestions_section}\n\n",
        text,
    )

    # Update Last reviewed date.
    text = re.sub(
        r"\*\*Last reviewed:\*\*\s*[\d-]+",
        f"**Last reviewed:** {today}",
        text,
    )

    ns.path.write_text(text, encoding="utf-8")


def format_human(north_stars: list[NorthStar], gaps_by_slug: dict[str, list[str]], suggestions_by_slug: dict[str, list[str]]) -> str:
    out: list[str] = []
    if not north_stars:
        return "No active north-stars found under .claude/north-stars/."

    out.append("=" * 72)
    out.append("  North Star Review")
    out.append("=" * 72)

    for ns in north_stars:
        out.append("")
        out.append(f"# {ns.title}")
        out.append(f"  slug: {ns.slug}  |  status: {ns.status}  |  project: {ns.project}")
        out.append("")
        gaps = gaps_by_slug.get(ns.slug, [])
        out.append(f"  Gap signals ({len(gaps)}):")
        if gaps:
            for g in gaps:
                out.append(f"    * {g}")
        else:
            out.append("    (none -- no anti-pattern hits)")
        out.append("")
        sugs = suggestions_by_slug.get(ns.slug, [])
        out.append(f"  Suggested next steps ({len(sugs)}):")
        for s in sugs:
            out.append(f"    -> {s}")

    out.append("")
    out.append("=" * 72)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project", help="Limit to one project (folder name under north-stars/)")
    p.add_argument("--repo-root", help="Override the repo root used for codebase grep")
    p.add_argument("--update", action="store_true", help="Rewrite Current gap + Suggested next steps in each thought file")
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    p.add_argument("--single", help="Review one north-star by slug")
    args = p.parse_args(argv)

    north_stars = [ns for ns in discover(args.project) if ns.status == ACTIVE_STATUS]
    if args.single:
        north_stars = [ns for ns in north_stars if ns.slug == args.single]

    if not north_stars:
        msg = "No active north-stars found."
        if args.project:
            msg += f" (project filter: {args.project})"
        if args.single:
            msg += f" (slug filter: {args.single})"
        print(msg)
        return 0

    gaps_by_slug: dict[str, list[str]] = {}
    suggestions_by_slug: dict[str, list[str]] = {}

    # ONE repo walk per distinct root, shared by every north-star under it.
    # Per-north-star walking cost 150s for 11 north-stars; per-snippet cost
    # 302s. Both exceeded the 120s agent tool timeout, which made
    # /north-star-review report a failure whenever an agent invoked it (#35).
    roots_for: dict[str, Path] = {}
    by_root: dict[Path, list[NorthStar]] = {}
    for ns in north_stars:
        rr = Path(args.repo_root) if args.repo_root else default_repo_root(ns.project)
        roots_for[ns.slug] = rr
        by_root.setdefault(rr, []).append(ns)

    hits_cache: dict[Path, dict[str, list[str]]] = {}
    for rr, members in by_root.items():
        snippets: list[str] = []
        for member in members:
            for ap in member.anti_patterns:
                for snippet in extract_quoted_snippets(ap):
                    if snippet not in snippets:
                        snippets.append(snippet)
        hits_cache[rr] = grep_repo_multi(rr, snippets, max_files=3)

    for ns in north_stars:
        repo_root = roots_for[ns.slug]
        gaps = compute_gap(ns, repo_root, hits_cache.get(repo_root))
        sugs = compute_suggestions(ns, gaps)
        gaps_by_slug[ns.slug] = gaps
        suggestions_by_slug[ns.slug] = sugs
        if args.update:
            update_north_star(ns, gaps, sugs)

    if args.json:
        payload = {
            "north_stars": [
                {
                    "slug": ns.slug,
                    "title": ns.title,
                    "project": ns.project,
                    "status": ns.status,
                    "gaps": gaps_by_slug[ns.slug],
                    "suggestions": suggestions_by_slug[ns.slug],
                }
                for ns in north_stars
            ]
        }
        print(json.dumps(payload, indent=2))
    else:
        print(format_human(north_stars, gaps_by_slug, suggestions_by_slug))

    return 0


if __name__ == "__main__":
    sys.exit(main())
