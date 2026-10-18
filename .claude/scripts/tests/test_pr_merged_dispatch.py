#!/usr/bin/env python3
"""
RED tests for pr_merged.py's dispatch, state entry, preconditions and brief lookup
(contract 2026-10-07-landing-and-loop-hardening, block 7; #451 problems 1, 2 and 5, and D-4).

What they pin:
  * D-1: the base a sub-task is cut from, and where it came from (base_source), through
    --dispatch (refusal "base-not-declared", exit 7) and --status (base, base_source,
    base_problem on each block entry; never a refusal).
  * Problem 2: a --pr run that records a merge writes status, branch, pull_request and base
    into the sub-task's state entry.
  * Problem 5: the Dispatch preconditions on the --dispatch packet (information only), and the
    read-only --preconditions command that /advance decides on.
  * D-4: find_linked_brief returns the parent brief when no header names one.

Fixtures: every contract, brief, conventions file and state store lives in a temporary
repository with neutral paths (the process changes into it for the run). This project's real
conventions file is never read. Every writing --dispatch patches pr_merged.create_branch with a
stand-in that accepts any arguments, so these tests do not depend on that function's signature.

Run: py -3 -B .claude/scripts/tests/test_pr_merged_dispatch.py
"""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pr_merged  # noqa: E402


# ---------------------------------------------------------------------------
# Structural guard: no test here may reach a real GitHub mutation (same guard as
# test_pr_merged.py).
# ---------------------------------------------------------------------------
_REAL_SUBPROCESS_RUN = subprocess.run
_FORBIDDEN_GH_MUTATIONS = (
    ("gh", "issue", "close"),
    ("gh", "issue", "develop"),
    ("gh", "pr", "merge"),
    ("gh", "issue", "comment"),
    ("gh", "pr", "create"),
    ("git", "push"),
    ("gh", "api", "user"),
)
_HAD_GH_AUTHENTICATED = hasattr(pr_merged, "gh_authenticated")
_REAL_GH_AUTHENTICATED = getattr(pr_merged, "gh_authenticated", None)


def _guarded_subprocess_run(cmd, *args, **kwargs):
    if isinstance(cmd, (list, tuple)):
        head = tuple(str(c) for c in cmd[:3])
        for forbidden in _FORBIDDEN_GH_MUTATIONS:
            if head[:len(forbidden)] == forbidden:
                raise RuntimeError(
                    "test suite attempted a real %r -- patch pr_merged._run in the failing "
                    "test instead of letting it reach subprocess.run" % (cmd,))
    return _REAL_SUBPROCESS_RUN(cmd, *args, **kwargs)


def setUpModule():
    subprocess.run = _guarded_subprocess_run
    pr_merged.gh_authenticated = lambda: True


def tearDownModule():
    subprocess.run = _REAL_SUBPROCESS_RUN
    if _HAD_GH_AUTHENTICATED:
        pr_merged.gh_authenticated = _REAL_GH_AUTHENTICATED
    elif hasattr(pr_merged, "gh_authenticated"):
        delattr(pr_merged, "gh_authenticated")


def _fn(name):
    """Look up a not-yet-built symbol on pr_merged without a collection-time crash."""
    return getattr(pr_merged, name, None)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
SLUG = "acme-contract"

#: Two sub-tasks; t2 waits on t1.
CONTRACT_CHAIN = """
## Implementation Handoff

### 1. Backend (`acme-dev`)

**Depends on:** none

**Files to touch:**
- docs/a.md

### 2. Frontend (`acme-dev`)

**Depends on:** 1

**Files to touch:**
- docs/b.md
"""

#: One mergeable sub-task.
CONTRACT_SINGLE = """
## Implementation Handoff

### 1. Backend (`acme-dev`)

**Depends on:** none

**Files to touch:**
- docs/a.md
"""

_T1_DONE = {"t1-backend": {"status": "completed", "verified": "github", "pull_request": "u1"}}

#: Conventions with one emulator gating one step; the step selects files under svc/.
CONVENTIONS = {
    "contractLanding": {
        "emulators": [{"id": "acme-store", "host": "127.0.0.1", "port": 19999,
                       "gates_steps": ["acme-suite"], "start_hint": "start the store",
                       "signatures": []}],
        "verification": {"steps": [{"id": "acme-suite", "suite": "acme-suite",
                                    "when_paths": ["svc/**"], "command": ["true"],
                                    "results": {"format": "exit-code"}}]},
    }
}


def _contract_with(blocks):
    """A contract of independent sub-tasks. blocks: list of (title, pre_line, files)."""
    parts = ["\n## Implementation Handoff\n"]
    for ordinal, (title, pre_line, files) in enumerate(blocks, start=1):
        parts.append("\n### %d. %s (`acme-dev`)\n\n**Depends on:** none\n\n" % (ordinal, title))
        if pre_line:
            parts.append(pre_line + "\n\n")
        parts.append("**Files to touch:**\n" + "".join("- %s\n" % f for f in files))
    return "".join(parts)


class _Repo:
    """A temporary repository the process changes into for the length of a test."""

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._old_cwd = os.getcwd()
        os.chdir(self.root)
        (self.root / ".claude" / "concepts").mkdir(parents=True)
        return self

    def __exit__(self, *exc):
        os.chdir(self._old_cwd)
        self._tmp.cleanup()
        return False

    def contract(self, text, slug=SLUG):
        path = self.root / ".claude" / "concepts" / (slug + ".md")
        path.write_text(text, encoding="utf-8")
        return path

    def brief(self, name, folder=".claude/work-items", **fields):
        path = self.root / folder / (name + ".md")
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["%s: %s" % (k, v) for k, v in fields.items()]
        path.write_text("---\n" + "\n".join(lines) + "\n---\n\nbody\n", encoding="utf-8")
        return path

    def child_brief(self, name, task_id, base, parent_issue="100", issue="101", slug=SLUG):
        return self.brief(name, id=issue, contract=slug, parent_issue=parent_issue, base=base,
                          branch="task/%s/%s" % (slug, task_id))

    def conventions(self, data=None):
        path = self.root / ".claude" / "work-item-conventions.json"
        path.write_text(json.dumps(CONVENTIONS if data is None else data), encoding="utf-8")
        return path

    def state(self, entries, slug=SLUG):
        path = self.root / ".claude" / "orchestrator" / "state" / slug / "state.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.dump({"contract": slug, "started_at": "2026-10-08T00:00:00+00:00",
                                   "sub_tasks": entries}, sort_keys=False), encoding="utf-8")
        return path

    def snapshot(self):
        """Every file under the repository, as {relative path: bytes}."""
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in sorted(self.root.rglob("*")) if p.is_file()}


def _entry(status="pending", base="master", issue=None, brief=None, branch=None, pr=None):
    return {"status": status, "branch": branch, "pull_request": pr, "issue": issue,
            "base": base, "brief": brief}


class _Result:
    def __init__(self, exit_code, out, err):
        self.exit_code = exit_code
        self.out = out
        self.err = err
        self.payload = None
        text = out.strip()
        if text.startswith("{"):
            try:
                self.payload = json.loads(text)
            except ValueError:
                self.payload = None
        self.branch = None       # the create_branch stand-in
        self.probe = None        # the _probe_emulator stand-in
        self.gh_calls = []       # every command that reached the _run stand-in
        self.write_state = None  # present when the test patched it
        self.mark_dispatched = None

    def gh_pr_views(self):
        return [c for c in self.gh_calls if list(c[:3]) == ["gh", "pr", "view"]]


def _branch_and_base(call):
    """The branch and base a create_branch call received, by keyword or by position."""
    args, kwargs = call
    branch = kwargs.get("branch", args[0] if len(args) > 0 else None)
    base = kwargs.get("base", args[1] if len(args) > 1 else None)
    return branch, base


def _drive(repo, contract_path, flags, records=None, emulator_up=False, pr_state="MERGED",
           patch_state_writes=False, extra_patches=()):
    """Run pr_merged.main() inside the temporary repository and collect what happened.

    pr_state is the state `gh pr view` answers for a precondition ("MERGED", "OPEN"), or None
    for a failing answer. Nothing real is reached: _run is a stand-in, create_branch is a
    stand-in accepting any arguments, and _probe_emulator is patched (created when absent).
    """
    gh_calls = []

    def fake_run(cmd):
        gh_calls.append(list(cmd))
        if list(cmd[:3]) == ["gh", "pr", "view"]:
            if pr_state is None:
                return 1, ""
            return 0, json.dumps({"state": pr_state})
        return 1, ""

    branch_stand_in = mock.MagicMock(return_value=(True, "stub"))
    probe_stand_in = mock.MagicMock(return_value=emulator_up)
    argv = ["pr_merged.py", "--contract", str(contract_path)] + list(flags)
    out, err = io.StringIO(), io.StringIO()
    write_state_mock = mock.MagicMock(return_value=None)
    mark_mock = mock.MagicMock(side_effect=lambda state, *a, **k: state)
    env = {k: v for k, v in os.environ.items() if k != "GH_REPO"}
    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(sys, "argv", argv))
        stack.enter_context(mock.patch.dict(os.environ, env, clear=True))
        stack.enter_context(mock.patch.object(pr_merged, "default_branch", return_value="master"))
        stack.enter_context(mock.patch.object(pr_merged, "load_records",
                                              return_value=dict(records or {})))
        stack.enter_context(mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)))
        stack.enter_context(mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)))
        stack.enter_context(mock.patch.object(pr_merged, "_run", fake_run))
        stack.enter_context(mock.patch.object(pr_merged, "create_branch", branch_stand_in))
        stack.enter_context(mock.patch.object(pr_merged, "_probe_emulator", probe_stand_in,
                                              create=True))
        if patch_state_writes:
            stack.enter_context(mock.patch.object(pr_merged, "write_state", write_state_mock))
            stack.enter_context(mock.patch.object(pr_merged, "mark_dispatched", mark_mock))
        for patcher in extra_patches:
            stack.enter_context(patcher)
        stack.enter_context(contextlib.redirect_stdout(out))
        stack.enter_context(contextlib.redirect_stderr(err))
        try:
            exit_code = pr_merged.main()
        except SystemExit as exc:  # argparse refusing a flag the script does not know yet
            exit_code = exc.code
    result = _Result(exit_code, out.getvalue(), err.getvalue())
    result.branch = branch_stand_in
    result.probe = probe_stand_in
    result.gh_calls = gh_calls
    if patch_state_writes:
        result.write_state = write_state_mock
        result.mark_dispatched = mark_mock
    return result


def _items(packet):
    """Preconditions as comparable (kind, ref, source) triples."""
    return [(i.get("kind"), i.get("ref"), i.get("source")) for i in packet.get("preconditions", [])]


# ---------------------------------------------------------------------------
# D-1 through --dispatch
# ---------------------------------------------------------------------------
class DispatchBaseResolutionTests(unittest.TestCase):
    """D-1 rules 1 to 5, read through a writing --dispatch."""

    def test_a_fresh_state_takes_the_parent_branch_the_briefs_declare(self):
        # Rule 3. new_state fills "master" into every entry; that default is never a declaration.
        with _Repo() as repo:
            contract = repo.contract(CONTRACT_CHAIN)
            repo.child_brief("b1", "t1-backend", "feature/p")
            repo.child_brief("b2", "t2-frontend", "feature/p", issue="102")
            res = _drive(repo, contract, ["--dispatch", "t1-backend", "--json"])
        self.assertEqual(res.exit_code, 0, "fixture sanity: a released sub-task dispatches")
        self.assertEqual(res.branch.call_count, 1, "fixture sanity: the branch is cut once")
        _, base = _branch_and_base(res.branch.call_args)
        self.assertEqual(base, "feature/p",
                         msg="briefs that declare parent branch feature/p must decide the base of "
                             "a sub-task whose state entry only carries new_state's default")
        self.assertEqual(res.payload.get("base"), "feature/p",
                         msg="the packet must carry the base the branch was cut from")
        self.assertEqual(res.payload.get("base_source"), "declared-topology",
                         msg="a base taken from the briefs' declared topology must say so")

    def test_a_sub_task_never_recorded_still_takes_the_declared_parent_branch(self):
        # The stored state has t1 only; t2 reaches --dispatch through backfill (base None).
        with _Repo() as repo:
            contract = repo.contract(CONTRACT_CHAIN)
            repo.child_brief("b1", "t1-backend", "feature/p")
            repo.child_brief("b2", "t2-frontend", "feature/p", issue="102")
            repo.state({"t1-backend": _entry("completed", base="feature/p", issue=101,
                                             branch="task/%s/t1-backend" % SLUG, pr="u1")})
            res = _drive(repo, contract, ["--dispatch", "t2-frontend", "--json"], records=_T1_DONE)
        self.assertEqual(
            res.exit_code, 0,
            msg="briefs that declare the parent branch fill in the base of a sub-task with no "
                "entry, instead of the sibling check refusing it (D-1 rule 3 before rule 4)")
        self.assertEqual(res.branch.call_count, 1)
        _, base = _branch_and_base(res.branch.call_args)
        self.assertEqual(base, "feature/p",
                         msg="a never-recorded sub-task is cut from the declared parent branch")
        self.assertEqual(res.payload.get("base_source"), "declared-topology")

    def test_a_recorded_brief_makes_its_entrys_base_win_over_the_declared_topology(self):
        # Rule 1 before rule 3. The recorded brief sits outside the work-items folder, so the
        # briefs the topology reads declare feature/p only.
        with _Repo() as repo:
            contract = repo.contract(CONTRACT_SINGLE)
            repo.child_brief("b1", "t9-other", "feature/p")
            recorded = repo.brief("t1-own", folder=".claude/elsewhere", id="7", base="feature/q")
            repo.state({"t1-backend": _entry(base="feature/q", issue=7, brief=str(recorded))})
            res = _drive(repo, contract, ["--dispatch", "t1-backend", "--json"])
        self.assertEqual(res.exit_code, 0, "fixture sanity: the recorded entry agrees with its brief")
        _, base = _branch_and_base(res.branch.call_args)
        self.assertEqual(base, "feature/q",
                         msg="an entry with a recorded brief is cut from its own base")
        self.assertEqual(res.payload.get("base_source"), "state",
                         msg="a base read from a state entry's recorded brief says so")

    def test_ambiguous_briefs_refuse_the_dispatch_as_base_not_declared(self):
        # Rule 2. Two different parent branches declared: nothing is guessed.
        with _Repo() as repo:
            contract = repo.contract(CONTRACT_SINGLE)
            repo.child_brief("b1", "t1-backend", "feature/p")
            repo.child_brief("b2", "t1-backend", "feature/q", issue="102")
            res = _drive(repo, contract, ["--dispatch", "t1-backend", "--json"])
        self.assertEqual(res.exit_code, 7,
                         msg="briefs that declare two different parent branches must refuse the "
                             "dispatch with exit 7, not cut from one of them or from master")
        self.assertIsNotNone(res.payload, "fixture sanity: the refusal is printed as JSON")
        self.assertEqual(res.payload.get("error"), "base-not-declared")
        next_command = res.payload.get("next_command")
        self.assertIsInstance(next_command, dict,
                              msg="the refusal must carry a next_command for the operator")
        self.assertIsInstance(next_command.get("commands"), list)
        self.assertTrue(next_command.get("reason"), "a next_command names its reason")
        self.assertEqual(res.branch.call_count, 0, "a refused dispatch cuts nothing")

    def test_two_parent_issues_on_one_base_also_refuse_ahead_of_the_declared_parent(self):
        # Rule 2 before rule 3: a parent branch IS declared (feature/p) but two parent issues
        # make the reading ambiguous, so the declared parent must not be taken.
        with _Repo() as repo:
            contract = repo.contract(CONTRACT_SINGLE)
            repo.child_brief("b1", "t1-backend", "feature/p", parent_issue="100")
            repo.child_brief("b2", "t1-backend", "feature/p", parent_issue="200", issue="102")
            res = _drive(repo, contract, ["--dispatch", "t1-backend", "--json"])
        self.assertEqual(res.exit_code, 7,
                         msg="an ambiguous reading beats the declared parent branch (rule 2 "
                             "before rule 3)")
        self.assertEqual((res.payload or {}).get("error"), "base-not-declared")
        self.assertEqual(res.branch.call_count, 0)

    def test_no_parent_declared_and_no_sibling_conflict_falls_back_to_the_default(self):
        # Rule 5.
        with _Repo() as repo:
            contract = repo.contract(CONTRACT_SINGLE)
            res = _drive(repo, contract, ["--dispatch", "t1-backend", "--json"])
        self.assertEqual(res.exit_code, 0)
        _, base = _branch_and_base(res.branch.call_args)
        self.assertEqual(base, "master")
        self.assertEqual(res.payload.get("base_source"), "default",
                         msg="a base that is only the default branch must be labelled so")

    def test_a_sibling_with_a_non_default_base_and_no_declaring_briefs_still_refuses(self):
        # Rule 4 before rule 5: the existing base-not-declared behaviour, unchanged.
        with _Repo() as repo:
            contract = repo.contract(CONTRACT_CHAIN)
            repo.brief("b0", id="100", contract=SLUG, parent_issue="none")  # declares no base
            repo.state({"t1-backend": _entry("completed", base="feature/x", issue=101,
                                             branch="task/%s/t1-backend" % SLUG, pr="u1"),
                        "t2-frontend": _entry(base=None)})
            res = _drive(repo, contract, ["--dispatch", "t2-frontend", "--json"], records=_T1_DONE)
        self.assertEqual(res.exit_code, 7)
        self.assertEqual((res.payload or {}).get("error"), "base-not-declared")
        self.assertIn("feature/x", (res.payload or {}).get("detail", ""),
                      msg="the sibling refusal still names the other base on record")
        self.assertEqual(res.branch.call_count, 0)


@unittest.skipUnless(hasattr(pr_merged, "brief_for_branch"),
                     "contract 460's rehydration is not on this branch")
class DispatchIdentityAmbiguousTests(unittest.TestCase):
    """D-1 rule 0: two briefs for one sub-task's branch beat every base rule."""

    def _two_briefs(self, repo):
        for name, issue in (("b1", "101"), ("b2", "102")):
            repo.brief(name, id=issue, contract=SLUG, parent_issue="100", base="feature/p",
                       branch="task/%s/t1-backend" % SLUG)

    def test_dispatch_refuses_identity_ambiguous_before_rule_one_is_read(self):
        with _Repo() as repo:
            contract = repo.contract(CONTRACT_SINGLE)
            self._two_briefs(repo)
            recorded = repo.brief("t1-own", folder=".claude/elsewhere", id="7", base="feature/q")
            repo.state({"t1-backend": _entry(base="feature/q", issue=7, brief=str(recorded))})
            res = _drive(repo, contract, ["--dispatch", "t1-backend", "--json"])
        self.assertEqual((res.payload or {}).get("error"), "identity-ambiguous",
                         msg="two briefs matching one branch refuse before a recorded brief's "
                             "base is read")
        self.assertEqual(res.branch.call_count, 0)

    def test_status_reports_identity_ambiguous_without_refusing(self):
        with _Repo() as repo:
            contract = repo.contract(CONTRACT_SINGLE)
            self._two_briefs(repo)
            res = _drive(repo, contract, ["--status", "--json"])
        self.assertEqual(res.exit_code, 0)
        entry = {b["id"]: b for b in res.payload["blocks"]}["t1-backend"]
        self.assertEqual(entry.get("base_problem"), "identity-ambiguous")


# ---------------------------------------------------------------------------
# D-1 through --status
# ---------------------------------------------------------------------------
class StatusBaseReportTests(unittest.TestCase):
    """--status reports base, base_source and base_problem per block entry and never refuses."""

    PRE_EXISTING_ENTRY_KEYS = ("ordinal", "id", "heading", "kind", "agent", "agent_role",
                               "files", "depends_on")
    PRE_EXISTING_REPORT_KEYS = ("contract", "sub_tasks", "blocks", "defects", "released",
                                "blocked", "next_move", "next_command", "completion", "state")

    def _blocks(self, res):
        self.assertEqual(res.exit_code, 0, msg="--status reads and never refuses (exit 0)")
        self.assertIsNotNone(res.payload, "fixture sanity: --status --json prints the report")
        return {b["id"]: b for b in res.payload["blocks"]}

    def test_declared_topology_is_reported_on_every_block_entry(self):
        with _Repo() as repo:
            contract = repo.contract(CONTRACT_CHAIN)
            repo.child_brief("b1", "t1-backend", "feature/p")
            repo.child_brief("b2", "t2-frontend", "feature/p", issue="102")
            res = _drive(repo, contract, ["--status", "--json"])
        blocks = self._blocks(res)
        for tid in ("t1-backend", "t2-frontend"):
            self.assertEqual(blocks[tid].get("base"), "feature/p",
                             msg="%s: the base the sub-task would be cut from" % tid)
            self.assertEqual(blocks[tid].get("base_source"), "declared-topology")
            self.assertIsNone(blocks[tid].get("base_problem"),
                              msg="no problem to report when the topology is clear")

    def test_a_recorded_brief_reports_the_entrys_base_from_state(self):
        with _Repo() as repo:
            contract = repo.contract(CONTRACT_SINGLE)
            repo.child_brief("b1", "t9-other", "feature/p")
            recorded = repo.brief("t1-own", folder=".claude/elsewhere", id="7", base="feature/q")
            repo.state({"t1-backend": _entry(base="feature/q", issue=7, brief=str(recorded))})
            res = _drive(repo, contract, ["--status", "--json"])
        entry = self._blocks(res)["t1-backend"]
        self.assertEqual(entry.get("base"), "feature/q")
        self.assertEqual(entry.get("base_source"), "state")

    def test_the_default_branch_is_reported_when_nothing_declares_a_parent(self):
        with _Repo() as repo:
            contract = repo.contract(CONTRACT_SINGLE)
            res = _drive(repo, contract, ["--status", "--json"])
        entry = self._blocks(res)["t1-backend"]
        self.assertEqual(entry.get("base"), "master")
        self.assertEqual(entry.get("base_source"), "default")

    def test_ambiguous_briefs_are_reported_as_a_problem_with_exit_zero(self):
        with _Repo() as repo:
            contract = repo.contract(CONTRACT_SINGLE)
            repo.child_brief("b1", "t1-backend", "feature/p")
            repo.child_brief("b2", "t1-backend", "feature/q", issue="102")
            res = _drive(repo, contract, ["--status", "--json"])
        entry = self._blocks(res)["t1-backend"]
        self.assertEqual(entry.get("base_problem"), "base-not-declared",
                         msg="--status names the ambiguity instead of refusing for it")

    def test_every_pre_existing_key_is_still_present(self):
        with _Repo() as repo:
            contract = repo.contract(CONTRACT_CHAIN)
            repo.child_brief("b1", "t1-backend", "feature/p")
            res = _drive(repo, contract, ["--status", "--json"])
        blocks = self._blocks(res)
        for key in self.PRE_EXISTING_REPORT_KEYS:
            self.assertIn(key, res.payload, msg="report key %r must survive" % key)
        for key in self.PRE_EXISTING_ENTRY_KEYS:
            self.assertIn(key, blocks["t1-backend"], msg="block entry key %r must survive" % key)
        # Positive control: the new keys are additions, not replacements, and they exist.
        self.assertIn("base_source", blocks["t1-backend"],
                      msg="the new keys must be there beside the old ones")


# ---------------------------------------------------------------------------
# Problem 2: the state entry written by a --pr run
# ---------------------------------------------------------------------------
class PrRunStateEntryTests(unittest.TestCase):
    def test_a_recorded_merge_writes_status_branch_pull_request_and_base(self):
        head = "task/%s/t1-backend" % SLUG
        url = "https://example.invalid/acme/repo/pull/173"
        pr = {"number": 173, "state": "MERGED", "mergedAt": "2026-10-08T00:00:00Z",
              "mergeCommit": {"oid": "cafef00d"}, "headRefName": head,
              "baseRefName": "feature/p", "url": url, "commits": [{"oid": "cafef00d"}],
              "statusCheckRollup": None}
        with _Repo() as repo:
            contract = repo.contract(CONTRACT_CHAIN)
            state_path = repo.state({
                "t1-backend": _entry("awaiting-merge", base="feature/p"),
                "t2-frontend": _entry(base="feature/p")})
            res = _drive(
                repo, contract, ["--pr", "173", "--json"],
                extra_patches=(
                    mock.patch.object(pr_merged, "gh_pr", side_effect=lambda n: pr),
                    mock.patch.object(pr_merged, "git_combined_diff", return_value=([], 1)),
                    mock.patch.object(pr_merged, "write_record", return_value=None)))
            stored = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        self.assertEqual(res.exit_code, 0, "fixture sanity: the merge is recorded")
        self.assertEqual([c["sub_task"] for c in res.payload["closed"]], ["t1-backend"],
                         msg="fixture sanity: the pull request closed t1-backend")
        entry = stored["sub_tasks"]["t1-backend"]
        self.assertEqual(entry.get("status"), "completed")
        self.assertEqual(entry.get("branch"), head,
                         msg="the state entry must carry the merged pull request's head branch")
        self.assertEqual(entry.get("pull_request"), url,
                         msg="the state entry must carry the merged pull request's link")
        self.assertEqual(entry.get("base"), "feature/p",
                         msg="the state entry must carry the base the pull request merged into")
        self.assertIsNone(stored["sub_tasks"]["t2-frontend"].get("pull_request"),
                          msg="positive control: a sub-task the pull request does not map to "
                              "is left alone")


# ---------------------------------------------------------------------------
# Problem 5: preconditions on the --dispatch packet
# ---------------------------------------------------------------------------
class DispatchPacketPreconditionsTests(unittest.TestCase):
    def _dispatch(self, blocks, **kwargs):
        with _Repo() as repo:
            repo.conventions()
            contract = repo.contract(_contract_with(blocks))
            return _drive(repo, contract, ["--dispatch", "t1-alpha", "--json"], **kwargs)

    def test_a_label_at_column_zero_declares_two_items(self):
        res = self._dispatch([("Alpha", "**Preconditions:** pull-request owner/repo#5, emulator azurite",
                               ["docs/x.md"])])
        self.assertEqual(res.exit_code, 0)
        self.assertIn("preconditions", res.payload,
                      msg="the dispatch packet must carry its preconditions")
        self.assertEqual(_items(res.payload),
                         [("pull-request", "owner/repo#5", "declared"),
                          ("emulator", "azurite", "declared")],
                         msg="the line's two comma-separated items, in the order written")

    def test_the_same_text_indented_or_mid_line_in_a_task_fence_declares_nothing(self):
        fenced = ("**Pre-written TASK block:**\n```\nTASK: do it\n"
                  "  **Preconditions:** emulator azurite\n"
                  "Notes **Preconditions:** emulator azurite\n```")
        res = self._dispatch([("Alpha", fenced, ["docs/x.md"])])
        # The fence sits before the Files label in this fixture, which is harmless to the parser.
        self.assertEqual(res.exit_code, 0)
        self.assertIn("preconditions", res.payload)
        self.assertEqual(res.payload["preconditions"], [],
                         msg="only a bold label that starts a line is read; a mention inside a "
                             "TASK fence declares nothing")

    def test_files_matching_a_fixture_step_derive_the_emulator_item(self):
        res = self._dispatch([("Alpha", "", ["svc/client.py"])], emulator_up=True)
        self.assertEqual(res.exit_code, 0)
        self.assertEqual(_items(res.payload), [("emulator", "acme-store", "derived")],
                         msg="a block whose files match a step that an emulator gates inherits "
                             "that emulator as a derived item")

    def test_no_line_and_no_match_gives_an_empty_list(self):
        res = self._dispatch([("Alpha", "", ["docs/x.md"])])
        self.assertEqual(res.exit_code, 0)
        self.assertIn("preconditions", res.payload)
        self.assertEqual(res.payload["preconditions"], [])

    def test_an_emulator_that_answers_is_met_and_one_that_does_not_is_unmet(self):
        for up, expected in ((True, "met"), (False, "unmet")):
            res = self._dispatch([("Alpha", "", ["svc/client.py"])], emulator_up=up)
            items = res.payload.get("preconditions", [])
            self.assertEqual([i.get("state") for i in items], [expected],
                             msg="probe answering %s must read %s" % (up, expected))

    def test_an_emulator_is_probed_once_per_id_even_when_declared_and_derived(self):
        res = self._dispatch(
            [("Alpha", "**Preconditions:** emulator acme-store", ["svc/client.py"])])
        self.assertEqual(res.exit_code, 0)
        self.assertEqual(res.probe.call_count, 1,
                         msg="one probe per emulator id per run, whatever number of items name it")

    def test_no_emulator_item_means_no_probe(self):
        res = self._dispatch(
            [("Alpha", "**Preconditions:** pull-request owner/repo#5, a human sign-off",
              ["docs/x.md"])])
        self.assertEqual(res.exit_code, 0)
        self.assertIn("preconditions", res.payload, "fixture sanity: items were read")
        self.assertFalse(res.probe.called, "no emulator item, so no port is opened")

    def test_a_merged_pull_request_is_met_an_open_one_unmet_a_failed_read_unknown(self):
        for pr_state, expected in (("MERGED", "met"), ("OPEN", "unmet"), (None, "unknown")):
            res = self._dispatch(
                [("Alpha", "**Preconditions:** pull-request owner/repo#5", ["docs/x.md"])],
                pr_state=pr_state)
            self.assertEqual([i.get("state") for i in res.payload.get("preconditions", [])],
                             [expected], msg="gh pr view answering %r must read %s" % (pr_state, expected))

    def test_any_other_text_is_unknown(self):
        res = self._dispatch([("Alpha", "**Preconditions:** the vendor key is provisioned",
                               ["docs/x.md"])])
        items = res.payload.get("preconditions", [])
        self.assertEqual([(i.get("kind"), i.get("state")) for i in items], [("other", "unknown")])

    def test_status_packets_carry_no_preconditions_and_probe_nothing(self):
        blocks = [("Alpha", "**Preconditions:** pull-request owner/repo#5", ["svc/client.py"])]
        with _Repo() as repo:
            repo.conventions()
            contract = repo.contract(_contract_with(blocks))
            res = _drive(repo, contract, ["--status", "--json"])
        self.assertEqual(res.exit_code, 0)
        packets = res.payload.get("dispatch", [])
        self.assertTrue(packets, "fixture sanity: --status lists the released sub-task's packet")
        for packet in packets:
            self.assertNotIn("preconditions", packet,
                             msg="--status never reads a precondition, so its packets omit the key")
        self.assertFalse(res.probe.called, "--status opens no port")
        self.assertEqual(res.gh_pr_views(), [], "--status asks gh for no precondition")


# ---------------------------------------------------------------------------
# Problem 5: --preconditions, the read-only reading /advance decides on
# ---------------------------------------------------------------------------
HOLD_REASON = ("every released sub-task waits on an unmet precondition; "
               "dispatch nothing until one is met")
READ_REASON = "ranked reading; /advance dispatches a ready sub-task with --dispatch"


class PreconditionsCommandTests(unittest.TestCase):
    def _read(self, repo, blocks, **kwargs):
        repo.conventions()
        contract = repo.contract(_contract_with(blocks))
        return contract, _drive(repo, contract, ["--preconditions", "--json"], **kwargs)

    def test_a_held_and_a_ready_sub_task_are_ranked_in_release_order(self):
        with _Repo() as repo:
            _, res = self._read(repo, [("Alpha", "", ["svc/client.py"]), ("Beta", "", ["docs/b.md"])])
        self.assertEqual(res.exit_code, 0)
        self.assertIsNotNone(res.payload, "fixture sanity: --preconditions --json prints JSON")
        self.assertEqual(res.payload.get("outcome"), "preconditions-read")
        self.assertEqual(res.payload.get("action"), "dispatch")
        self.assertEqual([(s.get("id"), s.get("rank")) for s in res.payload.get("sub_tasks", [])],
                         [("t1-alpha", "held"), ("t2-beta", "ready")],
                         msg="an unmet emulator holds its sub-task; a sub-task with no item is ready")
        self.assertEqual(res.payload["sub_tasks"][0]["preconditions"][0]["state"], "unmet")
        self.assertEqual(res.payload.get("next_command"), {"commands": [], "reason": READ_REASON})

    def test_an_unknown_item_with_no_unmet_one_ranks_unknown(self):
        with _Repo() as repo:
            _, res = self._read(repo, [
                ("Alpha", "**Preconditions:** the vendor key is provisioned", ["docs/a.md"]),
                ("Beta", "", ["docs/b.md"])])
        self.assertEqual([(s.get("id"), s.get("rank")) for s in (res.payload or {}).get("sub_tasks", [])],
                         [("t1-alpha", "unknown"), ("t2-beta", "ready")])

    def test_every_sub_task_held_says_to_dispatch_nothing(self):
        with _Repo() as repo:
            _, res = self._read(repo, [("Alpha", "", ["svc/a.py"]), ("Beta", "", ["svc/b.py"])])
        self.assertEqual(res.exit_code, 0)
        self.assertEqual([s.get("rank") for s in (res.payload or {}).get("sub_tasks", [])],
                         ["held", "held"])
        self.assertEqual((res.payload or {}).get("next_command"),
                         {"commands": [], "reason": HOLD_REASON})
        self.assertEqual(res.probe.call_count, 1,
                         msg="both sub-tasks name the same emulator, which is probed once per run")

    def test_it_cuts_nothing_and_writes_nothing(self):
        with _Repo() as repo:
            contract = repo.contract(_contract_with([("Alpha", "", ["svc/a.py"]),
                                                     ("Beta", "", ["docs/b.md"])]))
            repo.conventions()
            res = _drive(repo, contract, ["--preconditions", "--json"], patch_state_writes=True)
        self.assertEqual((res.payload or {}).get("outcome"), "preconditions-read",
                         "fixture sanity: the reading happened")
        self.assertFalse(res.branch.called, "no branch is cut")
        self.assertFalse(res.mark_dispatched.called, "no sub-task is marked dispatched")
        self.assertFalse(res.write_state.called, "no state is written")

    def test_the_state_file_and_the_repository_are_byte_identical_afterwards(self):
        with _Repo() as repo:
            contract = repo.contract(_contract_with([("Alpha", "", ["svc/a.py"]),
                                                     ("Beta", "", ["docs/b.md"])]))
            repo.conventions()
            repo.state({"t1-alpha": _entry(), "t2-beta": _entry()})
            before = repo.snapshot()
            res = _drive(repo, contract, ["--preconditions", "--json"])
            after = repo.snapshot()
        self.assertEqual((res.payload or {}).get("outcome"), "preconditions-read",
                         "fixture sanity: the reading happened")
        self.assertEqual(after, before,
                         msg="the reading must leave every file, the state store included, "
                             "byte for byte as it found it")

    def test_a_move_other_than_dispatch_lists_no_sub_tasks(self):
        blocks = [("Alpha", "", ["docs/a.md"])]
        done = {"t1-alpha": {"status": "completed", "verified": "github", "pull_request": "u1"}}
        with _Repo() as repo:
            _, res = self._read(repo, blocks, records=done)
        self.assertEqual(res.exit_code, 0)
        self.assertEqual((res.payload or {}).get("outcome"), "preconditions-read")
        self.assertEqual((res.payload or {}).get("action"), "complete")
        self.assertEqual((res.payload or {}).get("sub_tasks"), [])

    def test_it_is_refused_beside_any_flag_that_acts(self):
        combos = (
            ("--dispatch", ["--dispatch", "t1-alpha"]),
            ("--pr", ["--pr", "5"]),
            ("--record-subtask", ["--record-subtask", "t1-alpha"]),
            ("--record-delivery", ["--record-delivery"]),
            ("--resume", ["--resume"]),
            ("--owner-resolved", ["--owner-resolved", "t1-x.md"]),
            ("--skipped", ["--skipped", "full-suite rerun"]),
        )
        for flag, extra in combos:
            with self.subTest(flag=flag), _Repo() as repo:
                repo.conventions()
                contract = repo.contract(_contract_with([("Alpha", "", ["docs/a.md"])]))
                res = _drive(repo, contract, ["--preconditions", "--json"] + extra)
                self.assertEqual(res.exit_code, 2, msg="--preconditions with %s is a usage error" % flag)
                # Exit 2 alone proves nothing: argparse also exits 2 on a flag it does not know.
                self.assertIsNotNone(res.payload,
                                     msg="the refusal must be printed as a JSON payload, not "
                                         "left to argparse's own usage error")
                self.assertEqual(res.payload.get("error"), "usage-refused")
                self.assertEqual(res.payload.get("detail"),
                                 "--preconditions cannot be combined with %s" % flag)
                self.assertEqual(res.payload.get("next_command"), {
                    "commands": ["py -3 .claude/scripts/pr_merged.py --contract %s "
                                 "--preconditions --json" % SLUG],
                    "reason": "run --preconditions alone; it reads and writes nothing"})
                self.assertFalse(res.branch.called, "a refused call cuts nothing")

    def test_positive_control_dispatching_the_ready_sub_task_still_cuts_and_matches(self):
        blocks = [("Alpha", "", ["svc/a.py"]),
                  ("Beta", "**Preconditions:** pull-request owner/repo#5", ["docs/b.md"])]
        with _Repo() as repo:
            repo.conventions()
            contract = repo.contract(_contract_with(blocks))
            reading = _drive(repo, contract, ["--preconditions", "--json"], pr_state="MERGED")
            dispatched = _drive(repo, contract, ["--dispatch", "t2-beta", "--json"],
                                pr_state="MERGED")
        # The dispatch half is today's behaviour and holds before and after the change.
        self.assertEqual(dispatched.exit_code, 0)
        self.assertEqual(dispatched.branch.call_count, 1,
                         msg="dispatching the ready sub-task cuts its branch exactly once")
        branch, _ = _branch_and_base(dispatched.branch.call_args)
        self.assertEqual(branch, "task/%s/t2-beta" % SLUG)
        # The reading half is the new behaviour.
        by_id = {s["id"]: s for s in (reading.payload or {}).get("sub_tasks", [])}
        self.assertEqual(by_id.get("t2-beta", {}).get("rank"), "ready",
                         msg="a merged precondition leaves its sub-task ready")
        self.assertEqual(dispatched.payload.get("preconditions"),
                         by_id.get("t2-beta", {}).get("preconditions"),
                         msg="the packet carries the same preconditions the reading showed")


# ---------------------------------------------------------------------------
# D-4: find_linked_brief without a header
# ---------------------------------------------------------------------------
class FindLinkedBriefWithoutHeaderTests(unittest.TestCase):
    TEXT = "# a contract with no Work Item Brief header\n"

    def _folder(self, repo):
        return repo.root / ".claude" / "work-items"

    def test_a_parent_brief_beside_three_sub_task_briefs_is_the_one_returned(self):
        with _Repo() as repo:
            repo.brief("parent", id="100", contract=SLUG, branch="feature/p", parent_issue="none")
            for n in (1, 2, 3):
                repo.child_brief("child%d" % n, "t%d-x" % n, "feature/p", issue=str(100 + n))
            found = pr_merged.find_linked_brief(self.TEXT, SLUG, self._folder(repo))
            name = found.name if found is not None else None
        self.assertEqual(name, "parent.md",
                         msg="without a header the parent brief (its branch is the declared "
                             "parent branch and its id the parent issue) is the linked brief")

    def test_a_single_brief_naming_the_contract_is_returned(self):
        with _Repo() as repo:
            repo.brief("only", id="100", contract=SLUG, branch="feature/p")
            found = pr_merged.find_linked_brief(self.TEXT, SLUG, self._folder(repo))
            name = found.name if found is not None else None
        self.assertEqual(name, "only.md")

    def test_positive_control_two_parent_shaped_briefs_return_none(self):
        # Neither names a parent issue, no topology is declared, and two are not "the one
        # brief": there is nothing to choose between them.
        with _Repo() as repo:
            repo.brief("one", id="100", contract=SLUG, branch="feature/p", parent_issue="none")
            repo.brief("two", id="200", contract=SLUG, branch="feature/q", parent_issue="none")
            found = pr_merged.find_linked_brief(self.TEXT, SLUG, self._folder(repo))
        self.assertIsNone(found, "two candidates and no way to tell them apart is none")


if __name__ == "__main__":
    unittest.main()
