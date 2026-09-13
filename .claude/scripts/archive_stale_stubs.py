"""
archive_stale_stubs.py -- rename old follow-up stubs to .followup.archived.md.

A follow-up stub is a 10-line `.followup.md` file living at
`.claude/concepts/followups/<date>-<slug>.followup.md`. It's
created when a contract's Adjacent Areas table declares an area as
`follow-up handle` (cross-area scanner surfaced it; user chose to defer).

Stubs are durable but cheap. To prevent unbounded accumulation, this script
finds stubs whose mtime is older than DEFAULT_AGE_DAYS days and renames them
to `<slug>.followup.archived.md`. Archived files are no longer surfaced by
`/list-contracts` as "needs triage" but remain on disk for historical reference.

A stub is NOT archived if:
    - It already ends in `.followup.archived.md` (idempotent).
    - It ends in `.followup.superseded.md` (already promoted -- different lifecycle).
    - Its `Status:` line is anything OTHER than `stub` (defensive: someone may
      have promoted it manually without renaming).

CLI usage:
    py -3 archive_stale_stubs.py                     (dry-run by default)
    py -3 archive_stale_stubs.py --apply             (perform renames)
    py -3 archive_stale_stubs.py --days 60 --apply   (custom age threshold)
    py -3 archive_stale_stubs.py --root <path>       (alt concepts root)

Invoked by /validate-registries.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

from _claude_paths import concepts_roots, first_populated_dir

# Windows consoles default to cp1252, which cannot encode the arrows and
# dashes that appear in titles and registry excerpts. Applied to the whole
# class of printing scripts, not just the two that crashed first (#35).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass



def default_root() -> Path:
    """The concepts root actually holding contracts, project-local first."""
    return first_populated_dir(concepts_roots(), "*.md")
DEFAULT_AGE_DAYS = 30


def find_followup_stubs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    # Repo layout is FLAT: concepts/followups/, not concepts/<project>/followups/.
    # The old per-project walk looked for concepts/followups/followups under a
    # naive root swap and would have archived nothing forever (#35, INV-8).
    followups_dir = root / "followups"
    if not followups_dir.is_dir():
        return []
    out: list[Path] = []
    for entry in sorted(followups_dir.iterdir()):
        if not entry.is_file():
            continue
        if entry.name.lower().endswith(".followup.md"):
            out.append(entry)
    return out


def has_stub_status(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    match = re.search(r"(?im)^\*\*Status:\*\*\s*([a-z]+)\s*$", text)
    if not match:
        return False
    return match.group(1).strip().lower() == "stub"


def is_stale(path: Path, threshold_days: int) -> bool:
    try:
        mtime = dt.datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return False
    age = dt.datetime.now() - mtime
    return age.days >= threshold_days


def archive(path: Path, dry_run: bool) -> Path:
    new_path = path.with_name(path.name.replace(".followup.md", ".followup.archived.md"))
    if dry_run:
        return new_path
    path.rename(new_path)
    return new_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--root",
        default=None,
        help="Concepts root (default: resolved project-local, then global)",
    )
    p.add_argument(
        "--days",
        type=int,
        default=DEFAULT_AGE_DAYS,
        help=f"Age threshold in days (default: {DEFAULT_AGE_DAYS})",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Perform renames (default is dry-run)",
    )
    args = p.parse_args(argv)

    # expanduser() belongs on the USER-supplied branch -- default_root() is
    # already absolute. Swapping them silently broke `--root '~/...'`
    # (exit 0, wrong path, no output): the defect class under repair (#35).
    root = Path(args.root).expanduser() if args.root else default_root()
    if not root.exists():
        print(f"info: concepts root does not exist: {root}")
        return 0

    stubs = find_followup_stubs(root)
    archived = 0
    skipped_not_stub = 0
    skipped_fresh = 0

    for stub in stubs:
        if not has_stub_status(stub):
            skipped_not_stub += 1
            continue
        if not is_stale(stub, args.days):
            skipped_fresh += 1
            continue
        new_path = archive(stub, dry_run=not args.apply)
        verb = "would archive" if not args.apply else "archived"
        print(f"{verb}: {stub.name} -> {new_path.name}")
        archived += 1

    summary = f"summary: {archived} archived, {skipped_fresh} fresh, {skipped_not_stub} not-stub (status mismatch)"
    if not args.apply:
        summary += "  [DRY-RUN — pass --apply to perform renames]"
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
