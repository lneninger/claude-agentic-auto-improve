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
  py -3 .claude/scripts/pr_merged.py --contract <slug|path> --pr <n|link> [--pr <n|link>...] [--json]
  py -3 .claude/scripts/pr_merged.py --contract <slug|path> --status [--json]

A `--pr` reference is either a number, in this repository, or an `https://` link, which may
name another repository -- resolved by `gh` per call, never through a process-wide `--repo` flag
or a `GH_REPO` environment variable. With `GH_REPO` set, `--pr` and `--dispatch` both refuse
(exit 8) before touching the contract, git or `gh` at all.
"""

from __future__ import annotations

import argparse
import json
import os
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
def classify_pr(pr: Optional[Dict[str, Any]], default_branch: str = "master",
                accepted_bases: Optional[set] = None) -> str:
    """One verdict from a closed set. First match wins.

    ``accepted_bases`` is the Declared base set -- ``{default branch} union
    {every state entry's base}`` for one contract. ``None`` reproduces
    today's behaviour exactly (I-9): only the repository default branch
    counts as ``merged``. Given a set, ``merged`` holds for any base inside
    it -- a sub-task's own declared parent branch included -- and
    ``merged-elsewhere`` stays reachable for every base outside it.
    """
    if not pr:
        return "not-found"
    state = (pr.get("state") or "").upper()
    if state == "MERGED" and pr.get("mergedAt") and pr.get("mergeCommit"):
        accepted = accepted_bases if accepted_bases is not None else {default_branch}
        return "merged" if pr.get("baseRefName") in accepted else "merged-elsewhere"
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


#: A GitHub pull-request URL, as ``gh_pr`` reports it back in ``url`` --
#: never as the caller supplied it, since a caller may pass a link with a
#: trailing slash or query string this pattern does not need to accept.
_PR_URL_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/pull/\d+/?$")


def _owner_and_name_from_url(url: Optional[str]) -> Optional[Tuple[str, str]]:
    """``owner`` and ``name`` out of a pull request's own GitHub URL, or ``None``.

    Used only to decide whether a link-named pull request is Cross-Repository
    (X-3) -- an unparseable ``url`` returns ``None``, which the caller must
    read as "unreadable", never as "matches this repository" (fail-closed).
    """
    if not url:
        return None
    m = _PR_URL_RE.match(url)
    return (m.group(1), m.group(2)) if m else None


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------
def build_record(verdict: str, commit: Optional[str], pr_url: str,
                 merged_at: Optional[str], checks: Optional[str],
                 review_verdict: Optional[str] = None,
                 sub_issue_closed: Optional[str] = None,
                 hand_resolved: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """A record states what was observed. It never asserts what was not.

    A merge is not a test run, so ``tests_passed`` is ``unknown`` unless a
    status check on the merge commit said otherwise.

    ``review_verdict`` is the ``**Verdict:**`` reading a review-gate sub-task's
    own artefact carried, if one was read. ``None`` means no reading was
    taken -- either the sub-task declares no review artefact, or nothing
    could be read -- and the key is OMITTED entirely rather than stamped as
    null, so every record written before this parameter existed keeps its
    exact meaning.

    ``sub_issue_closed`` is ``close_sub_issue``'s outcome, stamped the same
    way for the same reason (I-8): ``None`` means no closure was attempted --
    either the sub-task carries no sub-issue, or the merge did not land on
    an accepted base -- and the key is OMITTED rather than stamped null, so
    every record written before sub-issues existed keeps its exact meaning.

    ``hand_resolved`` is the Hand-Resolved Summary ``summarise_hand_resolved``
    returned for this pull request. Stamped the same way and for the same
    reason (I-3): ``None`` means no summary was supplied and the key is
    OMITTED so a record written before this parameter existed keeps its exact
    meaning (I-2 reads that absence as not-recorded, never as clean). Unlike
    ``review_verdict`` and ``sub_issue_closed``, a caller mapping a pull
    request to a sub-task always has a summary to supply -- even an empty
    file list is a measurement -- so every new record carries this key (I-1).
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
    if sub_issue_closed is not None:
        record["sub_issue_closed"] = sub_issue_closed
    if hand_resolved is not None:
        record["hand_resolved"] = hand_resolved
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


def new_state(contract_slug: str, tasks: List[SubTask],
             base: Optional[str] = None) -> Dict[str, Any]:
    """A fresh position: every sub-task pending, nothing dispatched.

    ``base`` is the parent branch every sub-task's own branch will be cut
    from once it is released. ``None`` means "the repository default
    branch" and is resolved here, inside this one function, rather than at
    every call site -- the same "resolved in one place" shape
    ``verify_issue_link.py``'s analogous ``declared_base`` parameter uses.
    Each fresh entry also carries ``issue: None`` and ``brief: None`` --
    neither exists yet for a sub-task that has not been opened.
    """
    resolved_base = base if base is not None else default_branch()
    return {
        "contract": contract_slug,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "sub_tasks": {t.id: {"status": "pending", "branch": None, "pull_request": None,
                             "issue": None, "base": resolved_base, "brief": None}
                      for t in tasks},
    }


def record_sub_task_identity(state: Dict[str, Any], subtask_id: str, issue: int,
                             base: str, brief: str) -> Dict[str, Any]:
    """Stamp a sub-task's sub-issue, declared base and brief path into its entry.

    The sibling of ``mark_dispatched``: pure, returns a new state rather than
    mutating the one it is given, and called by ``/flow`` Step 2.7 through
    ``--record-subtask <id> --issue <n> --base <branch> --brief <path>``.
    """
    st = copy.deepcopy(state)
    if subtask_id in st["sub_tasks"]:
        st["sub_tasks"][subtask_id].update({"issue": issue, "base": base, "brief": brief})
    return st


def reconcile_subtask_identity(state_entry: Dict[str, Any],
                               brief_fields: Dict[str, Any]) -> Optional[str]:
    """Compare a state entry's issue/base against its brief's id:/base: -- I-7.

    Pure: takes no path and touches no disk -- the caller reads the brief
    and hands its frontmatter fields in. A mismatch is REFUSED, never
    reconciled: this returns a description naming both readings, and the
    caller is the one that halts dispatch on a non-``None`` result. A key
    missing on either side is not itself a mismatch -- there is nothing to
    compare a state entry against before a brief exists.
    """
    mismatches: List[str] = []
    entry_issue = state_entry.get("issue")
    brief_issue_raw = brief_fields.get("id")
    if entry_issue is not None and brief_issue_raw not in (None, ""):
        try:
            brief_issue: Any = int(str(brief_issue_raw).lstrip("#"))
        except ValueError:
            brief_issue = brief_issue_raw
        if entry_issue != brief_issue:
            mismatches.append(
                "issue: state entry says %r, brief says %r" % (entry_issue, brief_issue_raw))

    entry_base = state_entry.get("base")
    brief_base = brief_fields.get("base")
    if entry_base is not None and brief_base not in (None, "") and entry_base != brief_base:
        mismatches.append(
            "base: state entry says %r, brief says %r" % (entry_base, brief_base))

    return "; ".join(mismatches) if mismatches else None


def base_not_declared(state: Dict[str, Any], subtask_id: str,
                       default_base: str) -> Optional[str]:
    """Refuse a dispatch whose own entry declares no base beside a sibling
    that already declares a real parent -- Defect Two, second half.

    Pure. Fires only when BOTH hold: the subject's own entry has no base
    (the key is missing, or it is ``null``), and at least one OTHER entry
    in the same state declares a base that is not ``default_base``.
    Otherwise returns ``None`` -- this is I-8's own carve-out, kept intact:
    a state where no entry declares a non-default base triggers nothing,
    however the subject's own entry reads, and it dispatches from
    ``default_base`` exactly as before this refusal existed. The subject's
    own entry is never counted among the "other" entries, and an id with no
    entry in the state at all counts as having no base, the same as a
    present entry with a missing or null base key.

    Returns a description naming every other declared base on record, for
    the caller to print as the refusal's detail -- never a bare boolean --
    so the operator sees the remedy (record the sub-task's own identity
    with ``--record-subtask ... --base <parent>``) without having to go
    read the state store by hand.
    """
    sub_tasks = state.get("sub_tasks", {})
    subject = sub_tasks.get(subtask_id) or {}
    if subject.get("base"):
        return None

    other_bases = {
        entry.get("base")
        for tid, entry in sub_tasks.items()
        if tid != subtask_id and entry.get("base")
    }
    other_bases.discard(default_base)
    if not other_bases:
        return None

    return (
        "sub-task %r declares no base, but this state already declares %s on "
        "another sub-task in the same contract -- record this sub-task's own "
        "identity with --record-subtask %s --issue <n> --base <parent> "
        "--brief <path> (running /task in Parent-aware mode first if it has "
        "no brief yet), then dispatch again"
        % (subtask_id, sorted(other_bases), subtask_id)
    )


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


def backfill_state(state: Dict[str, Any], tasks: List[SubTask]) -> Dict[str, Any]:
    """Add a pending entry for every planned id the stored state lacks.

    Defect Two: a sub-task appended to a contract after its state store was
    first written is invisible to ``--record-subtask`` and to every other
    read of ``state["sub_tasks"]`` until something adds it. This is that
    something, applied by ``main()`` right after loading so every existing
    path -- including the refusal of an id outside the plan -- works on the
    complete set. Pure: returns a new state, never mutates the one it is
    given.

    Each added entry carries ``new_state``'s own six keys, with ``base``
    explicitly ``None`` -- never the repository default branch. The only
    base ``main()`` holds at this point is ``default_branch()``, and
    stamping it here would silently cut a backfilled sub-task from the
    default branch even where a sibling in this same contract carries a
    declared parent branch (Defect Two, second half; see
    ``base_not_declared``, the refusal that catches exactly that). It only
    ever adds: an existing entry, whatever it already carries, is left
    byte-identical, and an entry whose id is no longer planned is never
    removed.
    """
    st = copy.deepcopy(state)
    sub_tasks = st.setdefault("sub_tasks", {})
    for t in tasks:
        if t.id not in sub_tasks:
            sub_tasks[t.id] = {"status": "pending", "branch": None, "pull_request": None,
                               "issue": None, "base": None, "brief": None}
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


def create_branch(branch: str, base: str, issue: Optional[int] = None) -> Tuple[bool, str]:
    """Cut a sub-task branch from a freshly fetched ``base``.

    Never from whatever happens to be checked out -- a sub-task seeded from
    another branch inherits its commits and its review surface. ``base`` is
    the sub-task's own declared parent branch, not necessarily the
    repository default branch; the caller decides which.

    With an ``issue`` and a working ``gh``, the branch is cut through
    ``gh issue develop`` so it is registered against its sub-issue before it
    exists locally, then fetched and checked out. Without an issue, or when
    ``gh`` fails, this falls back to the plain ``git switch -c`` form and
    says which path was taken -- a silent fallback is what hides a missing
    linked branch.

    Three outcomes are named distinctly in the returned detail, never
    conflated: (1) ``gh issue develop`` registered the branch and the local
    checkout followed it -- success; (2) ``gh issue develop`` registered the
    branch but the local checkout itself failed -- the branch now exists on
    origin, so this is reported on its own terms rather than falling through
    to the plain-git path below, which would misreport a branch ``gh`` just
    correctly created as "branch already exists", a wrong detail worse than
    a silent one; (3) ``gh issue develop`` was never called, or it failed
    outright, so the plain-git path ran and the detail says exactly that.
    """
    if issue is not None:
        code, _out = _run(["gh", "issue", "develop", str(issue), "--name", branch,
                           "--base", base])
        if code == 0:
            _run(["git", "fetch", "origin", branch])
            checkout_code, checkout_out = _run(["git", "switch", branch])
            if checkout_code == 0:
                return True, (checkout_out or
                             f"registered {branch} against issue {issue} via gh issue develop")
            # Outcome (2): gh already registered the branch on origin -- the
            # local checkout is what failed. Report that on its own terms;
            # never fall through to the "branch already exists" check below,
            # which would misreport a branch gh just correctly created as a
            # fresh-dispatch collision.
            return False, (
                f"gh issue develop registered {branch} against issue {issue}, but the "
                f"local checkout failed ({checkout_out or 'no output'})"
            )
        # Outcome (3), gh half: gh issue develop itself failed outright.
        gh_fallback_detail = f" (gh issue develop failed for issue {issue}, fell back to plain git)"
    else:
        gh_fallback_detail = ""

    if _run(["git", "rev-parse", "--verify", branch])[0] == 0:
        return False, "branch already exists"
    if _run(["git", "fetch", "origin", base])[0] != 0:
        return False, "could not fetch origin/" + base
    code, out = _run(["git", "switch", "-c", branch, "origin/" + base])
    detail = (out or ("created " + branch)) + gh_fallback_detail
    return code == 0, detail


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


def declared_phase(task_block_text: Optional[str]) -> Optional[str]:
    """Read the ``phase:`` line out of a block's own TASK block.

    Returns ``RED`` or ``GREEN`` verbatim -- the closed set, read exactly,
    never inferred or normalised. ``None`` is returned both for a TASK block
    that declares no phase and for the absence of a TASK block altogether
    (``task_block_text`` is ``None``) -- the same answer on purpose, because
    in both cases the contract did not say. A value outside the closed set
    (wrong case, a near-miss word such as ``REVIEW`` or ``REFACTOR``) also
    reads as ``None`` rather than being guessed at.

    Scoped to the TASK block's own text: a ``phase:`` line sitting in prose
    outside the fenced block is not a declaration, so the caller must pass
    ``extract_task_block(...)``'s result rather than the whole block body.
    """
    if not task_block_text:
        return None
    matches = re.findall(r"^[ \t]*phase:[ \t]*(\S+)[ \t]*$", task_block_text, re.M)
    if not matches:
        return None
    values = {value.strip() for value in matches}
    if len(values) > 1:
        return None
    value = matches[0].strip()
    return value if value in ("RED", "GREEN") else None


def _declared_review_verdict_file(task: SubTask) -> Optional[str]:
    """The one path under ``.claude/reviews/`` a sub-task's own files declare, if any.

    The declared-path rule both ``build_dispatch`` and ``main`` apply when
    picking the verdict file (MECHANISMS.md:149, VOCABULARY.md:40,
    project-profile.md:60) -- one function so the two sites cannot drift.
    """
    return next((f for f in task.files if f.startswith(".claude/reviews/")), None)


def build_dispatch(task: SubTask, contract_slug: str, contract_path: str,
                   block_body: str, issue: Optional[int] = None,
                   base: Optional[str] = None, brief: Optional[str] = None,
                   needs_issue: bool = False) -> Dict[str, Any]:
    """Everything needed to start one sub-task, and nothing more.

    This produces the packet. It does not run anything: implementation needs a
    model, and a script cannot be one. The caller executes it.

    ``issue``, ``base`` and ``brief`` are the sub-task's own identity fields,
    read out of its state entry by the caller -- this function never reads
    state itself. ``needs_issue`` mirrors ``needs_agent``: the caller sets it
    true when the contract declares two or more mergeable sub-tasks and the
    state entry carries no ``issue``, so a caller never dispatches a
    sub-task that still has no sub-issue created for it.

    ``cycle`` and ``cycle_basis`` (Extension Point 12) are the Sub-Task
    Cycle: exactly one stage (I-6), decided by what the block DECLARES and
    never by who is assigned (Non-Goals -- no ``RED_STAGE_AGENT``). First
    match wins, four arms:
      1. ``task.files`` names a path under ``.claude/reviews/`` -> one
         ``review`` stage, basis ``verdict-bearing`` -- the same declared-path
         rule ``main`` already applies when it picks the verdict file
         (MECHANISMS.md:149, VOCABULARY.md:40, project-profile.md:60).
      2. ``declared_phase(...)`` is ``RED`` -> one ``red`` stage, basis
         ``declared-phase``.
      3. ``declared_phase(...)`` is ``GREEN`` -> one ``green`` stage, basis
         ``declared-phase``.
      4. otherwise -> one ``unphased`` stage, basis ``no-declared-phase``
         (I-7) -- the contract did not say, and the loop never invents a red
         stage it did not ask for.
    Every stage carries the block's own agent and the constant isolation
    ``fresh-subagent``.
    """
    block = extract_task_block(block_body)

    verdict_file = _declared_review_verdict_file(task)
    if verdict_file:
        stage, basis = "review", "verdict-bearing"
    else:
        phase = declared_phase(block)
        if phase == "RED":
            stage, basis = "red", "declared-phase"
        elif phase == "GREEN":
            stage, basis = "green", "declared-phase"
        else:
            stage, basis = "unphased", "no-declared-phase"
    cycle = [{"stage": stage, "agent": task.agent, "isolation": "fresh-subagent"}]

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
        "issue": issue,
        "base": base,
        "brief": brief,
        "needs_issue": needs_issue,
        "cycle": cycle,
        "cycle_basis": basis,
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


#: Extension Point 6. The closed set of moves ``advance()`` can return.
#: ``contract-defect`` is checked before every other move, so it is the one
#: an operator meets when a contract is malformed (Open Question one).
#: New Mechanisms' extension seam: a new move adds one member here and one
#: arm to ``next_command_for``, in the same change -- the totality test goes
#: red if only one of the two is done.
ADVANCE_ACTIONS = (
    "contract-defect", "nothing-planned", "escalate", "awaiting-merge",
    "complete", "dispatch", "blocked",
)


def next_command_for(
    move: Dict[str, Any], contract_slug: str
) -> Dict[str, Any]:
    """The Next Command: the runnable line for the loop's own next move.

    New Mechanisms: "a human-facing next step is data the owner returns,
    never prose a caller composes." One arm per member of ``ADVANCE_ACTIONS``,
    plus a fail-closed fallback for an action outside the closed set.

    ``move`` is ``advance()``'s own return mapping, never a bare action
    string -- the blocked arm's reason names what holds each sub-task, and
    the awaiting-merge arm's reason names the awaiting sub-task and its
    branch. Neither is derivable from an action string alone.

    I-5: ``commands`` empty is a valid, meaningful value and always travels
    with a non-empty ``reason``. ``blocked`` is the only move that returns an
    empty ``commands`` list; every other real move returns at least one line.

    ``complete`` always hands off to /verify-before-done, regardless of how
    many mergeable sub-tasks the contract declares. Routing a multi-sub-task
    contract's completion to the parent pull request is deferred -- see
    .claude/concepts/followups/2026-09-23-complete-move-routes-parent-pull-request.followup.md.
    """
    action = move.get("action")

    if action == "dispatch":
        return {
            "commands": ["/clear", "/advance %s" % contract_slug],
            "reason": "a sub-task is ready to dispatch; the next move is a fresh /advance, and "
                      "clearing keeps this session's context out of it",
        }

    if action == "awaiting-merge":
        awaiting = list(move.get("awaiting") or [])
        parts = ["%s (branch %s)" % (tid, branch_for(contract_slug, tid)) for tid in awaiting]
        return {
            "commands": ["/pr-merged <pr-number>"],
            "reason": ("waiting on a pull request to merge for " + "; ".join(parts))
                      if parts else "a sub-task is out for merge",
        }

    if action in ("escalate", "nothing-planned", "contract-defect"):
        return {
            "commands": ["/design-first %s" % contract_slug],
            "reason": "the remedy is amending the contract",
        }

    if action == "complete":
        return {
            "commands": ["/verify-before-done"],
            "reason": "every sub-task has a completion record",
        }

    if action == "blocked":
        blocked = move.get("blocked") or {}
        holders = "; ".join("%s <- %s" % (tid, ", ".join(why)) for tid, why in blocked.items())
        return {
            "commands": [],
            "reason": "nothing is ready to dispatch; " + (holders or "no sub-task is released"),
        }

    return {
        "commands": [],
        "reason": "advance() returned an action outside ADVANCE_ACTIONS: %r" % (action,),
    }


# ---------------------------------------------------------------------------
# Hand-resolved files
# ---------------------------------------------------------------------------
def summarise_hand_resolved(commit_shas: List[str],
                            git_combined_diff: Callable[[str], Tuple[List[str], Optional[int]]],
                            ensure_local: Optional[Callable[[str], bool]] = None,
                            commit_present: Optional[Callable[[str], bool]] = None,
                            ) -> Dict[str, Any]:
    """The Hand-Resolved Summary -- four facts, never one list.

    ``files``: paths differing from BOTH parents of a merge commit -- resolved
    by hand, or changed during the merge in a way neither side contained.
    Both entered without ever appearing as a reviewable diff. Ordered,
    de-duplicated, keeping first-seen order.

    ``merge_commits``: how many of the reported commits carried two or more
    parents and were therefore inspected. Zero means nothing was
    detectable -- the pull request's own commits contained no merge commit
    to read -- which is a different claim from ``files`` being empty because
    every inspected merge was clean. Collapsing the two into one list is
    exactly the overclaim Alternatives Considered rejects (Option D).

    ``commits_inspected``: every commit the pull request reported, whatever
    its parent count. An empty ``commit_shas`` asks git nothing at all and
    returns all zeroes -- a pull request nobody could inspect.

    ``commits_unread``: how many reported commits ``git_combined_diff``
    answered ``unknown`` for, even after the one fetch attempt below --
    Extension Point 2, W-3. Never compared with an integer directly: an
    ``unknown`` parent count is Python ``None``, and ``None >= 2`` raises.

    Each reported commit is read once, in reported order (W-1) -- twice only
    for a commit re-read after the fetch below. ``ensure_local`` and
    ``commit_present`` are both optional and both default to ``None``;
    ``detect_resolved_files`` passes neither, so its own callers keep the
    original one-read-per-commit walk exactly (W-5).

    With BOTH supplied, and at least one commit unread after its first read:
    ``commit_present`` is asked about each unread commit in reported order,
    stopping at the first one it reports absent (W-2, W-2a) -- a commit that
    is present but simply unshowable (case D, or a timed-out ``rev-list``)
    can never be helped by a fetch, so the single fetch this walk ever makes
    must never be spent on one. If one is found absent, ``ensure_local`` is
    called exactly once for the whole walk, aimed at that commit, whatever
    it answers -- and every commit whose first read was unknown (not only
    the fetched one) is re-read exactly once more, since one fetch can bring
    down more than the one commit it targeted. If every unread commit
    answers present, no fetch runs and no commit is re-read: nothing here
    could ever change what an already-present, unshowable commit reads.

    A final ``unknown`` (whether from the first read or the one re-read)
    adds one to ``commits_unread`` and nothing else.
    """
    first_reads: List[Tuple[str, List[str], Optional[int]]] = []
    unread_shas: List[str] = []
    for sha in commit_shas:
        files, parents = git_combined_diff(sha)
        first_reads.append((sha, files, parents))
        if parents is None:
            unread_shas.append(sha)

    reads = first_reads
    if unread_shas and ensure_local is not None and commit_present is not None:
        first_absent: Optional[str] = None
        for sha in unread_shas:
            if not commit_present(sha):
                first_absent = sha
                break
        if first_absent is not None:
            ensure_local(first_absent)
            reread = {sha: git_combined_diff(sha) for sha in unread_shas}
            reads = [
                (sha, reread[sha][0], reread[sha][1]) if sha in reread else (sha, files, parents)
                for sha, files, parents in first_reads
            ]

    files_out: List[str] = []
    merge_commits = 0
    commits_unread = 0
    for _sha, files, parents in reads:
        if parents is None:
            commits_unread += 1
            continue
        if parents >= 2:
            merge_commits += 1
            files_out.extend(files)
    seen: set = set()
    deduped = [f for f in files_out if not (f in seen or seen.add(f))]
    return {
        "files": deduped,
        "merge_commits": merge_commits,
        "commits_inspected": len(commit_shas),
        "commits_unread": commits_unread,
    }


def detect_resolved_files(commit_shas: List[str],
                          git_combined_diff: Callable[[str], Tuple[List[str], int]]) -> List[str]:
    """Files differing from BOTH parents of a merge commit.

    A projection of ``summarise_hand_resolved(...)["files"]`` -- kept as its
    own public name because the walk must not happen twice, and because its
    signature, ordering, de-duplication and skip-commits-with-fewer-than-two-
    parents rule are load-bearing for existing callers and their mutation
    probes (Extension Point 2).
    """
    return summarise_hand_resolved(commit_shas, git_combined_diff)["files"]


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


def gh_pr(ref: "int | str") -> Optional[Dict[str, Any]]:
    """Ask GitHub about one pull request -- Extension Point 5.

    ``ref`` is a Pull-request reference: either a number, in this repository,
    or an ``https://`` link, resolved by ``gh`` itself per call -- no
    ``--repo`` flag, and nothing written to the process environment. Either
    form is passed to ``gh pr view`` as its one positional argument.
    """
    code, out = _run(["gh", "pr", "view", str(ref), "--json",
                      "number,title,state,mergedAt,mergeCommit,headRefName,baseRefName,url,commits,statusCheckRollup"])
    if code != 0 or not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def repo_view(name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """A repository's identity -- Extension Point 6, the new edge X-3/X-5 need.

    Runs ``gh repo view [<name>] --json nameWithOwner,defaultBranchRef``.
    ``name`` absent (``None``) asks about the checkout's own repository;
    given an ``owner/name``, asks about that one instead -- never with
    ``--repo``, since this is a read of a DIFFERENT repository's identity,
    not a redirection of this run's own GitHub calls. Returns
    ``{"nameWithOwner": <str>, "defaultBranchRef": <str>}`` or ``None`` when
    ``gh`` fails or answers non-JSON; never raises.

    Measured (t2's own probe, since this was ASSUMED, not verified, at
    contract time): ``gh``'s own JSON answers ``defaultBranchRef`` as a
    nested ref object, ``{"name": "master"}``, never a bare string --
    flattened to its ``name`` here, so every consumer of this edge (X-5's
    accepted-base set, and every test double that stubs this edge with a
    flat string) reads one shape, never gh's own GraphQL nesting.
    """
    cmd = ["gh", "repo", "view"]
    if name:
        cmd.append(name)
    cmd += ["--json", "nameWithOwner,defaultBranchRef"]
    code, out = _run(cmd)
    if code != 0 or not out:
        return None
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    default_branch = payload.get("defaultBranchRef")
    if isinstance(default_branch, dict):
        default_branch = default_branch.get("name")
    return {"nameWithOwner": payload.get("nameWithOwner"), "defaultBranchRef": default_branch}


def git_combined_diff(sha: str) -> Tuple[List[str], Optional[int]]:
    """A commit's Commit reading -- files, and a parent count, or ``unknown``.

    First match wins (Data Shapes, CR-1 to CR-4):

    - CR-1: ``git rev-list --parents -n 1 <sha>`` exits non-zero, or exits
      zero but prints nothing -- the commit could not be read at all, and
      this returns ``([], None)``. ``None`` (Python's ``unknown``) is never
      compared with an integer directly by a caller; it must be checked for
      first, since ``None >= 2`` raises in Python 3.
    - CR-2: fewer than two parents -- ``git show`` never runs, because a
      non-merge commit has no combined diff to read.
    - CR-3: two or more parents and ``git show --cc --name-only --format=
      <sha>`` itself exits non-zero -- the merge could not be read either,
      so this returns ``([], None)`` too. This is the t4 artefact's case D,
      which the old code reported as a clean merge by discarding the exit
      code entirely.
    - CR-4: two or more parents and ``git show`` exits zero -- an empty
      listing here is a genuinely clean merge, reported with its true parent
      count.
    """
    code, parents = _run(["git", "rev-list", "--parents", "-n", "1", sha])
    if code != 0 or not parents.strip():
        return [], None
    parent_count = max(len(parents.split()) - 1, 0)
    if parent_count < 2:
        return [], parent_count
    show_code, out = _run(["git", "show", "--cc", "--name-only", "--format=", sha])
    if show_code != 0:
        return [], None
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


def commit_present(sha: str) -> bool:
    """Whether ``sha`` is already in the local clone -- Extension Point 3a.

    Runs the same ``git cat-file -e <sha>^{commit}`` presence check
    ``ensure_commit_local`` runs first, answering yes only on exit 0. Never
    raises, never fetches -- it exists so the walk can decide WHICH unread
    commit its one fetch attempt is worth aiming at (W-2), without spending
    that attempt on a commit that is already present but simply unshowable
    (case D, or a timed-out ``rev-list``), which a fetch could never help.
    """
    code, _out = _run(["git", "cat-file", "-e", f"{sha}^{{commit}}"])
    return code == 0


def ensure_commit_local(sha: str, ref: str) -> bool:
    """Confirm the merge commit is in the local clone -- Defect One's edge.

    Consulted only when a first read at ``sha`` yields nothing, so a
    commit already present costs one presence check here, and never a
    fetch. Runs
    ``git cat-file -e <sha>^{commit}``; only on failure does it run ONE
    ``git fetch origin <ref>`` -- ``ref`` is the ref where this commit lives,
    never the repository default branch: the merge-commit-verdict caller
    passes the pull request's own ``baseRefName``, and the Hand-Resolved
    walk (W-2/X-8) passes ``pull/<n>/head``, the pull request's own ref --
    and checks presence again, whatever the fetch's own
    exit code reports. A fetch that itself succeeds is not proof the commit
    is now present; only the re-check answers that. Every call goes through
    ``_run``, so no real git process starts under a patched module, and no
    more than one fetch is ever attempted per call.
    """
    presence_cmd = ["git", "cat-file", "-e", f"{sha}^{{commit}}"]
    code, _out = _run(presence_cmd)
    if code == 0:
        return True
    _run(["git", "fetch", "origin", ref])
    code, _out = _run(presence_cmd)
    return code == 0


def default_branch() -> str:
    code, out = _run(["git", "symbolic-ref", "refs/remotes/origin/HEAD"])
    return out.rsplit("/", 1)[-1] if code == 0 and out else "master"


def _read_issue_state(issue: int) -> Optional[str]:
    """The sub-issue's own state, read as an allow list -- I-10.

    Returns ``"OPEN"`` or ``"CLOSED"`` only when the payload actually says
    so. Everything else -- ``gh`` unreachable, unparseable JSON, a payload
    that parses to something other than a mapping (``json.loads`` can return
    a list, and ``list.get`` does not exist), a missing ``state`` key, or a
    value outside the two recognised states -- returns ``None``. This is
    deliberately an allow list rather than a "not CLOSED" catch-all: reading
    an unrecognised payload as OPEN would fire the close mutation having
    read nothing.
    """
    code, out = _run(["gh", "issue", "view", str(issue), "--json", "state"])
    if code != 0:
        return None
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    state = payload.get("state")
    if not isinstance(state, str):
        return None
    state = state.upper()
    return state if state in ("OPEN", "CLOSED") else None


def close_sub_issue(issue: int, pr_url: str) -> str:
    """Close a sub-issue after its pull request has merged -- I-10.

    Refuses to mutate anything before the issue's own state has been read,
    and only ever acts on an explicit ``OPEN`` reading -- never on the
    absence of ``CLOSED``. An issue already CLOSED is reported
    ``already-closed`` without a second write -- the read-before-close
    ordering that makes a re-run idempotent. An OPEN issue is closed and its
    state is re-read to confirm the outcome, reporting ``closed`` or
    ``close-failed``. Anything unverifiable -- unreachable ``gh``, malformed
    JSON, a non-mapping payload, or a value outside OPEN/CLOSED -- reports
    ``unverifiable`` rather than being read as either.
    """
    state = _read_issue_state(issue)
    if state is None:
        return "unverifiable"
    if state == "CLOSED":
        return "already-closed"

    close_code, _out = _run(["gh", "issue", "close", str(issue), "--reason", "completed",
                             "--comment", pr_url])
    if close_code != 0:
        return "close-failed"

    after = _read_issue_state(issue)
    if after is None:
        return "unverifiable"
    return "closed" if after == "CLOSED" else "close-failed"


_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def read_brief_frontmatter(brief_path: Path) -> Optional[Dict[str, str]]:
    """A minimal frontmatter reader for a brief's ``id:`` and ``base:`` keys.

    Deliberately narrow: ``reconcile_subtask_identity`` only ever compares
    these two fields against a state entry (I-7), so this reads only what
    that check needs rather than duplicating ``verify_issue_link.py``'s full
    frontmatter vocabulary -- the two scripts are synced into a sibling
    plugin independently, and cross-importing between them would couple
    their sync lifecycles. That is a worse problem than a small private
    reader of two keys, so this stays its own minimal parser rather than
    reusing the sibling's.

    Returns ``None`` when the brief cannot be read at all -- a recorded
    brief path that no longer resolves is unverifiable, not "nothing to
    compare"; I-7 is a refusal rule, and a caller must refuse the dispatch
    on ``None`` rather than fail open. An empty mapping is still returned
    when the file *is* readable but carries no frontmatter block, since
    that genuinely is nothing to compare against.
    """
    try:
        text = brief_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = _FRONTMATTER.match(text.replace("\r\n", "\n"))
    if not match:
        return {}
    fields: Dict[str, str] = {}
    for line in match.group(1).split("\n"):
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


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


def _render_hand_resolved_reading(entry: Dict[str, Any]) -> str:
    """One of the Hand-Resolved Summary's five readings, as prose for a person.

    Ordered, first match wins (Data Shapes, R-1 to R-10). ``U`` is
    ``commits_unread``:

    - R-1: ``source == "not-recorded"`` -> ``not-recorded`` (unchanged).
    - R-2: a ``stored-record`` entry with no ``commits_unread`` key ->
      ``not-recorded``. A record written before this contract cannot tell
      "no commit was unread" apart from "nobody counted", and its ``clean``
      may be the very W1 overclaim this contract fixes.
    - R-3: ``commits_unread`` present but not a genuine, non-negative,
      non-bool integer -> ``not detectable (unread count unreadable)``. A
      caller cannot trust a count it cannot recognise.
    - R-4: ``merge_commits`` malformed or non-positive, and ``U > 0`` ->
      ``not detectable (unread commits: U)`` -- the unread count is never
      silently dropped behind the uncounted wording below.
    - R-5: ``merge_commits`` malformed or non-positive (``U`` zero or
      absent) -> ``not detectable (no merge commits inspected)`` (unchanged).
    - R-6: ``files`` malformed -> ``not detectable (files unreadable)``
      (unchanged). Never raises: a hand-edited or partially-migrated record
      must be reported as unreadable, never allowed to crash an otherwise
      read-only render.
    - R-7: ``files`` non-empty -> the comma-joined list, with an
      ``" (unread commits: U)"`` suffix when ``U > 0``.
    - R-8: ``U > 0`` (an inspected merge, empty file list, some commit still
      unread) -> ``not detectable (unread commits: U)``. A genuinely
      inspected merge does not mask a fetch failure on a different commit.
    - R-9: no ``commits_unread`` key at all (a hand-built or otherwise
      unmeasured entry) -> ``not detectable (unread count unreadable)``. An
      absent key is never read as zero.
    - R-10: otherwise -- a present, well-formed zero unread count -- ->
      ``clean``. This is the only rule that can ever answer ``clean``.
    """
    if entry.get("source") == "not-recorded":
        return "not-recorded"  # R-1

    has_unread_key = "commits_unread" in entry
    commits_unread = entry.get("commits_unread")
    unread_ok = (has_unread_key and isinstance(commits_unread, int)
                and not isinstance(commits_unread, bool) and commits_unread >= 0)

    if entry.get("source") == "stored-record" and not has_unread_key:
        return "not-recorded"  # R-2

    if has_unread_key and not unread_ok:
        return "not detectable (unread count unreadable)"  # R-3

    merge_commits = entry.get("merge_commits")
    merge_ok = (isinstance(merge_commits, int) and not isinstance(merge_commits, bool)
               and merge_commits > 0)
    if not merge_ok:
        if unread_ok and commits_unread > 0:
            return "not detectable (unread commits: %d)" % commits_unread  # R-4
        return "not detectable (no merge commits inspected)"  # R-5

    files = entry.get("files")
    if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
        return "not detectable (files unreadable)"  # R-6

    if files:
        joined = ", ".join(files)
        if unread_ok and commits_unread > 0:
            return "%s (unread commits: %d)" % (joined, commits_unread)
        return joined  # R-7

    if unread_ok and commits_unread > 0:
        return "not detectable (unread commits: %d)" % commits_unread  # R-8

    if not has_unread_key:
        return "not detectable (unread count unreadable)"  # R-9

    return "clean"  # R-10


def _parse_pr_reference(value: str) -> "int | str":
    """A ``--pr`` argument -- a Pull-request reference (Data Shapes, Extension Point 8).

    ``int(value)`` first, exactly today's rule -- so ``0`` and negatives keep
    parsing and reach ``gh_pr``, which answers them ``not-found``, the same
    skip every other unresolvable number gets. Otherwise, a value starting
    ``https://`` is a link, carried verbatim. Anything else is neither, and
    argparse reports it as an invalid value (exit 2), unchanged from today.
    """
    try:
        return int(value)
    except ValueError:
        pass
    if value.startswith("https://"):
        return value
    raise argparse.ArgumentTypeError(
        "must be a pull-request number or an https:// link, got %r" % value)


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Close a sub-task whose pull request merged.")
    ap.add_argument("--contract", required=True, help="contract slug or path")
    ap.add_argument("--pr", action="append", type=_parse_pr_reference, default=[],
                    help="pull request number or https:// link (repeatable)")
    ap.add_argument("--status", action="store_true", help="report the plan without writing anything")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--dry-run", action="store_true", help="compute everything, write nothing")
    ap.add_argument("--dispatch", metavar="SUBTASK", help="start this sub-task: cut its branch and record it")
    ap.add_argument("--resume", action="store_true", help="report the stored position and what it waits for")
    ap.add_argument("--record-subtask", metavar="ID",
                    help="stamp a sub-task's issue, base and brief into the state store")
    ap.add_argument("--issue", type=int, help="the sub-task's own sub-issue number, with --record-subtask")
    ap.add_argument("--base", metavar="BRANCH",
                    help="the sub-task's declared base branch, with --record-subtask")
    ap.add_argument("--brief", metavar="PATH", help="the sub-task's brief path, with --record-subtask")
    args = ap.parse_args()

    # G-1 (Open Question 1, answered yes): a non-empty GH_REPO retargets every
    # `gh` call this process makes, including `gh issue close` -- so refuse
    # before touching the contract, git or gh at all, rather than let a
    # --pr or --dispatch run silently mutate another repository. The script
    # never sets GH_REPO itself; this only ever reads it to refuse.
    if os.environ.get("GH_REPO") and (args.pr or args.dispatch):
        print(json.dumps({
            "error": "gh-repo-set",
            "detail": "GH_REPO is set in the environment; refusing to run --pr or --dispatch, "
                      "which would let every gh call this process makes -- including "
                      "gh issue close -- silently retarget at another repository. Unset "
                      "GH_REPO in this shell and run again; a pull request in another "
                      "repository is passed as its https:// link instead.",
        }))
        return 8

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
    # `base` is already resolved on the line above -- hand it to new_state so
    # a fresh state store costs one subprocess, not two (Extension Points).
    state = load_state(slug) or new_state(slug, tasks, base=base)
    # Defect Two: a sub-task the plan already declares but the stored state
    # was written before may still be entirely absent from it (an amendment
    # appended it after the fact). backfill_state applies right here, before
    # anything below reads `state["sub_tasks"]` -- including --record-subtask,
    # which would otherwise refuse an id /flow's sub-issue step already
    # opened a sub-issue for on GitHub.
    state = backfill_state(state, tasks)

    if args.record_subtask:
        # /flow Step 2.7's writer: stamp one sub-task's issue, declared base
        # and brief path into the state store. Pure computation through
        # record_sub_task_identity; the only mutation here is the write.
        if args.issue is None or not args.base or not args.brief:
            print(json.dumps({"error": "record-subtask-incomplete",
                              "detail": "--record-subtask requires --issue, --base and --brief"}))
            return 2
        # I-5's witness is this entry's issue field, so recording against an
        # id the plan does not contain must never look like it worked: a
        # typo'd or stale id would otherwise write nothing, report success,
        # and leave the next run believing no sub-issue exists -- opening a
        # second one for the same sub-task.
        known_subtask_ids = list(state.get("sub_tasks", {}))
        if args.record_subtask not in known_subtask_ids:
            print(json.dumps({"error": "unknown-sub-task", "sub_task": args.record_subtask,
                              "known": known_subtask_ids}))
            return 2
        state = record_sub_task_identity(state, args.record_subtask, args.issue, args.base, args.brief)
        # Mirrors the report path below: a dry run computes and prints, but
        # never writes, and a status query never mutates either. --resume
        # joins them (Extension Point 10): a flag promising a read-only
        # report must not stamp an identity into the stored position.
        if not args.dry_run and not args.status and not args.resume:
            write_state(slug, state)
        result = {"recorded": args.record_subtask, "issue": args.issue, "base": args.base,
                  "brief": args.brief}
        print(json.dumps(result, indent=2) if args.json else
              f"recorded {args.record_subtask}: issue={args.issue} base={args.base} brief={args.brief}")
        return 0

    # The Declared base set (Data Shapes): the repository default branch,
    # plus every sub-task's own declared base already on record. This is
    # what lets a pull request merged into a parent branch -- every task
    # pull request under this topology -- be recognised as merged rather
    # than reported merged-elsewhere (the measured PR #173 defect).
    declared_bases = {base}
    for entry in state.get("sub_tasks", {}).values():
        entry_base = entry.get("base")
        if entry_base:
            declared_bases.add(entry_base)

    report: Dict[str, Any] = {
        "contract": slug,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sub_tasks": [asdict(t) for t in tasks],
        "blocks": [asdict(b) for b in blocks],
        "defects": [asdict(d) for d in defects],
        "closed": [], "skipped": [], "unmapped": [], "hand_resolved": [], "failed": [],
    }

    # Extension Point 5: seed hand_resolved from the summaries already stored
    # in the loaded completion records, BEFORE the pull-request loop runs --
    # so a read-only run that processes no pull request (criterion two) still
    # reports them. I-2: a record with no hand_resolved key was written before
    # this change and is reported as not-recorded, never as clean.
    for tid, rec in records.items():
        stored = rec.get("hand_resolved")
        # A stored hand_resolved value that is not a mapping -- a hand-edited
        # or partially-migrated record -- carries nothing this loop can read;
        # treated the same as a record with no hand_resolved key at all,
        # never passed to dict() where a bare scalar would raise.
        if isinstance(stored, dict):
            entry = dict(stored)
            entry["sub_task"] = tid
            entry["source"] = "stored-record"
        else:
            entry = {"sub_task": tid, "source": "not-recorded"}
        report["hand_resolved"].append(entry)

    # X-1/X-3, memoised per run: once for None (this checkout's own identity)
    # and once per distinct cross-repository name -- never for a bare number,
    # which never reaches this cache at all.
    _repo_view_cache: Dict[Optional[str], Optional[Dict[str, Any]]] = {}

    def _cached_repo_view(name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if name not in _repo_view_cache:
            _repo_view_cache[name] = repo_view(name)
        return _repo_view_cache[name]

    for ref in args.pr:
        pr = gh_pr(ref)

        # X-1: a bare number never calls repo_view and is never
        # Cross-Repository. X-3: a link is Cross-Repository unless BOTH this
        # checkout's own identity (repo_view(None)) answers, and the owner
        # and name parsed from the payload's own `url` equal it, compared
        # case-insensitively -- any unreadable part fails closed to
        # cross-repository. X-4: a link naming this repository takes exactly
        # the number path from here on.
        is_link = isinstance(ref, str)
        cross_repository = False
        cross_default_branch: Optional[str] = None
        if is_link and pr:
            owner_name = _owner_and_name_from_url(pr.get("url"))
            this_repo = _cached_repo_view(None)
            this_name = (this_repo.get("nameWithOwner") or "") if this_repo else ""
            if owner_name is None or this_repo is None:
                cross_repository = True
            elif ("%s/%s" % owner_name).lower() != this_name.lower():
                cross_repository = True
            if cross_repository:
                # X-5: the accepted base set is this OTHER repository's own
                # default branch alone -- this checkout's declared bases are
                # branches of THIS repository and are never added. The set
                # is empty when the remote identity cannot be read, which
                # yields merged-elsewhere, a halt.
                remote_name = ("%s/%s" % owner_name) if owner_name else None
                remote = _cached_repo_view(remote_name) if remote_name else None
                cross_default_branch = remote.get("defaultBranchRef") if remote else None

        if cross_repository:
            accepted = {cross_default_branch} if cross_default_branch else set()
            verdict = classify_pr(pr, accepted_bases=accepted)
        else:
            verdict = classify_pr(pr, base, accepted_bases=declared_bases)

        if verdict in ("not-found", "not-merged", "merged-elsewhere"):
            report["skipped"].append({"pr": ref, "verdict": verdict})
            continue

        task = map_pr_to_subtask(pr.get("headRefName", ""), pr.get("title", ""), tasks, slug)
        if task is None:
            report["unmapped"].append({"pr": ref, "branch": pr.get("headRefName")})
            continue

        shas = [c.get("oid") for c in (pr.get("commits") or []) if c.get("oid")]
        if cross_repository:
            # X-6: none of git_combined_diff, commit_present,
            # ensure_commit_local or file_at_commit is ever called for a
            # Cross-Repository Pull Request -- none of its commits exist in
            # this clone, so every reported commit is unread, without a read.
            n = len(shas)
            hand_resolved_summary = {
                "files": [], "merge_commits": 0, "commits_inspected": n, "commits_unread": n,
            }
        else:
            # Extension Point 1/4: one walk, via summarise_hand_resolved --
            # never detect_resolved_files beside it, which would ask git
            # about every commit twice. X-8: a local pull request's walk
            # gets its own ensure_local closure, aimed at
            # pull/<number>/head -- the payload's own number, never the
            # repository default branch or the review-verdict fetch's base
            # branch -- and commit_present, so at most one fetch is ever
            # spent on the first commit reported absent. With no number in
            # the payload, neither is passed (W-5).
            number_val = pr.get("number")
            if number_val is not None:
                def _walk_ensure_local(sha: str, _n=number_val) -> bool:
                    return ensure_commit_local(sha, "pull/%s/head" % _n)
                hand_resolved_summary = summarise_hand_resolved(
                    shas, git_combined_diff,
                    ensure_local=_walk_ensure_local, commit_present=commit_present)
            else:
                hand_resolved_summary = summarise_hand_resolved(shas, git_combined_diff)
        # Always appended, including an empty file list (I-1): a walk that
        # inspected commits and found nothing conflicted is a measurement,
        # not an absence.
        # A sub-task this run's pull request maps to may already carry a
        # seeded entry from a previous run's stored record (the loop above).
        # This run just watched the pull request resolve -- merged, or
        # closed without merging -- so it knows more than a record written
        # before it ever ran -- drop the stale seeded entry for THIS
        # sub-task only, never the seeded entries other sub-tasks still own.
        report["hand_resolved"] = [
            entry for entry in report["hand_resolved"]
            if not (entry.get("sub_task") == task.id and entry.get("source") != "measured-this-run")
        ]
        report["hand_resolved"].append({
            "pr": ref,
            "sub_task": task.id,
            "source": "measured-this-run",
            **hand_resolved_summary,
        })

        rollup = pr.get("statusCheckRollup")
        checks = rollup[0].get("conclusion") if isinstance(rollup, list) and rollup else None
        merge_sha = (pr.get("mergeCommit") or {}).get("oid")

        review_verdict = None
        verdict_file = _declared_review_verdict_file(task)
        # A pull request that closed WITHOUT merging has no merge commit, so
        # nothing was read and no reading is stamped -- the key stays absent.
        # Stamping "unreadable" here would claim an attempt that never
        # happened. The dependent is already withheld by an older, stronger
        # mechanism: build_record marks this record "failed" for a
        # closed-unmerged pull request, and advance() short-circuits on any
        # failed record before the release check is ever reached.
        if verdict_file and merge_sha:
            if cross_repository:
                # X-6: the merge commit lives in ANOTHER repository, so no
                # read is ever attempted here -- this is the loop's third
                # review reading, distinct from both `unreadable` (the
                # commit is local but the artefact can't be parsed) and
                # `unfetched` (the commit is local-repository but absent
                # from this clone, whose remedy is a fetch). No fetch in
                # this clone can ever reach another repository's merge
                # commit, so reusing `unfetched` here would send the
                # operator to a remedy that can never work.
                review_verdict = "cross-repository"
            else:
                artefact_text = file_at_commit(merge_sha, verdict_file)
                # parse_review_verdict stays pure: it reports what the
                # artefact says, or nothing. "unreadable" means the commit
                # is in the local clone but the artefact still can't be
                # parsed -- absent, malformed, or out of the closed set.
                # "unfetched" means the commit itself never made it into
                # the local clone even after one fetch attempt -- a
                # different failure with a different remedy (fetch it,
                # don't rewrite it), so Defect One's fetch
                # (ensure_commit_local) runs only on a first empty read,
                # and only that outcome decides between the two.
                if artefact_text is None:
                    if ensure_commit_local(merge_sha, pr.get("baseRefName") or base):
                        artefact_text = file_at_commit(merge_sha, verdict_file)
                        reading = parse_review_verdict(artefact_text) if artefact_text is not None else None
                        review_verdict = reading or "unreadable"
                    else:
                        review_verdict = "unfetched"
                else:
                    reading = parse_review_verdict(artefact_text)
                    review_verdict = reading or "unreadable"

        # I-10: close the sub-issue only once a merge into an accepted base
        # is confirmed, and only when this sub-task actually has one --
        # never on a dry run or a status report, since gh issue close is a
        # real mutation, not a local write. X-7: this runs through the
        # UNCHANGED close_sub_issue, whose issue number comes from THIS
        # repository's own state store and whose gh calls carry no --repo,
        # so a cross-repository merge still closes only this repository's
        # sub-issue, never the other repository's.
        sub_issue_closed = None
        task_state_entry = state.get("sub_tasks", {}).get(task.id, {})
        task_issue = task_state_entry.get("issue")
        if (verdict == "merged" and task_issue is not None and not args.dry_run
                and not args.status and not args.resume):
            # The close comment never carries the other repository's link or
            # name (X-7): a cross-repository pull request's own url points
            # at a different repository, and naming it here would be the
            # one place that link could leak into a gh call this repository
            # issues.
            close_comment = "merged in another repository" if cross_repository else pr.get("url", "")
            sub_issue_closed = close_sub_issue(task_issue, close_comment)

        rec = build_record(verdict, merge_sha, pr.get("url", ""), pr.get("mergedAt"), checks,
                           review_verdict=review_verdict, sub_issue_closed=sub_issue_closed,
                           hand_resolved=hand_resolved_summary)
        if not args.dry_run and not args.status and not args.resume:
            write_record(slug, task.id, rec)
        records[task.id] = rec
        (report["failed"] if rec["status"] == "failed" else report["closed"]).append(
            {"pr": ref, "sub_task": task.id, "record": rec})

    report["review_verdicts"] = {
        tid: rec["review_verdict"] for tid, rec in records.items() if "review_verdict" in rec
    }

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

        # Defect Two, second half: an entry with no declared base falls back
        # to `base` (default_branch()) at `declared_task_base` below,
        # silently, even where a sibling in this same contract already
        # declares a real parent branch. This refusal runs BEFORE
        # that fallback is ever read, before the identity check, and before
        # any branch is cut, in every mode including --dry-run -- a dry run
        # must preview the real run, not silently succeed. I-8 stays intact:
        # a state where no OTHER entry declares a non-default base triggers
        # nothing here, and dispatch proceeds exactly as it did before this
        # refusal existed.
        base_refusal = base_not_declared(state, task.id, base)
        if base_refusal:
            print(json.dumps({"error": "base-not-declared", "sub_task": task.id,
                              "detail": base_refusal}))
            return 7

        task_state_entry = state.get("sub_tasks", {}).get(task.id, {})
        # I-1 -- the acceptance criterion this whole feature exists to
        # satisfy: a sub-task branch is cut from ITS OWN declared base, read
        # out of its state entry, never unconditionally from the default
        # branch. I-8: an entry with no base key falls back to base.
        declared_task_base = task_state_entry.get("base") or base
        task_issue = task_state_entry.get("issue")

        # I-7, run before every dispatch: a state entry's issue/base must
        # agree with its own brief. A mismatch REFUSES the dispatch and
        # names both readings -- it is never reconciled silently. No brief
        # recorded yet is not itself a mismatch; there is nothing to compare
        # a state entry against before one exists.
        brief_path_str = task_state_entry.get("brief")
        if brief_path_str:
            brief_fields = read_brief_frontmatter(Path(brief_path_str))
            # A recorded brief path that no longer resolves is unverifiable,
            # never "nothing to compare" -- I-7 is a refusal rule, and
            # reading None as {} here would dispatch on a state entry whose
            # only witness (I-5) cannot be checked against anything.
            if brief_fields is None:
                print(json.dumps({"error": "brief-unreadable", "sub_task": task.id,
                                  "detail": f"recorded brief {brief_path_str!r} could not be "
                                            "read; refusing to dispatch without checking it "
                                            "against the state entry (I-7)"}))
                return 6
            mismatch = reconcile_subtask_identity(task_state_entry, brief_fields)
            if mismatch:
                print(json.dumps({"error": "identity-mismatch", "sub_task": task.id,
                                  "detail": mismatch}))
                return 5

        branch = branch_for(slug, task.id)
        # Extension Point 10 extended to --dispatch: --resume and --status are
        # the same read-only front doors as --dry-run here -- each promises a
        # report of the stored position, never a mutation of it, so all three
        # take the same "compute, never cut, never stamp" path. Mirrors the
        # identical three-flag guard already used for --record-subtask and
        # for closing the sub-issue (both above).
        read_only_dispatch = args.dry_run or args.resume or args.status
        ok, detail = (True, "read-only run") if read_only_dispatch else create_branch(
            branch, declared_task_base, issue=task_issue)
        if not ok:
            print(json.dumps({"error": "branch-failed", "branch": branch, "detail": detail}))
            return 4
        state = mark_dispatched(state, task.id, branch)
        if not read_only_dispatch:
            write_state(slug, state)
        bodies = handoff_bodies(contract.read_text(encoding="utf-8", errors="replace"))
        # needs_issue mirrors needs_agent: true only once the contract is
        # actually orchestrating two or more mergeable sub-tasks (I-6) and
        # this one still carries no sub-issue.
        needs_issue = len(tasks) >= 2 and task_issue is None
        packet = build_dispatch(task, slug, str(contract), bodies.get(task.id, ""),
                                issue=task_issue, base=declared_task_base,
                                brief=task_state_entry.get("brief"), needs_issue=needs_issue)
        # N-2: a read-only run (--dry-run, --resume or --status) never cuts
        # the branch (`ok, detail` above is a stub "read-only run" result),
        # so the packet and the printed line must not claim it did either.
        packet["branch_created"] = None if read_only_dispatch else branch
        if args.json:
            print(json.dumps(packet, indent=2))
        elif read_only_dispatch:
            print(f"would dispatch {task.id} on {branch} -> {task.agent}")
        else:
            print(f"dispatched {task.id} on {branch} -> {task.agent}")
        return 0

    move = advance(tasks, records, state, defects=defects)
    report["next_move"] = move
    report["released"] = move.get("sub_tasks", [])
    report["blocked"] = move.get("blocked", {})
    report["complete"] = move["action"] == "complete"
    report["state"] = state
    # Extension Point 8: the Next Command for this move, so both front doors
    # print one answer instead of each composing an ending.
    report["next_command"] = next_command_for(move, slug)
    if not args.dry_run and not args.status and not args.resume:
        write_state(slug, state)

    if move["action"] == "dispatch":
        bodies = handoff_bodies(contract.read_text(encoding="utf-8", errors="replace"))
        by_id = {t.id: t for t in tasks}
        report["dispatch"] = []
        for tid in move["sub_tasks"]:
            entry = state.get("sub_tasks", {}).get(tid, {})
            report["dispatch"].append(build_dispatch(
                by_id[tid], slug, str(contract), bodies.get(tid, ""),
                issue=entry.get("issue"), base=entry.get("base") or base,
                brief=entry.get("brief"),
                needs_issue=len(tasks) >= 2 and entry.get("issue") is None,
            ))

    # Extension Point 5 / W2: stamp every hand_resolved entry -- seeded
    # stored-record entries, not-recorded placeholders, and entries measured
    # this run alike -- with its own rendered reading, once the list is
    # final and before either output branch reads it. A caller of --json
    # output must never have to reimplement the five-state reading the
    # human-readable branch below already computes; both branches now read
    # the same stamped value instead of two independent renderings that
    # could drift apart.
    for entry in report["hand_resolved"]:
        entry["reading"] = _render_hand_resolved_reading(entry)

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
                who = h.get("sub_task", "?")
                # N-4: name the pull request too when this entry carries one
                # -- a seeded or not-recorded entry has none, and stays
                # identified by sub-task alone. Extension Point 11: a
                # link-valued pr prints bare (never "#<link>"); a number
                # still prints "#<n>".
                pr_value = h.get("pr")
                if pr_value is None:
                    pr_suffix = ""
                elif isinstance(pr_value, str):
                    pr_suffix = f" {pr_value}"
                else:
                    pr_suffix = f" #{pr_value}"
                print(f"  hand-resolved {who}{pr_suffix}: {h['reading']}")
        print(f"  next move: {move['action']}" + (f" - {move.get('detail')}" if move.get("detail") else ""))
        for d in report.get("dispatch", []):
            flag = "  [TASK BLOCK MISSING — author it in the contract]" if d["needs_authoring"] else ""
            print(f"    dispatch {d['sub_task']} -> {d['agent']} on {d['branch']}{flag}")
        # Extension Point 9: the next command is the FINAL line, after the
        # dispatch listing -- a skill that composes its own ending is the
        # second implementation of a rule this script owns.
        nc = report["next_command"]
        if nc["commands"]:
            print("next command: " + ", then ".join(nc["commands"]))
        else:
            print("next command: none — %s" % nc["reason"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
