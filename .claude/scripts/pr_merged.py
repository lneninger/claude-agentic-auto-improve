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
import copy
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

CONCEPTS_DIR = Path(".claude/concepts")
RESULTS_DIR = Path(".claude/orchestrator/results")

# Agents that can own a sub-task, for a project that declares none of its own.
# Only names the plugin actually ships: a project adds its own through the profile.
DEFAULT_IMPLEMENTERS = (
    "dotnet-backend-architect",
    "angular-senior-dev",
    "senior-test-engineer",
    "ui-ux-designer",
    "python-ai-developer",
)

PROFILE_PATH = Path(".claude/project-profile.md")


DEFAULT_REVIEW_GATES = (
    "fullstack-code-reviewer",
    "test-strategy-critic",
    "api-contract-reviewer",
    "security-auditor",
    "migration-safety-reviewer",
    "sql-performance-reviewer",
    "contract-critic",
    "data-architect",
)


def load_slot(profile_text: Optional[str], slot: str) -> Tuple[str, ...]:
    """Read any named slot from the project profile.

    One reader for every slot, so a new thing the flow needs is a slot in the
    template and a line here, never a second configuration file competing with
    the profile.

    A slot holding backticked values yields exactly those. A slot holding one
    plain word, such as the project name, yields that word. A slot still holding
    the template's italic placeholder yields nothing, because that prose
    describes the slot rather than filling it.
    """
    if not profile_text:
        return ()
    pattern = r"^\|\s*`?" + re.escape(slot) + r"`?\s*\|(.+?)\|\s*$"
    m = re.search(pattern, profile_text, re.M | re.I)
    if not m:
        return ()
    raw = m.group(1).strip()
    if "`" in raw:
        # A list slot: the values are backticked, so take exactly those.
        return tuple(v for v in re.findall(r"`([^`]+)`", raw) if v.lower() != "none")
    if raw.startswith("*(") or raw.lower() in ("none", ""):
        # An unfilled template slot. Its italic prose is a description of the
        # slot, never a value, and reading it as one is how a fresh project
        # inherits a dozen nonsense entries.
        return ()
    return (raw,)


def load_review_gates(profile_text: Optional[str]) -> Tuple[str, ...]:
    """Agents that review rather than implement.

    A review gate that declares a ``Files to touch`` entry (its review
    artefact) is an ordinary mergeable block, resolved through this list
    exactly as an implementer is resolved through ``IMPLEMENTER_AGENTS`` --
    see ``classify_handoff``. Declaring them is what lets a name that is
    neither an implementer nor a gate be reported as a mistake instead of
    silently vanishing from the plan.
    """
    return load_slot(profile_text, "review-gates") or DEFAULT_REVIEW_GATES


def agents_named_in(contract_text: str) -> List[str]:
    """Every backticked agent-shaped name in the handoff headings, in order."""
    section = re.search(r"^## Implementation Handoff(.*?)(?=^## |\Z)", contract_text, re.S | re.M)
    if not section:
        return []
    out = []
    for heading in re.findall(r"^### (.+)$", section.group(1), re.M):
        out.extend(re.findall(r"`([a-z][a-z0-9-]{4,})`", heading))
    return out


def unknown_agents(contract_text: str, implementers: Tuple[str, ...],
                   gates: Tuple[str, ...]) -> List[str]:
    """Names that are neither an implementer nor a declared review gate.

    These are almost always a typo or a shorthand. Left unreported, the block
    quietly stops being a sub-task and the work disappears from the plan with
    nothing to say it did.
    """
    known = set(implementers) | set(gates)
    seen, out = set(), []
    for name in agents_named_in(contract_text):
        if name not in known and name not in seen:
            seen.add(name); out.append(name)
    return out




def load_implementers(profile_text: Optional[str]) -> Tuple[str, ...]:
    """Which agents may own a sub-task, read from the project profile.

    Pure: it reads the text it is given and never touches disk. ``None`` or an
    empty string means the project authored no profile. ``read_profile`` is the
    separate thing that goes to disk, so "no profile" and "read the file" are
    never the same argument.

    A generic mechanism must not carry one project's agent names into another.
    The profile declares them in an ``implementers`` slot; absence falls back to
    the agents the plugin ships.

    A slot reading ``none`` also falls back. An empty implementer list would
    make every handoff block fail the sub-task test, so a contract would parse
    to nothing and the loop would report nothing-planned for work that exists.
    """
    if not profile_text:
        return DEFAULT_IMPLEMENTERS
    return load_slot(profile_text, "implementers") or DEFAULT_IMPLEMENTERS


def read_profile() -> Optional[str]:
    """The project profile's text, or None when the project has not authored one."""
    return PROFILE_PATH.read_text(encoding="utf-8", errors="replace")         if PROFILE_PATH.is_file() else None


#: Resolved once at import for the running project.
IMPLEMENTER_AGENTS = load_implementers(read_profile())
REVIEW_GATES = load_review_gates(read_profile())


@dataclass
class SubTask:
    """One merge-gated unit of a contract."""

    id: str
    ordinal: int
    name: str
    #: ``None`` when the block names no recognised agent -- never an empty
    #: string. The dispatch packet is JSON a model reads, and "" reads as a
    #: name.
    agent: Optional[str]
    #: Declared ordinals this waits for. ``None`` means the contract never said,
    #: which is a defect and must never be read as "no dependencies".
    depends_on: Optional[List[int]]
    files: List[str] = field(default_factory=list)
    #: Which list resolved ``agent``: implementer | review-gate | unrecognised
    #: | none. Defaults to ``None`` ("unset") so a hand-built SubTask in a
    #: test is not forced to invent a role -- ``classify_handoff`` always
    #: sets this explicitly.
    agent_role: Optional[str] = None


# ---------------------------------------------------------------------------
# Block classification -- what a block declares, never who is assigned
# ---------------------------------------------------------------------------
@dataclass
class HandoffBlock:
    """One ``###`` block in the handoff section, whatever kind it is.

    The accounting listing: its length equals the number of ``###`` headings
    in the section. Every block gets one of these, including scope notes and
    malformed blocks -- nothing is discarded.
    """

    ordinal: int
    id: str
    heading: str
    #: Closed set: mergeable | scope-note | malformed. Decided by what the
    #: block declares -- files, an agent, both, or neither.
    kind: str
    agent: Optional[str]
    #: Closed set: implementer | review-gate | unrecognised | none.
    agent_role: str
    files: List[str]
    depends_on: Optional[List[int]]


@dataclass
class BlockDefect:
    """A block that cannot be delivered as written, whatever its kind.

    Separate from ``kind`` deliberately: kind describes the declaration,
    defect describes the deliverability. A block may be ``mergeable`` and
    defective at once -- files present, agent name a typo.
    """

    ordinal: int
    id: str
    heading: str
    #: Closed set: no-files-but-names-an-agent | files-but-no-recognised-agent.
    reason: str
    agent: Optional[str]


@dataclass
class HandoffClassification:
    """The single return of ``classify_handoff``.

    ``sub_tasks`` keeps ``parse_handoff``'s exact position, ordering and
    fields -- it is the mergeable subset whose agent actually resolved to a
    recognised name, so it can be dispatched.
    """

    blocks: List[HandoffBlock]
    sub_tasks: List[SubTask]
    defects: List[BlockDefect]


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


def classify_handoff(contract_text: str,
                     implementers: Optional[Tuple[str, ...]] = None,
                     gates: Optional[Tuple[str, ...]] = None) -> HandoffClassification:
    """Classify every ``###`` block in the ``## Implementation Handoff`` section.

    A block is judged by what it DECLARES, never by who is assigned:

      declares files? | agent in heading        | kind        | in defects?
      -----------------|--------------------------|-------------|-------------
      yes              | implementer              | mergeable   | no
      yes              | review-gate               | mergeable   | no
      yes              | agent-shaped, unrecognised | mergeable  | yes
      yes              | none present              | mergeable   | yes
      no                | implementer or review-gate | malformed | yes
      no                | agent-shaped, unrecognised | malformed  | yes
      no                | none present              | scope-note  | no

    ``sub_tasks`` is the mergeable subset whose agent actually resolved --
    the two "mergeable but defective" rows above are tracked in ``defects``
    and excluded from ``sub_tasks``, because there is no one to dispatch them
    to. Nothing that appears in the handoff section is silently dropped:
    ``len(blocks)`` equals the number of ``###`` headings.

    Headings after the section end are never read.
    """
    section = re.search(r"^## Implementation Handoff(.*?)(?=^## |\Z)", contract_text, re.S | re.M)
    if not section:
        return HandoffClassification(blocks=[], sub_tasks=[], defects=[])

    impls = implementers if implementers is not None else IMPLEMENTER_AGENTS
    gts = gates if gates is not None else REVIEW_GATES

    blocks: List[HandoffBlock] = []
    sub_tasks: List[SubTask] = []
    defects: List[BlockDefect] = []

    for index, block in enumerate(re.split(r"^### ", section.group(1), flags=re.M)[1:], start=1):
        heading, _, body = block.partition("\n")
        heading = heading.strip()

        named_order = re.findall(r"`([a-z][a-z0-9-]{4,})`", heading)
        named = set(named_order)
        files = re.findall(r"^-\s+`?([^\s`]+)`?", body.split("**Files to touch:**")[-1], re.M) \
            if "**Files to touch:**" in body else []

        agent = next((a for a in impls if a in named), None)
        if agent:
            role = "implementer"
        else:
            agent = next((a for a in gts if a in named), None)
            if agent:
                role = "review-gate"
            elif named_order:
                agent = named_order[0]
                role = "unrecognised"
            else:
                role = "none"

        ordinal_match = re.match(r"(\d+)\.", heading)
        ordinal = int(ordinal_match.group(1)) if ordinal_match else index
        clean = re.sub(r"^\d+\.\s*", "", heading)
        block_id = derive_subtask_id(ordinal, clean)
        name = re.split(r"\s+[—–-]\s+", clean.split("(")[0])[0].strip()
        depends_on = _parse_depends_on(body)

        if files:
            kind = "mergeable"
        elif role != "none":
            kind = "malformed"
        else:
            kind = "scope-note"

        blocks.append(HandoffBlock(
            ordinal=ordinal, id=block_id, heading=heading, kind=kind,
            agent=agent, agent_role=role, files=files, depends_on=depends_on,
        ))

        if kind == "mergeable" and role in ("implementer", "review-gate"):
            sub_tasks.append(SubTask(
                id=block_id, ordinal=ordinal, name=name, agent=agent,
                depends_on=depends_on, files=files, agent_role=role,
            ))
        elif kind == "mergeable":
            defects.append(BlockDefect(
                ordinal=ordinal, id=block_id, heading=heading,
                reason="files-but-no-recognised-agent", agent=agent,
            ))
        elif kind == "malformed":
            defects.append(BlockDefect(
                ordinal=ordinal, id=block_id, heading=heading,
                reason="no-files-but-names-an-agent", agent=agent,
            ))

    return HandoffClassification(blocks=blocks, sub_tasks=sub_tasks, defects=defects)


def parse_handoff(contract_text: str,
                  implementers: Optional[Tuple[str, ...]] = None) -> List[SubTask]:
    """Read the ``## Implementation Handoff`` section into sub-tasks.

    A projection of ``classify_handoff``: a sub-task is a mergeable block
    whose agent actually resolved, whether to an implementer or to a review
    gate that declares its own review artefact as a file to touch. A scope
    note declares neither an agent nor files. A block naming an agent with no
    files -- review gate or otherwise -- is a contract defect, reported
    through ``classify_handoff(...).defects`` rather than silently dropped.

    Headings after the section end are never read.
    """
    return classify_handoff(contract_text, implementers=implementers, gates=None).sub_tasks


def handoff_bodies(contract_text: str) -> Dict[str, str]:
    """Sub-task identity -> the raw text of its handoff block.

    Kept separate from ``parse_handoff`` so the parsed plan stays small enough
    to hand around as JSON.
    """
    out: Dict[str, str] = {}
    section = re.search(r"^## Implementation Handoff(.*?)(?=^## |\Z)", contract_text, re.S | re.M)
    if not section:
        return out
    for index, block in enumerate(re.split(r"^### ", section.group(1), flags=re.M)[1:], start=1):
        heading, _, body = block.partition("\n")
        heading = heading.strip()
        om = re.match(r"(\d+)\.", heading)
        ordinal = int(om.group(1)) if om else index
        out[derive_subtask_id(ordinal, re.sub(r"^\d+\.\s*", "", heading))] = body
    return out


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
                 merged_at: Optional[str], checks: Optional[str],
                 review_verdict: Optional[str] = None) -> Dict[str, Any]:
    """A record states what was observed. It never asserts what was not.

    A merge is not a test run, so ``tests_passed`` is ``unknown`` unless a
    status check on the merge commit said otherwise.

    ``review_verdict`` is the ``**Verdict:**`` reading a review-gate sub-task's
    own artefact carried, if one was read. ``None`` means no reading was
    taken -- either the sub-task declares no review artefact, or nothing
    could be read -- and the key is OMITTED entirely rather than stamped as
    null, so every record written before this parameter existed keeps its
    exact meaning.
    """
    if checks == "SUCCESS":
        tests_passed, verified_by = True, "ci"
    elif checks == "FAILURE":
        tests_passed, verified_by = False, "ci"
    else:
        tests_passed, verified_by = "unknown", "none"

    failed = verdict == "closed-unmerged"
    record = {
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
    if review_verdict is not None:
        record["review_verdict"] = review_verdict
    return record


# ---------------------------------------------------------------------------
# Releases
# ---------------------------------------------------------------------------
def compute_released(tasks: List[SubTask],
                     records: Dict[str, Dict[str, Any]]
                     ) -> Tuple[List[SubTask], Dict[str, List[str]]]:
    """Return the sub-tasks now released, and what still blocks the rest.

    Computed from completion records only. Live state can go stale; a record
    is evidence. A record releases nothing unless it is completed AND carries
    ``verified: github``. A dependency's record may also carry a
    ``review_verdict`` (stamped for a verdict-bearing sub-task); a reading
    outside ``pass`` / ``pass-with-findings`` is treated as unmet, naming the
    reading in the blocked reason. A record with no ``review_verdict`` key is
    judged exactly as before this field existed -- that is what protects
    every record written before this change.
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
                continue
            verdict = rec.get("review_verdict")
            if verdict is not None and verdict not in ("pass", "pass-with-findings"):
                unmet.append(f"{dep.id} (review verdict: {verdict})")

        if unmet:
            blocked[task.id] = unmet
        else:
            released.append(task)

    return released, blocked


# ---------------------------------------------------------------------------
# The state store — what makes suspend and resume real
# ---------------------------------------------------------------------------
STATE_DIR = Path(".claude/orchestrator/state")


def new_state(contract_slug: str, tasks: List[SubTask]) -> Dict[str, Any]:
    """A fresh position: every sub-task pending, nothing dispatched."""
    return {
        "contract": contract_slug,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "sub_tasks": {t.id: {"status": "pending", "branch": None, "pull_request": None}
                      for t in tasks},
    }


def mark_dispatched(state: Dict[str, Any], subtask_id: str, branch: str) -> Dict[str, Any]:
    """Record that a sub-task was started and is now waiting for a merge.

    ``awaiting-merge`` is the state the old orchestrator never had. Without it,
    a sub-task suspended on an open pull request is indistinguishable from one
    that is genuinely stuck.
    """
    st = copy.deepcopy(state)
    if subtask_id in st["sub_tasks"]:
        st["sub_tasks"][subtask_id].update({"status": "awaiting-merge", "branch": branch})
    return st


def reconcile_state(state: Dict[str, Any], records: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Bring the position into line with the evidence.

    Records are the durable truth; state is a working position. A record for a
    sub-task the plan does not contain is ignored, never invented into state.
    """
    st = copy.deepcopy(state)
    for tid, rec in records.items():
        if tid not in st["sub_tasks"]:
            continue
        status = rec.get("status")
        if status in ("completed", "failed"):
            st["sub_tasks"][tid]["status"] = status
    return st


def awaiting_merge(state: Dict[str, Any]) -> List[str]:
    return [tid for tid, v in state.get("sub_tasks", {}).items()
            if v.get("status") == "awaiting-merge"]


def state_path(contract_slug: str) -> Path:
    return STATE_DIR / contract_slug / "state.yaml"


def load_state(contract_slug: str) -> Optional[Dict[str, Any]]:
    f = state_path(contract_slug)
    if not f.is_file():
        return None
    try:
        import yaml
        return yaml.safe_load(f.read_text(encoding="utf-8")) or None
    except Exception:
        return None


def write_state(contract_slug: str, state: Dict[str, Any]) -> Path:
    import yaml
    f = state_path(contract_slug)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(yaml.dump(state, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return f


def create_branch(branch: str, base: str) -> Tuple[bool, str]:
    """Cut a sub-task branch from a freshly fetched default branch.

    Never from whatever happens to be checked out. A sub-task seeded from
    another branch inherits its commits and its review surface.
    """
    if _run(["git", "rev-parse", "--verify", branch])[0] == 0:
        return False, "branch already exists"
    if _run(["git", "fetch", "origin", base])[0] != 0:
        return False, "could not fetch origin/" + base
    code, out = _run(["git", "switch", "-c", branch, "origin/" + base])
    return code == 0, out or ("created " + branch)


# ---------------------------------------------------------------------------
# Dispatch — extracted from the contract, never invented
# ---------------------------------------------------------------------------
def extract_task_block(block_body: str) -> Optional[str]:
    """Pull the architect's pre-written TASK block out of a handoff block.

    The contract already carries one per sub-task in most cases, so dispatch
    reads it rather than composing instructions of its own. Returns ``None``
    when the block has none — a gap to report, never to fill by guessing.
    """
    m = re.search(r"\*\*Pre-written TASK block:\*\*\s*```[a-z]*\n(.*?)```", block_body, re.S)
    return m.group(1).rstrip() if m else None


def build_dispatch(task: SubTask, contract_slug: str, contract_path: str,
                   block_body: str) -> Dict[str, Any]:
    """Everything needed to start one sub-task, and nothing more.

    This produces the packet. It does not run anything: implementation needs a
    model, and a script cannot be one. The caller executes it.
    """
    block = extract_task_block(block_body)
    return {
        "sub_task": task.id,
        "branch": branch_for(contract_slug, task.id),
        "agent": task.agent,
        "files": task.files,
        "contract": contract_path,
        "task_block": block,
        "needs_authoring": block is None,
        #: Mirrors needs_authoring. A None agent has no one to dispatch to --
        #: the caller must refuse rather than send an empty name to a model.
        "needs_agent": task.agent is None,
    }


# ---------------------------------------------------------------------------
# advance — one move, then stop
# ---------------------------------------------------------------------------
def advance(tasks: List[SubTask], records: Dict[str, Dict[str, Any]],
            state: Optional[Dict[str, Any]] = None,
            defects: Optional[List[Any]] = None) -> Dict[str, Any]:
    """Decide the contract's next single move. This never iterates.

    A merge-gated loop does not spin. It makes one move, then suspends until a
    person merges something and the closing phase wakes it.

    The order of these questions matters, and a contract's own defects are
    asked about FIRST — ahead of even an empty plan. A contract whose blocks
    are all malformed parses to an empty task list, and asking
    "nothing-planned" first would describe a contract declaring nine
    defective blocks as one declaring none. Only once there are no defects to
    report does an empty plan get read as having nothing planned, never as
    complete — ``all()`` over an empty collection answers yes, and reading
    that as success is the defect that made the old orchestrator report a
    finished contract having written no code.
    """
    if defects:
        return {"action": "contract-defect", "defects": defects,
                "detail": "one or more handoff blocks cannot be delivered as written; "
                          "amend the contract before anything is dispatched"}

    if not tasks:
        return {"action": "nothing-planned",
                "detail": "the contract declares no sub-tasks; nothing can be complete"}

    failed = [tid for tid, rec in records.items() if rec.get("status") == "failed"]
    if failed:
        return {"action": "escalate", "failed": failed,
                "detail": "a sub-task could not be delivered; the contract needs amending"}

    if state:
        waiting = awaiting_merge(reconcile_state(state, records))
        if waiting:
            return {"action": "awaiting-merge", "awaiting": waiting,
                    "detail": "a sub-task is out for merge; /pr-merged continues once it lands"}

    if all(t.id in records for t in tasks):
        return {"action": "complete",
                "detail": "every sub-task has a completion record"}

    released, blocked = compute_released(tasks, records)
    if released:
        return {"action": "dispatch", "sub_tasks": [t.id for t in released], "blocked": blocked}

    return {"action": "blocked", "blocked": blocked,
            "detail": "sub-tasks remain and none is ready"}


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
# The one machine-read line in a review artefact
# ---------------------------------------------------------------------------
_REVIEW_VERDICT_VALUES = ("pass", "pass-with-findings", "blocked")


def parse_review_verdict(artefact_text: str) -> Optional[str]:
    """Read a review artefact's ``**Verdict:**`` header line.

    Fixed shape, alone on its own line: ``**Verdict:** pass``,
    ``**Verdict:** pass-with-findings`` or ``**Verdict:** blocked``. Prose
    elsewhere in the file is for the reader and is never read here. A missing
    line, free prose that is not the fixed header, or a value outside the
    closed set all return ``None`` -- a guess here is worse than admitting
    the artefact could not be read.
    """
    m = re.search(r"^\*\*Verdict:\*\*\s*(\S+)\s*$", artefact_text, re.M)
    if not m:
        return None
    value = m.group(1).strip()
    return value if value in _REVIEW_VERDICT_VALUES else None


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
                      "number,title,state,mergedAt,mergeCommit,headRefName,baseRefName,url,commits,statusCheckRollup"])
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


def file_at_commit(sha: str, path: str) -> Optional[str]:
    """The text of ``path`` as it existed at ``sha``, or ``None`` if it can't
    be read -- the file didn't exist at that commit, or the commit is unknown.

    Injectable the same way ``git_combined_diff`` is: called by its module-
    level name, so a caller patches ``pr_merged.file_at_commit`` directly
    without threading it through as a parameter.
    """
    code, out = _run(["git", "show", f"{sha}:{path}"])
    return out if code == 0 else None


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
    ap.add_argument("--dispatch", metavar="SUBTASK", help="start this sub-task: cut its branch and record it")
    ap.add_argument("--resume", action="store_true", help="report the stored position and what it waits for")
    args = ap.parse_args()

    contract = find_contract(args.contract)
    if not contract:
        print(json.dumps({"error": "contract-not-found", "contract": args.contract}))
        return 2

    slug = contract.stem
    classification = classify_handoff(contract.read_text(encoding="utf-8", errors="replace"))
    tasks = classification.sub_tasks
    blocks = classification.blocks
    defects = classification.defects
    records = load_records(slug)
    base = default_branch()

    report: Dict[str, Any] = {
        "contract": slug,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sub_tasks": [asdict(t) for t in tasks],
        "blocks": [asdict(b) for b in blocks],
        "defects": [asdict(d) for d in defects],
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
        merge_sha = (pr.get("mergeCommit") or {}).get("oid")

        review_verdict = None
        verdict_file = next((f for f in task.files if f.startswith(".claude/reviews/")), None)
        # A pull request that closed WITHOUT merging has no merge commit, so
        # nothing was read and no reading is stamped -- the key stays absent.
        # Stamping "unreadable" here would claim an attempt that never
        # happened. The dependent is already withheld by an older, stronger
        # mechanism: build_record marks this record "failed" for a
        # closed-unmerged pull request, and advance() short-circuits on any
        # failed record before the release check is ever reached.
        if verdict_file and merge_sha:
            artefact_text = file_at_commit(merge_sha, verdict_file)
            # parse_review_verdict stays pure: it reports what the artefact
            # says, or nothing. "unreadable" is the loop's own judgement
            # about an artefact -- absent, unparseable, or out of the closed
            # set -- and is never something a gate writes, so it is named
            # here rather than by the parser.
            reading = parse_review_verdict(artefact_text) if artefact_text is not None else None
            review_verdict = reading or "unreadable"

        rec = build_record(verdict, merge_sha, pr.get("url", ""), pr.get("mergedAt"), checks,
                           review_verdict=review_verdict)
        if not args.dry_run and not args.status:
            write_record(slug, task.id, rec)
        records[task.id] = rec
        (report["failed"] if rec["status"] == "failed" else report["closed"]).append(
            {"pr": number, "sub_task": task.id, "record": rec})

    report["review_verdicts"] = {
        tid: rec["review_verdict"] for tid, rec in records.items() if "review_verdict" in rec
    }

    state = load_state(slug) or new_state(slug, tasks)
    state = reconcile_state(state, records)

    if args.dispatch:
        by_id = {t.id: t for t in tasks}
        task = by_id.get(args.dispatch)
        if not task:
            print(json.dumps({"error": "unknown-sub-task", "sub_task": args.dispatch,
                              "known": list(by_id)}))
            return 2
        move_now = advance(tasks, records, state, defects=defects)
        ready = move_now.get("sub_tasks", []) if move_now["action"] == "dispatch" else []
        if task.id not in ready:
            if move_now["action"] == "contract-defect":
                print(json.dumps({"error": "contract-defect", "sub_task": task.id,
                                  "defects": move_now.get("defects", []),
                                  "detail": "one or more handoff blocks cannot be delivered as "
                                            "written; amend the contract before anything is "
                                            "dispatched"}))
            else:
                print(json.dumps({"error": "not-released", "sub_task": task.id,
                                  "detail": "its dependencies have not landed; dispatching it "
                                            "would build on work that does not exist"}))
            return 3
        branch = branch_for(slug, task.id)
        ok, detail = (True, "dry run") if args.dry_run else create_branch(branch, base)
        if not ok:
            print(json.dumps({"error": "branch-failed", "branch": branch, "detail": detail}))
            return 4
        state = mark_dispatched(state, task.id, branch)
        if not args.dry_run:
            write_state(slug, state)
        bodies = handoff_bodies(contract.read_text(encoding="utf-8", errors="replace"))
        packet = build_dispatch(task, slug, str(contract), bodies.get(task.id, ""))
        packet["branch_created"] = branch
        print(json.dumps(packet, indent=2) if args.json else
              f"dispatched {task.id} on {branch} -> {task.agent}")
        return 0

    move = advance(tasks, records, state, defects=defects)
    report["next_move"] = move
    report["released"] = move.get("sub_tasks", [])
    report["blocked"] = move.get("blocked", {})
    report["complete"] = move["action"] == "complete"
    report["state"] = state
    if not args.dry_run and not args.status:
        write_state(slug, state)

    if move["action"] == "dispatch":
        bodies = handoff_bodies(contract.read_text(encoding="utf-8", errors="replace"))
        by_id = {t.id: t for t in tasks}
        report["dispatch"] = [
            build_dispatch(by_id[tid], slug, str(contract), bodies.get(tid, ""))
            for tid in move["sub_tasks"]
        ]

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"contract {slug}: {len(tasks)} sub-tasks")
        print(f"  closed:   {[c['sub_task'] for c in report['closed']] or 'none'}")
        print(f"  failed:   {[c['sub_task'] for c in report['failed']] or 'none'}")
        print(f"  released: {report['released'] or 'none'}")
        for tid, why in report["blocked"].items():
            print(f"  blocked:  {tid} <- {', '.join(why)}")
        if report["hand_resolved"]:
            for h in report["hand_resolved"]:
                print(f"  hand-resolved in #{h['pr']}: {', '.join(h['files'])}")
        print(f"  next move: {move['action']}" + (f" - {move.get('detail')}" if move.get("detail") else ""))
        for d in report.get("dispatch", []):
            flag = "  [TASK BLOCK MISSING — author it in the contract]" if d["needs_authoring"] else ""
            print(f"    dispatch {d['sub_task']} -> {d['agent']} on {d['branch']}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
