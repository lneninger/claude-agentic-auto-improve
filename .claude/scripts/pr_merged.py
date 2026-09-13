#!/usr/bin/env python3
"""
pr_merged.py — the closing phase of one sub-task, as a callable script.

One implementation, two front doors. The `/pr-merged` skill calls this for a
person; the orchestrator loop calls it and reads the JSON. Both get identical
behaviour, which two separate implementations would not.

What it does:
  1. Ask GitHub whether each pull request really merged. Never trust the claim.
  2. Flag files resolved by hand anywhere in the pull request's history.
  3. Map the pull request to a sub-task by its branch.
  4. Write a completion record, or a failure record that escalates.
  5. Recompute which sub-tasks that releases, and what still blocks the rest.
  6. Hand the sets back. Iteration belongs to the caller, never to this phase.

Usage:
  py -3 .claude/scripts/pr_merged.py --contract <slug|path> --pr <n> [--pr <n>...] [--json]
  py -3 .claude/scripts/pr_merged.py --contract <slug|path> --status [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

CONCEPTS_DIR = Path(".claude/concepts")
RESULTS_DIR = Path(".claude/orchestrator/results")

# Agents that can own a sub-task. A block naming none of these is not a sub-task.
IMPLEMENTER_AGENTS = (
    "dotnet-backend-architect",
    "angular-senior-dev",
    "ingestion-data-architect",
    "senior-test-engineer",
    "ui-ux-designer",
    "llm-training-engineer",
    "python-ai-developer",
    "pinescript-developer",
)


@dataclass
class SubTask:
    """One merge-gated unit of a contract."""

    id: str
    ordinal: int
    name: str
    agent: str
    #: Declared ordinals this waits for. ``None`` means the contract never said,
    #: which is a defect and must never be read as "no dependencies".
    depends_on: Optional[List[int]]
    files: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
def _slug(text: str) -> str:
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


def derive_subtask_id(ordinal: int, heading: str) -> str:
    """``2``, ``Backend (`dotnet-backend-architect`)`` -> ``t2-backend``.

    Derived, never stored twice. The same identity names the branch, the
    completion record and the sub-task in a pull request title.
    """
    name = heading.split("(")[0]
    name = re.split(r"\s+[—–-]\s+", name)[0]
    return f"t{ordinal}-{_slug(name)}"


def branch_for(contract_slug: str, subtask_id: str) -> str:
    return f"task/{contract_slug}/{subtask_id}"


# ---------------------------------------------------------------------------
# Reading the plan out of the contract
# ---------------------------------------------------------------------------
def _parse_depends_on(body: str) -> Optional[List[int]]:
    m = re.search(r"^\*\*Depends on:\*\*(.*)$", body, re.M)
    if not m:
        return None  # a defect, not an implied "none"
    raw = m.group(1).strip()
    if raw.lower().startswith("none"):
        return []
    return [int(n) for n in re.findall(r"\d+", raw.split("—")[0].split("–")[0])]


def parse_handoff(contract_text: str) -> List[SubTask]:
    """Read the ``## Implementation Handoff`` section into sub-tasks.

    A sub-task is a block that names an implementer agent AND carries a
    ``Files to touch`` list. A scope note has neither. A review gate has an
    agent but nothing to merge. Neither is waited on.

    Headings after the section end are never read.
    """
    section = re.search(r"^## Implementation Handoff(.*?)(?=^## |\Z)", contract_text, re.S | re.M)
    if not section:
        return []

    tasks: List[SubTask] = []
    for index, block in enumerate(re.split(r"^### ", section.group(1), flags=re.M)[1:], start=1):
        heading, _, body = block.partition("\n")
        heading = heading.strip()

        agent = next((a for a in IMPLEMENTER_AGENTS if a in heading), None)
        files = re.findall(r"^-\s+`?([^\s`]+)`?", body.split("**Files to touch:**")[-1], re.M) \
            if "**Files to touch:**" in body else []
        if not agent or not files:
            continue  # scope note, review gate, or anything else that never merges

        ordinal_match = re.match(r"(\d+)\.", heading)
        ordinal = int(ordinal_match.group(1)) if ordinal_match else index
        clean = re.sub(r"^\d+\.\s*", "", heading)

        tasks.append(SubTask(
            id=derive_subtask_id(ordinal, clean),
            ordinal=ordinal,
            name=re.split(r"\s+[—–-]\s+", clean.split("(")[0])[0].strip(),
            agent=agent,
            depends_on=_parse_depends_on(body),
            files=files,
        ))
    return tasks


# ---------------------------------------------------------------------------
# What GitHub says
# ---------------------------------------------------------------------------
def classify_pr(pr: Optional[Dict[str, Any]], default_branch: str = "master") -> str:
    """One verdict from a closed set. First match wins."""
    if not pr:
        return "not-found"
    state = (pr.get("state") or "").upper()
    if state == "MERGED" and pr.get("mergedAt") and pr.get("mergeCommit"):
        return "merged" if pr.get("baseRefName") == default_branch else "merged-elsewhere"
    if state == "OPEN":
        return "not-merged"
    if state == "CLOSED" and not pr.get("mergedAt"):
        return "closed-unmerged"
    return "not-found"


def map_pr_to_subtask(head_branch: str, title: str, tasks: List[SubTask],
                      contract_slug: str) -> Optional[SubTask]:
    """Match by derived identity. No heuristic over file lists."""
    for t in tasks:
        if head_branch == branch_for(contract_slug, t.id):
            return t
    for t in tasks:
        if t.id in (title or "") or t.id in (head_branch or ""):
            return t
    return None


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------
def build_record(verdict: str, commit: Optional[str], pr_url: str,
                 merged_at: Optional[str], checks: Optional[str]) -> Dict[str, Any]:
    """A record states what was observed. It never asserts what was not.

    A merge is not a test run, so ``tests_passed`` is ``unknown`` unless a
    status check on the merge commit said otherwise.
    """
    if checks == "SUCCESS":
        tests_passed, verified_by = True, "ci"
    elif checks == "FAILURE":
        tests_passed, verified_by = False, "ci"
    else:
        tests_passed, verified_by = "unknown", "none"

    failed = verdict == "closed-unmerged"
    return {
        "status": "failed" if failed else "completed",
        "commit": commit,
        "tests_passed": tests_passed,
        "tests_verified_by": verified_by,
        "contract_impact": {
            "requires_architect": failed,
            "severity": "medium" if failed else "none",
            "description": ("Pull request closed without merging; the sub-task could not be "
                            "delivered as specified." if failed else None),
        },
        "completed_by": "pr-merged",
        "pull_request": pr_url,
        "merged_at": merged_at,
        "verified": "github",
    }


# ---------------------------------------------------------------------------
# Releases
# ---------------------------------------------------------------------------
def compute_released(tasks: List[SubTask],
                     records: Dict[str, Dict[str, Any]]
                     ) -> Tuple[List[SubTask], Dict[str, List[str]]]:
    """Return the sub-tasks now released, and what still blocks the rest.

    Computed from completion records only. Live state can go stale; a record
    is evidence. A record releases nothing unless it is completed AND carries
    ``verified: github``.
    """
    by_ordinal = {t.ordinal: t for t in tasks}
    released: List[SubTask] = []
    blocked: Dict[str, List[str]] = {}

    for task in tasks:
        if task.id in records:
            continue  # already closed, in either direction

        if task.depends_on is None:
            blocked[task.id] = ["(contract declares no Depends on line)"]
            continue

        unmet: List[str] = []
        for ordinal in task.depends_on:
            dep = by_ordinal.get(ordinal)
            if dep is None:
                unmet.append(f"(ordinal {ordinal} is not in the plan)")
                continue
            rec = records.get(dep.id)
            if not rec or rec.get("status") != "completed" or rec.get("verified") != "github":
                unmet.append(dep.id)

        if unmet:
            blocked[task.id] = unmet
        else:
            released.append(task)

    return released, blocked


# ---------------------------------------------------------------------------
# Hand-resolved files
# ---------------------------------------------------------------------------
def detect_resolved_files(commit_shas: List[str],
                          git_combined_diff: Callable[[str], Tuple[List[str], int]]) -> List[str]:
    """Files differing from BOTH parents of a merge commit.

    Those were resolved by hand, or changed during the merge in a way neither
    side contained. Both entered without ever appearing as a reviewable diff.

    A commit with fewer than two parents has no combined diff and is skipped.
    """
    out: List[str] = []
    for sha in commit_shas:
        files, parents = git_combined_diff(sha)
        if parents >= 2:
            out.extend(files)
    seen = set()
    return [f for f in out if not (f in seen or seen.add(f))]


# ---------------------------------------------------------------------------
# Edges: the only places that touch git or GitHub
# ---------------------------------------------------------------------------
def _run(cmd: List[str]) -> Tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return p.returncode, p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def gh_pr(number: int) -> Optional[Dict[str, Any]]:
    code, out = _run(["gh", "pr", "view", str(number), "--json",
                      "number,state,mergedAt,mergeCommit,headRefName,baseRefName,url,commits,statusCheckRollup"])
    if code != 0 or not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def git_combined_diff(sha: str) -> Tuple[List[str], int]:
    _, parents = _run(["git", "rev-list", "--parents", "-n", "1", sha])
    parent_count = max(len(parents.split()) - 1, 0)
    if parent_count < 2:
        return [], parent_count
    _, out = _run(["git", "show", "--cc", "--name-only", "--format=", sha])
    return [l for l in out.splitlines() if l.strip()], parent_count


def default_branch() -> str:
    code, out = _run(["git", "symbolic-ref", "refs/remotes/origin/HEAD"])
    return out.rsplit("/", 1)[-1] if code == 0 and out else "master"


def find_contract(slug_or_path: str) -> Optional[Path]:
    p = Path(slug_or_path)
    if p.is_file():
        return p
    matches = sorted(CONCEPTS_DIR.glob(f"*{slug_or_path}*.md"))
    return matches[0] if matches else None


def load_records(contract_slug: str) -> Dict[str, Dict[str, Any]]:
    d = RESULTS_DIR / contract_slug
    if not d.is_dir():
        return {}
    out = {}
    for f in d.glob("*.yaml"):
        try:
            import yaml
            out[f.stem] = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
    return out


def write_record(contract_slug: str, subtask_id: str, record: Dict[str, Any]) -> Path:
    import yaml
    d = RESULTS_DIR / contract_slug
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{subtask_id}.yaml"
    f.write_text(yaml.dump(record, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Close a sub-task whose pull request merged.")
    ap.add_argument("--contract", required=True, help="contract slug or path")
    ap.add_argument("--pr", action="append", type=int, default=[], help="pull request number (repeatable)")
    ap.add_argument("--status", action="store_true", help="report the plan without writing anything")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--dry-run", action="store_true", help="compute everything, write nothing")
    args = ap.parse_args()

    contract = find_contract(args.contract)
    if not contract:
        print(json.dumps({"error": "contract-not-found", "contract": args.contract}))
        return 2

    slug = contract.stem
    tasks = parse_handoff(contract.read_text(encoding="utf-8", errors="replace"))
    records = load_records(slug)
    base = default_branch()

    report: Dict[str, Any] = {
        "contract": slug,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sub_tasks": [asdict(t) for t in tasks],
        "closed": [], "skipped": [], "unmapped": [], "hand_resolved": [], "failed": [],
    }

    for number in args.pr:
        pr = gh_pr(number)
        verdict = classify_pr(pr, base)
        if verdict in ("not-found", "not-merged", "merged-elsewhere"):
            report["skipped"].append({"pr": number, "verdict": verdict})
            continue

        task = map_pr_to_subtask(pr.get("headRefName", ""), pr.get("title", ""), tasks, slug)
        if task is None:
            report["unmapped"].append({"pr": number, "branch": pr.get("headRefName")})
            continue

        shas = [c.get("oid") for c in (pr.get("commits") or []) if c.get("oid")]
        resolved = detect_resolved_files(shas, git_combined_diff)
        if resolved:
            report["hand_resolved"].append({"pr": number, "files": resolved})

        rollup = pr.get("statusCheckRollup")
        checks = rollup[0].get("conclusion") if isinstance(rollup, list) and rollup else None
        rec = build_record(verdict, (pr.get("mergeCommit") or {}).get("oid"),
                           pr.get("url", ""), pr.get("mergedAt"), checks)
        if not args.dry_run and not args.status:
            write_record(slug, task.id, rec)
        records[task.id] = rec
        (report["failed"] if rec["status"] == "failed" else report["closed"]).append(
            {"pr": number, "sub_task": task.id, "record": rec})

    released, blocked = compute_released(tasks, records)
    report["released"] = [t.id for t in released]
    report["blocked"] = blocked
    report["complete"] = bool(tasks) and all(t.id in records for t in tasks) and not report["failed"]

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"contract {slug}: {len(tasks)} sub-tasks")
        print(f"  closed:   {[c['sub_task'] for c in report['closed']] or 'none'}")
        print(f"  failed:   {[c['sub_task'] for c in report['failed']] or 'none'}")
        print(f"  released: {report['released'] or 'none'}")
        for tid, why in blocked.items():
            print(f"  blocked:  {tid} <- {', '.join(why)}")
        if report["hand_resolved"]:
            for h in report["hand_resolved"]:
                print(f"  hand-resolved in #{h['pr']}: {', '.join(h['files'])}")
        print(f"  contract complete: {report['complete']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
