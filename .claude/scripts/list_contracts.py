#!/usr/bin/env python3
"""
list_contracts.py -- inventory every concept contract under .claude/concepts/.

Groups by project, then by status. Highlights contracts needing user action
(drafts with unresolved Open Questions, approved contracts not yet implemented).

Usage:
    py -3 list_contracts.py [--project <name>] [--status <name>] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from _claude_paths import concepts_roots, first_populated_dir, project_matches

# Windows consoles default to cp1252, which cannot encode the arrows and
# box-drawing characters this report prints. That never surfaced while the
# script found zero contracts and printed only ASCII; once it actually
# resolved the repo tree, the first non-ASCII contract title crashed the run
# with a UnicodeEncodeError and a non-zero exit (#35). Best-effort and
# guarded -- a stream that cannot be reconfigured is left alone.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass


def concepts_root() -> Path:
    """The concepts root actually holding contracts, project-local first.

    Call-time, never a module constant: the constant form is what made this
    report zero of 109 contracts after the 2026-08-25 migration (#35, INV-2).
    """
    return first_populated_dir(concepts_roots(), "*.md")


def project_name_for(root: Path) -> str:
    """Project name for a resolved ``<project>/.claude/concepts`` root.

    The repo layout is flat -- contracts sit directly in ``concepts/`` -- so
    the old ``path.parent.name`` derivation yielded ``<loose>`` for every
    contract. The project name comes from the root that owns the tree.
    """
    try:
        return root.parent.parent.name
    except (AttributeError, IndexError):
        return "<loose>"

STATUS_ORDER = {
    "draft": 0,
    "approved": 1,
    "stub": 2,
    "implemented": 3,
    "superseded": 4,
    "archived": 5,
    "rejected": 6,
    "unknown": 7,
}

STATUS_ICONS = {
    "draft":       "[DRAFT]     ",
    "approved":    "[APPROVED]  ",
    "stub":        "[STUB]      ",
    "implemented": "[IMPLEMENT] ",
    "superseded":  "[SUPERSEDED]",
    "archived":    "[ARCHIVED]  ",
    "rejected":    "[REJECTED]  ",
    "unknown":     "[UNKNOWN]   ",
}

# Follow-up stub age threshold for the "needs triage" callout (days).
STUB_TRIAGE_AGE_DAYS = 7


def parse_contract(path: Path, project_override: str | None = None) -> dict[str, Any]:
    """Extract status, title, open-question count, and files-to-touch from a contract."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        return {
            "path": path,
            "error": str(e),
            "status": "unknown",
        }

    title = path.stem
    status = "unknown"
    open_questions = 0
    unresolved_questions = 0
    file_count = 0
    supersedes: str | None = None

    lines = text.splitlines()
    in_open_questions = False
    in_files_to_touch = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Title is the first # heading
        if i < 5 and stripped.startswith("# ") and title == path.stem:
            title = stripped.lstrip("# ").strip()

        # Status line
        if status == "unknown":
            m = re.search(r"\*?\*?Status:\*?\*?\s*([a-zA-Z_-]+)", stripped)
            if m:
                status = m.group(1).lower().strip()
                if status.startswith("superseded"):
                    status = "superseded"

        # Supersedes line
        if supersedes is None:
            m = re.search(r"\*?\*?Supersedes:\*?\*?\s*(.+)", stripped)
            if m:
                val = m.group(1).strip().strip("<>")
                if val and not val.startswith("optional"):
                    supersedes = val

        # Section tracking
        if re.match(r"##+\s*open\s*questions", stripped, re.I):
            in_open_questions = True
            in_files_to_touch = False
            continue
        if re.match(r"##+\s*implementation\s*handoff", stripped, re.I) or \
           re.match(r"##+\s*review", stripped, re.I):
            in_open_questions = False
        if re.search(r"\*?\*?files\s+to\s+touch:?\*?\*?", stripped, re.I):
            in_files_to_touch = True
            continue
        if in_files_to_touch and re.match(r"^#", stripped):
            in_files_to_touch = False

        # Count bullet questions
        if in_open_questions and stripped.startswith(("-", "*", "+")):
            content = stripped.lstrip("-*+ ")
            if content and not content.startswith("("):
                open_questions += 1
                # Unresolved if it starts with "[ ]" or has no answer line below
                if content.startswith("[ ]"):
                    unresolved_questions += 1
                elif not re.search(r"\*?\*?answer:?\*?\*?", content, re.I):
                    # Heuristic: unresolved if no "Answer:" on this line
                    unresolved_questions += 1

        # Count files to touch
        if in_files_to_touch and stripped.startswith(("-", "*", "+")):
            entry = stripped.lstrip("-*+ ").strip().strip("`")
            if entry and not entry.lower().startswith("pre-written"):
                file_count += 1

    # Project resolution: handle followups/ subdirectory.
    if project_override is not None:
        project = project_override
    else:
        project = "<loose>"
        if path.parent.parent.name == "concepts":
            project = path.parent.name
        elif path.parent.name == "followups" and path.parent.parent.parent.name == "concepts":
            project = path.parent.parent.name

    # Filename-based lifecycle overrides for follow-up stubs:
    name_lower = path.name.lower()
    is_followup = name_lower.endswith(".followup.md") or ".followup." in name_lower
    if name_lower.endswith(".followup.archived.md"):
        status = "archived"
    elif name_lower.endswith(".followup.superseded.md"):
        status = "superseded"

    return {
        "path": path,
        "project": project,
        "title": title,
        "status": status,
        "open_questions": open_questions,
        "unresolved_questions": unresolved_questions,
        "files_to_touch_count": file_count,
        "supersedes": supersedes,
        "mtime": path.stat().st_mtime,
        "is_followup": is_followup,
    }


def collect(project_filter: str | None, status_filter: str | None) -> list[dict[str, Any]]:
    root = concepts_root()
    if not root.exists():
        return []
    project = project_name_for(root)
    contracts = []
    for md in sorted(root.rglob("*.md")):
        if md.name.startswith("."):
            continue
        info = parse_contract(md, project_override=project)
        # Alias-based: --project accepts the checkout name OR the main-repo
        # name, case-folded. In a worktree the checkout name is the branch
        # slug, so an exact match against the documented
        # `--project StockToolScalpingMachine` silently returned zero (#35).
        if not project_matches(root, project_filter):
            continue
        if status_filter and info.get("status") != status_filter:
            continue
        contracts.append(info)
    contracts.sort(key=lambda c: (STATUS_ORDER.get(c["status"], 9), -c["mtime"]))
    return contracts


def print_human(contracts: list[dict[str, Any]]) -> None:
    if not contracts:
        print("No concept contracts found under .claude/concepts/")
        return

    # Group by project
    by_project: dict[str, list[dict[str, Any]]] = {}
    for c in contracts:
        by_project.setdefault(c["project"], []).append(c)

    # Summary
    total = len(contracts)
    by_status: dict[str, int] = {}
    for c in contracts:
        by_status[c["status"]] = by_status.get(c["status"], 0) + 1

    print()
    print("=" * 72)
    print("  Concept Contract Inventory")
    print("=" * 72)
    print(f"  Total: {total}  |  " + "  ".join(f"{s}: {n}" for s, n in sorted(by_status.items())))
    print("=" * 72)

    for project in sorted(by_project.keys()):
        print()
        print(f"--- Project: {project} ---")
        for c in by_project[project]:
            icon = STATUS_ICONS.get(c["status"], "[?]")
            short_path = c["path"].name
            action = ""
            if c["status"] == "draft":
                unresolved = c.get("unresolved_questions", 0)
                if unresolved:
                    action = f"  [ACTION: resolve {unresolved} Open Question(s)]"
                else:
                    action = "  [ACTION: review and flip Status to 'approved']"
            elif c["status"] == "approved":
                action = f"  [ACTION: run implementer(s), {c['files_to_touch_count']} file(s)]"
            elif c["status"] == "implemented":
                action = "  [OK: code is live]"
            elif c["status"] == "superseded" and c.get("supersedes"):
                action = f"  [superseded by: {c['supersedes']}]"
            elif c["status"] == "stub":
                import time
                age_days = max(0, int((time.time() - c["mtime"]) / 86400))
                if age_days >= STUB_TRIAGE_AGE_DAYS:
                    action = f"  [NEEDS TRIAGE: {age_days}d old; promote via /design-first or let archive_stale_stubs.py reap]"
                else:
                    action = f"  [follow-up stub, {age_days}d old]"

            print(f"  {icon} {short_path}")
            print(f"             {c['title']}{action}")

    print()
    print("=" * 72)
    print("  Next steps")
    print("=" * 72)
    draft_actions = sum(1 for c in contracts if c["status"] == "draft")
    approved_actions = sum(1 for c in contracts if c["status"] == "approved")
    stub_triage = sum(
        1 for c in contracts
        if c["status"] == "stub"
        and (__import__("time").time() - c["mtime"]) / 86400 >= STUB_TRIAGE_AGE_DAYS
    )
    if draft_actions:
        print(f"  * {draft_actions} draft contract(s) need user input -> /design-first continue")
    if approved_actions:
        print(f"  * {approved_actions} approved contract(s) ready for implementation")
    if stub_triage:
        print(f"  * {stub_triage} follow-up stub(s) >= {STUB_TRIAGE_AGE_DAYS}d old need triage -> promote or run archive_stale_stubs.py")
    if not draft_actions and not approved_actions and not stub_triage:
        print("  All contracts are in a stable state (implemented, archived, superseded).")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="List concept contracts.")
    parser.add_argument("--project", help="Filter by project name (folder under concepts/)")
    parser.add_argument("--status", help="Filter by status (draft|approved|implemented|archived|...)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    contracts = collect(args.project, args.status)

    if args.json:
        data = [
            {**c, "path": str(c["path"])} for c in contracts
        ]
        print(json.dumps(data, indent=2, default=str))
        return 0

    print_human(contracts)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print(f"[list-contracts] error: {e}", file=sys.stderr)
        sys.exit(1)
