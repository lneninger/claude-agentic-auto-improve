#!/usr/bin/env python3
"""
_memory_common.py -- shared pure logic for the memory-architecture system.

Imported by:
    memory-pager.py   (Stop hook -- Layer 3 pager + Layer 2 loud-fail)
    memory-health.py  (audit CLI -- Layer 2 reliability invariant checker)
    tests/test_memory_pager.py

Design invariant (Layer 2): every function here is PURE and side-effect-free
except the explicitly-named append/save helpers. Budgets, link integrity, and
token estimation are all deterministic functions of the config + file contents,
so they are unit-testable without touching the live hook wiring.

Token model: approx tokens == chars // 4 (the same heuristic used when the
budgets in memory-blocks.json were set). It is an ESTIMATE -- the point is
relative drift detection, not exact billing.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path

HOME = Path.home()
CONFIG_PATH = HOME / ".claude" / "memory-blocks.json"

# [label](target) -- captures markdown links. Targets that are http(s)/anchor/
# mailto are filtered out by is_local_md_link.
_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def expand(path_str: str) -> Path:
    """Expand ~ and normalize a config path string to an absolute Path.

    Handles ~ home prefix, forward-slash Windows paths (d:/Dev/...), and
    relative-to-home values. Does NOT require the path to exist.
    """
    s = (path_str or "").strip().strip('"')
    s = os.path.expanduser(s)
    return Path(s)


def estimate_tokens_from_text(text: str) -> int:
    return len(text) // 4


def estimate_tokens(path: Path) -> int:
    """Approx tokens for a file; 0 if missing/unreadable (fail-soft)."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeError):
        return 0
    return estimate_tokens_from_text(text)


def load_config(config_path: Path | None = None) -> dict:
    """Load memory-blocks.json. Raises only on hard IO/JSON error; callers
    fail-soft."""
    cp = config_path or CONFIG_PATH
    return json.loads(cp.read_text(encoding="utf-8"))


def check_budgets(surfaces: list[dict]) -> list[dict]:
    """For each surface {id,label,path,budget_tokens}, return a status row.

    over_by > 0 means the surface exceeds its budget. Missing files report
    tokens=0 and exists=False (not over budget -- absence is a different
    failure, surfaced separately).
    """
    rows: list[dict] = []
    for s in surfaces:
        p = expand(s.get("path", ""))
        exists = p.exists()
        tokens = estimate_tokens(p) if exists else 0
        budget = int(s.get("budget_tokens", 0) or 0)
        # Missing surfaces are not "over budget" -- absence is a separate failure
        # (status MISSING), so over_by stays 0 to keep the >0 over-filter clean.
        over_by = (tokens - budget) if (exists and budget) else 0
        rows.append(
            {
                "id": s.get("id", ""),
                "label": s.get("label", ""),
                "path": str(p),
                "exists": exists,
                "tokens": tokens,
                "budget": budget,
                "over_by": over_by,
                "status": ("MISSING" if not exists else "OVER" if over_by > 0 else "OK"),
            }
        )
    return rows


def is_local_md_link(target: str) -> bool:
    t = target.strip().split()[0] if target.strip() else ""
    if not t:
        return False
    low = t.lower()
    if low.startswith(("http://", "https://", "mailto:", "#")):
        return False
    # strip anchor
    t_noanchor = t.split("#", 1)[0]
    return t_noanchor.lower().endswith(".md")


def extract_md_link_targets(text: str) -> list[str]:
    out = []
    for m in _LINK_RE.finditer(text):
        target = m.group(1).strip()
        if is_local_md_link(target):
            out.append(target.split()[0].split("#", 1)[0])
    return out


def check_links(md_path: Path) -> list[dict]:
    """Return dead links found in md_path: [{target, resolved}].

    A link is dead if its resolved path (relative to md_path's directory,
    with ~ expansion) does not exist. This is the divergence detector: a
    pointer-index whose targets have been renamed/deleted is drifting.
    """
    try:
        text = md_path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeError):
        return []
    dead: list[dict] = []
    base = md_path.parent
    for target in extract_md_link_targets(text):
        if target.startswith("~"):
            resolved = expand(target)
        elif os.path.isabs(target):
            resolved = Path(target)
        else:
            resolved = (base / target)
        try:
            ok = resolved.exists()
        except OSError:
            ok = False
        if not ok:
            dead.append({"target": target, "resolved": str(resolved)})
    return dead


def build_pressure_entries(over_rows: list[dict]) -> list[dict]:
    """Turn over-budget rows into staging proposal entries (Layer 3 self-edit
    proposals). Deterministic; dedupe key is (id, tokens, today)."""
    today = date.today().isoformat()
    entries = []
    for r in over_rows:
        entries.append(
            {
                "key": f"{r['id']}:{r['tokens']}:{today}",
                "date": today,
                "id": r["id"],
                "label": r["label"],
                "path": r["path"],
                "tokens": r["tokens"],
                "budget": r["budget"],
                "over_by": r["over_by"],
            }
        )
    return entries


def render_staging_entry(e: dict) -> str:
    return (
        f"\n## {e['date']} -- memory pressure: {e['label']} (`{e['id']}`)\n"
        f"- Surface: `{e['path']}`\n"
        f"- Size: ~{e['tokens']} tokens vs budget {e['budget']} "
        f"(**over by ~{e['over_by']}**)\n"
        f"- Proposed action: demote cold/reference sections to an on-demand "
        f"doc and leave a 2-line pointer. Promote nothing into always-on.\n"
    )


def load_seen(seen_path: Path) -> dict:
    if not seen_path.exists():
        return {}
    try:
        return json.loads(seen_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_seen(seen_path: Path, data: dict) -> None:
    seen_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = seen_path.with_suffix(seen_path.suffix + f".tmp.{os.getpid()}")
    try:
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, seen_path)
    except (OSError, PermissionError):
        pass


def append_staging(staging_path: Path, entries: list[dict], seen: dict) -> tuple[int, dict]:
    """Append non-duplicate pressure entries to the staging file.

    Returns (num_appended, updated_seen). Dedupe by entry['key'] against seen
    so repeated Stop fires at the same size on the same day are no-ops.
    """
    new = [e for e in entries if e["key"] not in seen]
    if not new:
        return 0, seen
    staging_path.parent.mkdir(parents=True, exist_ok=True)
    header_needed = not staging_path.exists()
    chunk = ""
    if header_needed:
        chunk += (
            "# Memory Consolidation Proposals (STAGING)\n\n"
            "> Auto-written by `memory-pager.py` when an always-on surface "
            "exceeds its budget.\n"
            "> These are PROPOSALS for review -- nothing here is promoted "
            "automatically. Resolve an entry by trimming the surface, then "
            "delete the entry.\n"
        )
    for e in new:
        chunk += render_staging_entry(e)
    try:
        with staging_path.open("a", encoding="utf-8") as fh:
            fh.write(chunk)
    except OSError:
        return 0, seen
    for e in new:
        seen[e["key"]] = True
    return len(new), seen
