#!/usr/bin/env python3
"""
test_verify_parent_link.py -- RED suite for the parent-link verifier
(work item #164, contract
.claude/concepts/2026-09-19-flow-parent-subissue-topology.md, sub-task 2).

House style: plain runnable script, NO pytest -- matches
.claude/scripts/tests/test_verify_issue_link.py (the sibling this script is
modelled on) and .claude/scripts/tests/test_script_path_resolution.py.
check(name, cond, detail) accumulator, printed PASS/FAIL summary, non-zero
exit on any failure.

    py -3 .claude/scripts/tests/test_verify_parent_link.py

--------------------------------------------------------------------------
WHAT THIS PINS DOWN
--------------------------------------------------------------------------
Creating a sub-issue with a parent is a REQUEST, not a fact (I-4 of the
contract): `gh issue create --parent <n>` can exit 0 while the link never
took. The only admissible proof is GitHub's own read-back,
`gh issue view <sub> --json parent`, and this suite pins the four-verdict
ORDERED decision procedure that turns that read-back into a verdict:
`unverifiable` -> `no-parent` -> `foreign-parent` -> `linked`, first match
wins. This is the sibling mechanism the registry names at
`.claude/registries/MECHANISMS.md:113` ("Closing-link verification as an
obligation, not an assertion"): a new instance, not a new mechanism.

The vocabulary (verdict names, the gh read-back command) is declared ONCE,
in `.claude/work-item-conventions.json` -> `issueLink.parentLink`, written
by sub-task 3. This suite asserts the subject AGREES with that file rather
than restating it -- the same discipline `test_verify_issue_link.py` case 19
/ 20 apply to the sibling script. `maxRepairAttempts`, unlike the verdict
names, is declared in the OUTER `issueLink` block, not the nested one --
sub-task 3's own comment in the conventions file says so explicitly, and a
positive/negative pair below pins the split so a script that reads the
wrong location is caught either way.

ISOLATION (JOURNAL 2026-08-26 x2 -- a test that fakes $HOME alone still
reads the real repo; a suite that resolves its subject by absolute path can
pass vacuously): every case except the two explicitly named "real corpus"
checks builds its own fixture conventions file under a temp dir and injects
`run_gh`. The subject is resolved via `__file__`.

FIXTURE ISSUE NUMBERS (the hazard this suite must not repeat): the sibling
suite for the merge recorder named a REAL, OPEN issue (#163) with a small
"obviously fake" integer that collided with reality. Every sub-issue /
parent number used below is drawn from the 9,000,000+ range, which this
repository's tracker (currently in the low hundreds) cannot reach, even
though `run_gh` is injected in every case and none of these numbers is ever
sent to a live `gh` process.

DESTRUCTIVE-COMMAND GUARD (the hazard the merge-recorder suite's fixture
almost triggered for real): applied at IMPORT TIME, once, for the whole
module -- not per test. Mirrors `.claude/scripts/tests/test_pr_merged.py`'s
module-level `subprocess.run` guard. `verify_parent_link.py` is documented
as read-only (the one repair, `gh issue edit --parent`, belongs to `/task`,
never to this script), so any test whose fixture fails to intercept the
seam gets a loud `RuntimeError` instead of a real mutation reaching GitHub.

MUTATION PROBE (contract CONSTRAINTS, sub-task 2): "delete the foreign-parent
rule and prove the tool then reports a wrong parent as linked. Run every
probe with python -B; a restored source file still executes the mutant from
its __pycache__." The probe below transiently rewrites the real
`verify_parent_link.py` on disk (neutralising the one `if` guard that
detects a foreign parent), runs a subprocess with `-B` against it, restores
the original bytes and purges any `__pycache__` entry in a `finally` block.
This is a real, if brief, on-disk mutation of a tracked file inside a git
worktree -- safe only when no concurrent process is editing the same file
at the same moment (see memory note "Mutation probes race parallel
editors"). It is gated on the subject existing at all, so during RED it
degrades to the same named import-failure check every other case uses.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

# --------------------------------------------------------------------------
# Destructive-command guard -- installed BEFORE the subject is imported, so
# no fixture in this file can ever race it into existence. Never patch this
# away; intercept run_gh in the failing test instead.
# --------------------------------------------------------------------------
_REAL_SUBPROCESS_RUN = subprocess.run
_FORBIDDEN_GH_MUTATIONS = (
    ("gh", "issue", "edit"),
    ("gh", "issue", "create"),
    ("gh", "issue", "close"),
    ("gh", "issue", "develop"),
)


def _guarded_subprocess_run(cmd, *args, **kwargs):
    if isinstance(cmd, (list, tuple)):
        head = tuple(str(c) for c in cmd[:3])
        for forbidden in _FORBIDDEN_GH_MUTATIONS:
            if head[: len(forbidden)] == forbidden:
                raise RuntimeError(
                    "test suite attempted a real %r -- a fixture failed to intercept "
                    "run_gh before this command reached subprocess.run. Never patch "
                    "this guard away; inject run_gh in the failing test instead." % (cmd,)
                )
    return _REAL_SUBPROCESS_RUN(cmd, *args, **kwargs)


subprocess.run = _guarded_subprocess_run

# --------------------------------------------------------------------------
# Subject resolution -- via __file__, never Path.home(), never absolute.
# --------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
SUBJECT_PATH = SCRIPTS_DIR / "verify_parent_link.py"

IMPORT_ERROR = None
try:
    import verify_parent_link as V  # type: ignore
except Exception as exc:  # noqa: BLE001 -- RED by assertion, not by traceback
    V = None  # type: ignore
    IMPORT_ERROR = "%s: %s" % (type(exc).__name__, exc)

# --------------------------------------------------------------------------
# Harness
# --------------------------------------------------------------------------
_RESULTS = []


def check(name, cond, detail=""):
    _RESULTS.append((bool(cond), name, detail))


def need_subject(name):
    """Record a FAILED CHECK when the subject is missing, never a traceback.

    Before verify_parent_link.py exists, every case fails naming the import
    error -- a named check, not a bare ImportError traceback.
    """
    if V is None:
        check(name, False, "subject not importable -- %s" % IMPORT_ERROR)
        return True
    return False


def tmp():
    return tempfile.TemporaryDirectory()


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
# Fixture issue numbers, deliberately unreachable by this tracker (see the
# module docstring's "FIXTURE ISSUE NUMBERS" note).
SUB_ISSUE = 9_000_164
EXPECTED_PARENT = 9_000_160
FOREIGN_PARENT = 9_000_199

# The nested block's REAL shape, captured verbatim from
# .claude/work-item-conventions.json -> issueLink.parentLink on 2026-09-20.
# It deliberately carries NO maxRepairAttempts key -- that constant lives in
# the OUTER issueLink block, per sub-task 3's own "$comment" in that file.
PARENT_LINK_BLOCK = {
    "createFlag": "--parent",
    "editFlag": "--parent",
    "readCommand": "gh issue view <sub> --json parent",
    "parentListCommand": "gh issue view <parent> --json subIssues",
    "verdicts": ["unverifiable", "no-parent", "foreign-parent", "linked"],
}


def write_conventions(
    root,
    include_issue_link=True,
    include_parent_link=True,
    outer_max_repair=1,
    parent_overrides=None,
):
    """Fixture work-item-conventions.json, isolated under a temp dir.

    ``include_issue_link=False`` omits the outer ``issueLink`` block
    entirely. ``include_parent_link=False`` keeps the outer block but omits
    the nested ``parentLink`` block -- the shape sub-task 3's dependency
    note describes: "a script that reads a key nobody has written yet
    reports conventions-missing".
    """
    payload = {}
    if include_issue_link:
        outer = {"maxRepairAttempts": outer_max_repair}
        if include_parent_link:
            block = dict(PARENT_LINK_BLOCK)
            if parent_overrides:
                block.update(parent_overrides)
            outer["parentLink"] = block
        payload["issueLink"] = outer
    path = root / "work-item-conventions.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def gh_stub_parent(
    reported_parent=EXPECTED_PARENT,
    version_rc=0,
    version_err="",
    issue_rc=0,
    issue_err="could not resolve to an Issue",
    recorder=None,
):
    """An injectable run_gh answering ``gh issue view <sub> --json parent``.

    Response shapes captured verbatim from a real
    ``gh issue view <n> --json parent`` run against this repository on
    2026-09-19/20: a linked sub-issue returns ``{"parent": {"number": N,
    "state": ..., "title": ..., "url": ..., "id": ...}}``; an unlinked one
    returns ``{"parent": null}`` (measured against issue #160 itself).
    """

    def run_gh(args):
        if recorder is not None:
            recorder.append(list(args))
        if args and args[0] == "--version":
            return (version_rc, "gh version 2.96.0\n", version_err)
        if list(args[:2]) == ["issue", "view"]:
            if issue_rc != 0:
                return (issue_rc, "", issue_err)
            if reported_parent is None:
                body = {"parent": None}
            else:
                body = {
                    "parent": {
                        "id": "I_kwDORb7AlM8AAAABSJiPrw",
                        "number": reported_parent,
                        "state": "OPEN",
                        "title": "fixture parent",
                        "url": "https://github.example/fixture-owner/fixture-repo/issues/%d"
                        % reported_parent,
                    }
                }
            return (0, json.dumps(body), "")
        return (1, "", "unexpected argv: %r" % (args,))

    return run_gh


def gh_stub_raw_payload(stdout_text, version_rc=0, version_err="", issue_rc=0, issue_err=""):
    """An injectable run_gh returning the LITERAL ``stdout_text`` for the
    parent read-back -- unlike ``gh_stub_parent``, which only ever emits the
    two well-formed shapes GitHub itself has been measured to return. This
    fixture exists to probe the malformed/wrongly-shaped responses
    CRITICAL-1 and CRITICAL-2 regression cases require: a parent dict with
    no ``number``, a bare-integer parent, empty stdout on a success exit,
    and a top-level payload that is not an object at all.
    """

    def run_gh(args):
        if args and args[0] == "--version":
            return (version_rc, "gh version 2.96.0\n", version_err)
        if list(args[:2]) == ["issue", "view"]:
            if issue_rc != 0:
                return (issue_rc, "", issue_err)
            return (0, stdout_text, "")
        return (1, "", "unexpected argv: %r" % (args,))

    return run_gh


def exp(
    sub_issue=SUB_ISSUE,
    expected_parent=EXPECTED_PARENT,
    reported_parent=EXPECTED_PARENT,
    repair_attempted=False,
    resolver_cause=None,
):
    """A Parent Link Expectation, per the contract's Data Shapes -> Value
    Objects table: ``subIssue``, ``expectedParent``, ``reportedParent |
    null``, ``repairAttempted``, ``resolverCause | null``.
    """
    return {
        "subIssue": sub_issue,
        "expectedParent": expected_parent,
        "reportedParent": reported_parent,
        "repairAttempted": repair_attempted,
        "resolverCause": resolver_cause,
    }


def _disable_foreign_parent_guard(source_text):
    """Return mutated source with the foreign-parent guard neutralised.

    Finds the nearest ``if`` statement guarding the line that names the
    ``"foreign-parent"`` verdict and forces its condition to ``False``, so
    control falls through to whatever rule follows -- which the contract's
    Extension Points section names explicitly as the fall-through case,
    ``linked``. Returns ``None`` if no such shape is found, which the
    caller reports as its own failure rather than silently skipping the
    probe.
    """
    lines = source_text.splitlines(keepends=True)
    target = None
    for i, line in enumerate(lines):
        if "foreign-parent" in line:
            target = i
            break
    if target is None:
        return None
    guard = None
    for j in range(target, -1, -1):
        stripped = lines[j].lstrip()
        if stripped.startswith("if ") and stripped.rstrip().endswith(":"):
            guard = j
            break
    if guard is None:
        return None
    indent = lines[guard][: len(lines[guard]) - len(lines[guard].lstrip())]
    lines[guard] = "%sif False:  # neutralised by test_verify_parent_link.py mutation probe\n" % indent
    return "".join(lines)


# ==========================================================================
# Case group A -- declared vocabulary, closed sets
# ==========================================================================
def case_verdicts_closed_set_exact_order():
    name = "A1 VERDICTS is exactly [unverifiable, no-parent, foreign-parent, linked], in order"
    if need_subject(name):
        return
    check(
        name,
        list(V.VERDICTS) == ["unverifiable", "no-parent", "foreign-parent", "linked"],
        "got %r" % (list(getattr(V, "VERDICTS", [])),),
    )


def case_verdicts_match_real_conventions_file():
    name = "A2 VERDICTS agrees with the REAL work-item-conventions.json issueLink.parentLink.verdicts"
    if need_subject(name):
        return
    real_path = V.work_item_conventions_path()
    payload = json.loads(real_path.read_text(encoding="utf-8"))
    declared = ((payload.get("issueLink") or {}).get("parentLink") or {}).get("verdicts")
    check(
        name,
        list(V.VERDICTS) == list(declared or []),
        "python=%r json=%r" % (list(getattr(V, "VERDICTS", [])), declared),
    )


def case_halting_is_a_declared_set_excluding_linked():
    name = "A3 HALTING is set-like and equals {unverifiable, no-parent, foreign-parent}"
    if need_subject(name):
        return
    check(name, isinstance(V.HALTING, (set, frozenset)), "type=%r" % type(V.HALTING))
    check(
        "A3 HALTING == {unverifiable, no-parent, foreign-parent}",
        set(getattr(V, "HALTING", [])) == {"unverifiable", "no-parent", "foreign-parent"},
        "got %r" % (set(getattr(V, "HALTING", [])),),
    )
    check(
        "A3 'linked' is NOT a member of HALTING -- a caller tells a refusal from a pass by "
        "membership, not string comparison",
        "linked" not in getattr(V, "HALTING", {"linked"}),
    )


def case_unverifiable_is_conventions_missing_on_a_missing_block():
    name = "A4 'conventions-missing' is the literal cause when the parentLink block is absent"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root, include_parent_link=False)
        block, cause = V.read_conventions(conv)
        check(name, cause == "conventions-missing", "got cause=%r block=%r" % (cause, block))


# ==========================================================================
# Case group B -- evaluate(), the pure ordered decision procedure
# ==========================================================================
def case_eval_linked_is_the_fallthrough_pass():
    name = "B1 linked: reportedParent == expectedParent, no resolver failure"
    if need_subject(name):
        return
    r = V.evaluate(exp(reported_parent=EXPECTED_PARENT))
    check(name, r.get("verdict") == "linked", "got %r" % r.get("verdict"))
    check(
        "B1 halt is computed BY membership in HALTING, not an independent flag",
        r.get("halt") == (r.get("verdict") in V.HALTING),
        "halt=%r verdict=%r HALTING=%r" % (r.get("halt"), r.get("verdict"), V.HALTING),
    )
    check("B1 linked does not halt", r.get("halt") is False, "got %r" % r.get("halt"))


def case_eval_no_parent():
    name = "B2 no-parent: reportedParent is null (measured gh shape for an unlinked sub-issue)"
    if need_subject(name):
        return
    r = V.evaluate(exp(reported_parent=None))
    check(name, r.get("verdict") == "no-parent", "got %r" % r.get("verdict"))
    check("B2 no-parent halts", r.get("halt") is True, "got %r" % r.get("halt"))


def case_eval_foreign_parent_negative():
    name = "B3 NEGATIVE: reportedParent names a DIFFERENT issue -- must never read as a pass"
    if need_subject(name):
        return
    r = V.evaluate(exp(reported_parent=FOREIGN_PARENT))
    check(name, r.get("verdict") == "foreign-parent", "got %r" % r.get("verdict"))
    check("B3 foreign-parent halts", r.get("halt") is True, "got %r" % r.get("halt"))
    check(
        "B3 foreign-parent is NOT read as linked",
        r.get("verdict") != "linked",
        "got %r" % r.get("verdict"),
    )


def case_eval_no_parent_and_foreign_parent_are_discriminated():
    name = "B4 DISCRIMINATION: null-parent and wrong-parent report DIFFERENT verdicts"
    if need_subject(name):
        return
    no_parent = V.evaluate(exp(reported_parent=None)).get("verdict")
    foreign = V.evaluate(exp(reported_parent=FOREIGN_PARENT)).get("verdict")
    check(
        name,
        no_parent != foreign and no_parent == "no-parent" and foreign == "foreign-parent",
        "no_parent=%r foreign=%r" % (no_parent, foreign),
    )


def case_eval_unverifiable_outranks_a_would_be_pass():
    name = "B5 ORDERING: resolverCause wins even when reportedParent already matches"
    if need_subject(name):
        return
    r = V.evaluate(exp(reported_parent=EXPECTED_PARENT, resolver_cause="gh-missing"))
    check(name, r.get("verdict") == "unverifiable", "got %r" % r.get("verdict"))
    check("B5 unverifiable halts", r.get("halt") is True, "got %r" % r.get("halt"))


def case_eval_unverifiable_outranks_foreign_parent_too():
    name = "B6 ORDERING: resolverCause wins even when reportedParent would otherwise be foreign"
    if need_subject(name):
        return
    r = V.evaluate(exp(reported_parent=FOREIGN_PARENT, resolver_cause="gh-missing"))
    check(
        name,
        r.get("verdict") == "unverifiable",
        "got %r -- rule 1 must fire before rule 3 examines reportedParent at all" % r.get("verdict"),
    )


def case_eval_verdict_is_always_a_declared_member():
    name = "B7 CLOSURE: every constructed expectation resolves to a declared VERDICTS member"
    if need_subject(name):
        return
    fixtures = [
        exp(reported_parent=EXPECTED_PARENT),
        exp(reported_parent=None),
        exp(reported_parent=FOREIGN_PARENT),
        exp(resolver_cause="gh-missing"),
    ]
    verdicts = [V.evaluate(f).get("verdict") for f in fixtures]
    check(
        name,
        all(v in V.VERDICTS for v in verdicts),
        "verdicts=%r declared=%r" % (verdicts, list(V.VERDICTS)),
    )


# ==========================================================================
# Case group C -- mutation probe on the foreign-parent guard (B3's pairing)
# ==========================================================================
def case_mutation_probe_foreign_parent_guard_is_load_bearing():
    name = "C1 MUTATION PROBE: disabling the foreign-parent guard reports a wrong parent as linked"
    if need_subject(name):
        return
    original = SUBJECT_PATH.read_text(encoding="utf-8")
    mutated = _disable_foreign_parent_guard(original)
    if mutated is None:
        check(
            name,
            False,
            "could not locate a guarded 'foreign-parent' rule to neutralise in %s -- the "
            "probe itself found no shape to mutate" % SUBJECT_PATH,
        )
        return
    pycache = SUBJECT_PATH.parent / "__pycache__"
    fixture = exp(reported_parent=FOREIGN_PARENT)
    mutant_verdict = None
    stdout, stderr, returncode = "", "", None
    try:
        SUBJECT_PATH.write_text(mutated, encoding="utf-8")
        code = (
            "import sys, json\n"
            "sys.path.insert(0, %r)\n" % str(SCRIPTS_DIR)
            + "import verify_parent_link as M\n"
            "print(json.dumps(M.evaluate(json.loads(sys.argv[1]))))\n"
        )
        proc = _REAL_SUBPROCESS_RUN(
            [sys.executable, "-B", "-c", code, json.dumps(fixture)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(SCRIPTS_DIR),
        )
        stdout, stderr, returncode = proc.stdout, proc.stderr, proc.returncode
        if returncode == 0 and stdout.strip():
            try:
                mutant_verdict = json.loads(stdout.strip().splitlines()[-1]).get("verdict")
            except (ValueError, IndexError):
                mutant_verdict = None
    finally:
        SUBJECT_PATH.write_text(original, encoding="utf-8")
        if pycache.exists():
            for p in pycache.glob("verify_parent_link.*"):
                try:
                    p.unlink()
                except OSError:
                    pass

    check(
        name,
        mutant_verdict == "linked",
        "expected the disabled guard to silently pass the SAME fixture as 'linked'; "
        "got verdict=%r rc=%r stdout=%r stderr=%r" % (mutant_verdict, returncode, stdout, stderr),
    )

    # POSITIVE CONTROL pairing (required by the brief): the UNMUTATED subject
    # must still report foreign-parent for the IDENTICAL fixture, proving the
    # probe measured this guard and not some unrelated difference.
    control_name = "C1 CONTROL: the unmutated subject reports foreign-parent for the same fixture"
    unmutated_verdict = V.evaluate(fixture).get("verdict")
    check(
        control_name,
        unmutated_verdict == "foreign-parent",
        "got %r -- if this also fails, case C1 measured nothing" % unmutated_verdict,
    )


# ==========================================================================
# Case group D -- verify(), the impure driver wired to gh
# ==========================================================================
def case_verify_linked():
    name = "D1 verify(): linked end to end through an injected run_gh"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root)
        r = V.verify(
            SUB_ISSUE,
            EXPECTED_PARENT,
            conventions_path=conv,
            run_gh=gh_stub_parent(reported_parent=EXPECTED_PARENT),
        )
        check(name, r.get("verdict") == "linked", "got %r" % r.get("verdict"))
        check("D1 does not halt", r.get("halt") is False, "got %r" % r.get("halt"))


def case_verify_no_parent():
    name = "D2 verify(): no-parent end to end (the measured gh shape for an unlinked sub-issue)"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root)
        r = V.verify(
            SUB_ISSUE,
            EXPECTED_PARENT,
            conventions_path=conv,
            run_gh=gh_stub_parent(reported_parent=None),
        )
        check(name, r.get("verdict") == "no-parent", "got %r" % r.get("verdict"))
        check("D2 halts", r.get("halt") is True, "got %r" % r.get("halt"))


def case_verify_foreign_parent():
    name = "D3 verify(): foreign-parent end to end -- must never be read as a pass"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root)
        r = V.verify(
            SUB_ISSUE,
            EXPECTED_PARENT,
            conventions_path=conv,
            run_gh=gh_stub_parent(reported_parent=FOREIGN_PARENT),
        )
        check(name, r.get("verdict") == "foreign-parent", "got %r" % r.get("verdict"))
        check("D3 halts", r.get("halt") is True, "got %r" % r.get("halt"))


def case_verify_conventions_missing_file_absent():
    name = "D4 verify(): a conventions file that does not exist at all halts unverifiable"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        missing = root / "does-not-exist.json"
        r = V.verify(
            SUB_ISSUE,
            EXPECTED_PARENT,
            conventions_path=missing,
            run_gh=gh_stub_parent(reported_parent=EXPECTED_PARENT),
        )
        check(name, r.get("verdict") == "unverifiable", "got %r" % r.get("verdict"))
        check("D4 cause is the literal 'conventions-missing'", r.get("cause") == "conventions-missing",
              "got %r" % r.get("cause"))
        check("D4 halts", r.get("halt") is True, "got %r" % r.get("halt"))


def case_verify_conventions_missing_no_issue_link_key():
    name = "D5 verify(): a conventions file with no issueLink key at all halts unverifiable"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root, include_issue_link=False)
        r = V.verify(
            SUB_ISSUE,
            EXPECTED_PARENT,
            conventions_path=conv,
            run_gh=gh_stub_parent(reported_parent=EXPECTED_PARENT),
        )
        check(name, r.get("verdict") == "unverifiable", "got %r" % r.get("verdict"))
        check("D5 cause is 'conventions-missing'", r.get("cause") == "conventions-missing",
              "got %r" % r.get("cause"))


def case_verify_conventions_missing_no_parent_link_key():
    name = (
        "D6 verify(): issueLink present but its parentLink key is absent -- "
        "sub-task 3's own dependency note, halts unverifiable, NEVER a quiet pass"
    )
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root, include_parent_link=False)
        r = V.verify(
            SUB_ISSUE,
            EXPECTED_PARENT,
            conventions_path=conv,
            run_gh=gh_stub_parent(reported_parent=EXPECTED_PARENT),
        )
        check(name, r.get("verdict") == "unverifiable", "got %r" % r.get("verdict"))
        check("D6 is not linked", r.get("verdict") != "linked", "got %r" % r.get("verdict"))
        check("D6 cause is 'conventions-missing'", r.get("cause") == "conventions-missing",
              "got %r" % r.get("cause"))


def case_verify_conventions_present_is_a_positive_control():
    name = (
        "D7 POSITIVE CONTROL: a well-formed conventions file does NOT halt -- "
        "an implementation that always reports conventions-missing fails this"
    )
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root)
        r = V.verify(
            SUB_ISSUE,
            EXPECTED_PARENT,
            conventions_path=conv,
            run_gh=gh_stub_parent(reported_parent=EXPECTED_PARENT),
        )
        check(name, r.get("verdict") == "linked", "got %r" % r.get("verdict"))
        check("D7 does not halt", r.get("halt") is False, "got %r" % r.get("halt"))


def case_verify_gh_missing():
    name = "D8 verify(): gh itself is missing -- unverifiable, cause gh-missing"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root)
        r = V.verify(
            SUB_ISSUE,
            EXPECTED_PARENT,
            conventions_path=conv,
            run_gh=gh_stub_parent(version_rc=1, version_err="'gh' is not recognized"),
        )
        check(name, r.get("verdict") == "unverifiable", "got %r" % r.get("verdict"))
        check("D8 cause is gh-missing", r.get("cause") == "gh-missing", "got %r" % r.get("cause"))
        check(
            "D8 carries its own non-empty remediation line",
            bool(r.get("remediation")),
            "got %r" % r.get("remediation"),
        )


def case_verify_gh_unauthenticated():
    name = "D9 verify(): gh is present but not logged in -- unverifiable, cause gh-unauthenticated"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root)
        r = V.verify(
            SUB_ISSUE,
            EXPECTED_PARENT,
            conventions_path=conv,
            run_gh=gh_stub_parent(
                version_rc=1, version_err="You are not logged into any GitHub hosts."
            ),
        )
        check(name, r.get("verdict") == "unverifiable", "got %r" % r.get("verdict"))
        check(
            "D9 cause is gh-unauthenticated", r.get("cause") == "gh-unauthenticated",
            "got %r" % r.get("cause"),
        )


def case_verify_gh_missing_and_gh_unauthenticated_are_discriminated():
    name = "D10 DISCRIMINATION: gh-missing and gh-unauthenticated get DIFFERENT causes"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root)
        missing = V.verify(
            SUB_ISSUE, EXPECTED_PARENT, conventions_path=conv,
            run_gh=gh_stub_parent(version_rc=1, version_err="'gh' is not recognized"),
        ).get("cause")
        unauth = V.verify(
            SUB_ISSUE, EXPECTED_PARENT, conventions_path=conv,
            run_gh=gh_stub_parent(version_rc=1, version_err="not logged into any GitHub hosts"),
        ).get("cause")
        check(
            name,
            missing != unauth and missing == "gh-missing" and unauth == "gh-unauthenticated",
            "missing=%r unauth=%r" % (missing, unauth),
        )


def case_verify_query_failed_on_the_read_back_itself():
    name = "D11 verify(): the read-back call itself fails -- unverifiable, never a fifth verdict"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root)
        r = V.verify(
            SUB_ISSUE,
            EXPECTED_PARENT,
            conventions_path=conv,
            run_gh=gh_stub_parent(issue_rc=1, issue_err="unexpected server error"),
        )
        check(name, r.get("verdict") == "unverifiable", "got %r" % r.get("verdict"))
        check("D11 halts", r.get("halt") is True, "got %r" % r.get("halt"))
        check(
            "D11 verdict stays inside the closed set (no fifth verdict for this failure mode)",
            r.get("verdict") in V.VERDICTS,
            "got %r declared=%r" % (r.get("verdict"), list(V.VERDICTS)),
        )


# ==========================================================================
# Case group D (cont.) -- CRITICAL-1 / CRITICAL-2 regressions (independent
# review, 2026-09-20). An unreadable or wrongly-shaped read-back response
# must NEVER collapse to no-parent (the verdict that triggers /task's one
# automatic re-parent) and must NEVER crash instead of returning a verdict.
# ==========================================================================
def case_verify_parent_dict_with_no_number_is_unverifiable():
    name = (
        "D12 CRITICAL-1: parent is a dict with no 'number' key -- must be "
        "unverifiable/query-failed, NEVER a silent no-parent (would auto-reparent)"
    )
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root)
        r = V.verify(
            SUB_ISSUE,
            EXPECTED_PARENT,
            conventions_path=conv,
            run_gh=gh_stub_raw_payload(json.dumps({"parent": {"state": "OPEN"}})),
        )
        check(name, r.get("verdict") == "unverifiable", "got %r" % r.get("verdict"))
        check(
            "D12 verdict is NOT no-parent",
            r.get("verdict") != "no-parent",
            "got %r -- an unreadable shape must never collapse to the auto-reparent verdict"
            % r.get("verdict"),
        )
        check("D12 cause is query-failed", r.get("cause") == "query-failed", "got %r" % r.get("cause"))


def case_verify_parent_as_bare_integer_is_unverifiable():
    name = (
        "D13 CRITICAL-1: parent is a bare integer, not a dict -- must be "
        "unverifiable/query-failed, NEVER a silent no-parent"
    )
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root)
        r = V.verify(
            SUB_ISSUE,
            EXPECTED_PARENT,
            conventions_path=conv,
            run_gh=gh_stub_raw_payload(json.dumps({"parent": EXPECTED_PARENT})),
        )
        check(name, r.get("verdict") == "unverifiable", "got %r" % r.get("verdict"))
        check(
            "D13 verdict is NOT no-parent",
            r.get("verdict") != "no-parent",
            "got %r" % r.get("verdict"),
        )
        check("D13 cause is query-failed", r.get("cause") == "query-failed", "got %r" % r.get("cause"))


def case_verify_empty_stdout_success_is_unverifiable():
    name = (
        "D14 CRITICAL-1: rc=0 with EMPTY stdout -- must be unverifiable/query-failed, "
        "NEVER a silent no-parent"
    )
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root)
        r = V.verify(
            SUB_ISSUE,
            EXPECTED_PARENT,
            conventions_path=conv,
            run_gh=gh_stub_raw_payload(""),
        )
        check(name, r.get("verdict") == "unverifiable", "got %r" % r.get("verdict"))
        check(
            "D14 verdict is NOT no-parent",
            r.get("verdict") != "no-parent",
            "got %r" % r.get("verdict"),
        )
        check("D14 cause is query-failed", r.get("cause") == "query-failed", "got %r" % r.get("cause"))


def case_verify_top_level_null_is_unverifiable_not_a_crash():
    name = (
        "D15 CRITICAL-2: top-level payload is JSON null -- must return unverifiable, "
        "NEVER raise an uncaught exception"
    )
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root)
        r = V.verify(
            SUB_ISSUE,
            EXPECTED_PARENT,
            conventions_path=conv,
            run_gh=gh_stub_raw_payload("null"),
        )
        check(name, r.get("verdict") == "unverifiable", "got %r" % r.get("verdict"))
        check("D15 cause is query-failed", r.get("cause") == "query-failed", "got %r" % r.get("cause"))


def case_verify_top_level_list_is_unverifiable_not_a_crash():
    name = (
        "D16 CRITICAL-2: top-level payload is a JSON list -- must return unverifiable, "
        "NEVER raise an uncaught exception"
    )
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root)
        r = V.verify(
            SUB_ISSUE,
            EXPECTED_PARENT,
            conventions_path=conv,
            run_gh=gh_stub_raw_payload("[1, 2, 3]"),
        )
        check(name, r.get("verdict") == "unverifiable", "got %r" % r.get("verdict"))
        check("D16 cause is query-failed", r.get("cause") == "query-failed", "got %r" % r.get("cause"))


# ==========================================================================
# Case group E -- maxRepairAttempts lives in the OUTER block, not the nested one
# ==========================================================================
def case_max_repair_attempts_read_from_the_outer_block():
    name = (
        "E1 read_conventions(): maxRepairAttempts comes from the OUTER issueLink block "
        "(sub-task 3's comment names this split explicitly)"
    )
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root, outer_max_repair=5)
        block, cause = V.read_conventions(conv)
        check(name, cause is None, "unexpected cause=%r" % cause)
        check(
            "E1 the read value is 5, from the outer block",
            (block or {}).get("maxRepairAttempts") == 5,
            "got %r" % ((block or {}).get("maxRepairAttempts"),),
        )


def case_max_repair_attempts_ignores_a_wrongly_placed_nested_copy():
    name = (
        "E2 NEGATIVE: a maxRepairAttempts key placed on the NESTED parentLink block is never read "
        "-- restating it there is the exact drift the outer-block comment forbids"
    )
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        # The outer block is dropped down to 1 so 99 cannot be confused for it;
        # the bogus 99 is planted only on the NESTED block, where sub-task 3's
        # own file explicitly says the constant does not live.
        conv = write_conventions(root, outer_max_repair=1, parent_overrides={"maxRepairAttempts": 99})
        block, cause = V.read_conventions(conv)
        check(name, cause is None, "unexpected cause=%r" % cause)
        got = (block or {}).get("maxRepairAttempts")
        check(
            "E2 the read value is NOT 99 -- the nested copy must never win",
            got != 99,
            "got %r -- the script read the wrongly-placed nested value" % got,
        )
        check("E2 the read value IS the outer 1", got == 1, "got %r" % got)


# ==========================================================================
# Case group F -- read-only proof (the script never mutates)
# ==========================================================================
def case_read_only_no_mutating_gh_argv_ever_recorded():
    name = "F1 read-only: verify() records only a read (issue view), never a mutating gh verb"
    if need_subject(name):
        return
    calls = []
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root)
        V.verify(
            SUB_ISSUE,
            EXPECTED_PARENT,
            conventions_path=conv,
            run_gh=gh_stub_parent(reported_parent=FOREIGN_PARENT, recorder=calls),
        )
    mutating = [
        c
        for c in calls
        if len(c) >= 2
        and c[:2] in (["issue", "edit"], ["issue", "create"], ["issue", "close"], ["issue", "develop"])
    ]
    check(name, mutating == [], "mutating gh argv recorded: %r (all calls: %r)" % (mutating, calls))
    check(
        "F1 at least one read (issue view) was recorded",
        any(c[:2] == ["issue", "view"] for c in calls),
        "calls=%r" % (calls,),
    )
    check(
        "F1 the read-back targets the SUB issue, not the parent",
        any(c[:2] == ["issue", "view"] and str(SUB_ISSUE) in [str(x) for x in c] for c in calls),
        "calls=%r" % (calls,),
    )

    # POSITIVE CONTROL: the subject's own seam really does reach
    # subprocess.run -- otherwise "no mutating call was recorded" is true only
    # because nothing runs through the seam at all.
    control_name = "F1 CONTROL: the subject's own run_gh seam reaches subprocess.run"
    probe = []
    saved_run = subprocess.run

    def probe_rec(*a, **kw):
        probe.append((a, kw))
        raise AssertionError("probe")

    try:
        V.subprocess.run = probe_rec  # type: ignore[attr-defined]
        try:
            V.default_run_gh(["--version"])
        except AssertionError:
            pass
    finally:
        subprocess.run = saved_run
        V.subprocess.run = saved_run  # type: ignore[attr-defined]
    check(control_name, probe != [], "the seam never fired -- 'no mutating call' would be vacuous")


# ==========================================================================
# Case group G -- the destructive-command guard installed by this file
# ==========================================================================
def case_destructive_guard_blocks_forbidden_and_allows_the_rest():
    name = "G1 destructive guard: a real 'gh issue edit --parent' raises before reaching a process"
    try:
        _guarded_subprocess_run(["gh", "issue", "edit", "9000164", "--parent", "1"])
        check(name, False, "no exception raised -- the guard did not fire")
    except RuntimeError:
        check(name, True)

    control_name = "G1 CONTROL: a harmless command is NOT blocked by the guard"
    global _REAL_SUBPROCESS_RUN
    saved = _REAL_SUBPROCESS_RUN
    seen = []

    def fake_real(cmd, *a, **kw):
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    _REAL_SUBPROCESS_RUN = fake_real
    try:
        _guarded_subprocess_run(["git", "rev-parse", "HEAD"])
    finally:
        _REAL_SUBPROCESS_RUN = saved
    check(control_name, seen == [["git", "rev-parse", "HEAD"]], "seen=%r" % (seen,))


# ==========================================================================
# Runner
# ==========================================================================
def main():
    cases = [
        case_verdicts_closed_set_exact_order,
        case_verdicts_match_real_conventions_file,
        case_halting_is_a_declared_set_excluding_linked,
        case_unverifiable_is_conventions_missing_on_a_missing_block,
        case_eval_linked_is_the_fallthrough_pass,
        case_eval_no_parent,
        case_eval_foreign_parent_negative,
        case_eval_no_parent_and_foreign_parent_are_discriminated,
        case_eval_unverifiable_outranks_a_would_be_pass,
        case_eval_unverifiable_outranks_foreign_parent_too,
        case_eval_verdict_is_always_a_declared_member,
        case_mutation_probe_foreign_parent_guard_is_load_bearing,
        case_verify_linked,
        case_verify_no_parent,
        case_verify_foreign_parent,
        case_verify_conventions_missing_file_absent,
        case_verify_conventions_missing_no_issue_link_key,
        case_verify_conventions_missing_no_parent_link_key,
        case_verify_conventions_present_is_a_positive_control,
        case_verify_gh_missing,
        case_verify_gh_unauthenticated,
        case_verify_gh_missing_and_gh_unauthenticated_are_discriminated,
        case_verify_query_failed_on_the_read_back_itself,
        case_verify_parent_dict_with_no_number_is_unverifiable,
        case_verify_parent_as_bare_integer_is_unverifiable,
        case_verify_empty_stdout_success_is_unverifiable,
        case_verify_top_level_null_is_unverifiable_not_a_crash,
        case_verify_top_level_list_is_unverifiable_not_a_crash,
        case_max_repair_attempts_read_from_the_outer_block,
        case_max_repair_attempts_ignores_a_wrongly_placed_nested_copy,
        case_read_only_no_mutating_gh_argv_ever_recorded,
        case_destructive_guard_blocks_forbidden_and_allows_the_rest,
    ]
    for c in cases:
        c()

    failed = [r for r in _RESULTS if not r[0]]
    for ok, name, detail in _RESULTS:
        if not ok:
            print("FAIL  %s%s" % (name, ("  -- " + detail) if detail else ""))
    print("")
    print("%d checks, %d passed, %d failed" % (len(_RESULTS), len(_RESULTS) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
