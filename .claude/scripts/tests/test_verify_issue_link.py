#!/usr/bin/env python3
"""
test_verify_issue_link.py -- RED suite for closing-link verification
(work item #39, contract
.claude/concepts/2026-08-27-pr-issue-close-linkage.md).

House style: plain runnable script, NO pytest -- matches
.claude/scripts/tests/test_script_path_resolution.py.
check(name, cond, detail) accumulator, printed PASS/FAIL summary, non-zero
exit on any failure.

    py -3 .claude/scripts/tests/test_verify_issue_link.py

--------------------------------------------------------------------------
WHAT THIS PINS DOWN
--------------------------------------------------------------------------
`/ship` writes "Closes #N" into a PR body and ASSUMES GitHub registered it.
It does not. Measured 2026-08-27: 5 of the last 12 merged PRs carried no
resolved closing link, and issue #6 is still open although PR #30 delivered
it. The only admissible proof is GitHub's own resolved reference, exposed by
`gh pr view --json closingIssuesReferences` (INV-1).

This suite pins the 16-verdict ORDERED decision procedure. Order IS the
enforcement mechanism for INV-3 (never rewrite Refs into Closes) and INV-13,
so a rule moved "for readability" must go RED here.

ISOLATION (JOURNAL 2026-08-26 x2 -- a test that fakes $HOME alone still
reads the real repo; a suite that resolves its subject by absolute path can
pass vacuously): this suite never reads the real work-item-conventions.json,
the real .claude/work-items/, or the real network. Every case builds fixture
files under a temp dir and injects run_gh. The subject is resolved via
__file__.

NO ANY-MATCH ASSERTIONS over a value set. Each of the 16 verdicts and each
of the 5 unverifiable causes has its OWN case with its OWN fixture, because
an array-wide positive control cannot prove a newly-added token is
detectable (JOURNAL 2026-08-26).
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# --------------------------------------------------------------------------
# Subject resolution -- via __file__, never Path.home(), never absolute.
# --------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

IMPORT_ERROR = None
try:
    import verify_issue_link as V  # type: ignore
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

    The contract requires this suite to be RED by assertion. Before
    verify_issue_link.py exists, every case fails naming the import error.
    """
    if V is None:
        check(name, False, "subject not importable -- %s" % IMPORT_ERROR)
        return True
    return False


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
# The brief's repo: string is the OLD name -- the repository was renamed and the
# git remote still says the old one. GitHub answers that name by redirect but
# REPORTS the canonical one. Every fixture below therefore exercises the
# rename: the brief carries the alias, gh reports CANONICAL, and a genuine link
# must still resolve. Verified 2026-08-27 with `gh repo view --json nameWithOwner`.
#
# The two names below are PLACEHOLDERS, not this project's own repository names.
# What the fixtures test is the RELATIONSHIP -- alias differs from canonical,
# same owner, matching is case-folded -- and that relationship is unchanged by
# the substitution. Nothing here compares against a real repository.
REPO = "lneninger/legacy-repo-name"          # alias, as every brief spells it
CANONICAL = "lneninger/canonical-repo-name"  # what gh actually reports
OWNER, REPO_NAME = CANONICAL.split("/")

ISSUE_LINK_BLOCK = {
    "closingKeyword": "Closes",
    "referenceKeyword": "Refs",
    "oneKeywordPerLine": True,
    "sameRepoFormat": "Closes #<n>",
    "crossRepoFormat": "Closes <owner>/<repo>#<n>",
    "resolvesToClosingLink": False,
    "absentIdTokens": ["none", "None", ""],
    "unresolvedIdTokens": ["UNKNOWN", "unknown"],
    "partialField": "partial",
    "linkStateField": "issue_link",
    "linkStates": ["closes", "refs", "none", "unresolved", "manual", "unknown"],
    "maxRepairAttempts": 1,
    # The closed sets live in the conventions file, and case 19 asserts the
    # subject agrees with them. Before this, the JSON arrays were decorative:
    # nothing read them, the script kept its own list, and this suite compared
    # against a THIRD hand-written copy -- three unsynchronized declarations of
    # one closed set, which is the drift INV-8 exists to prevent.
    "verdicts": [
        "unverifiable", "malformed-id", "unresolved-id", "not-applicable",
        "issue-unreachable", "issue-already-closed", "pr-not-open",
        "foreign-closing-ref", "unexpected-closing-ref", "exempt-partial",
        "deferred-close", "linked", "undeclared-target", "refs-without-partial",
        "absent-repairable", "still-absent",
    ],
    "unverifiableCauses": ["gh-missing", "gh-unauthenticated", "query-failed",
                           "pr-not-found", "conventions-missing"],
}

def resolved_link(number, owner=OWNER, repo=REPO_NAME):
    """GitHub's REAL closingIssuesReferences element shape.

    The SHAPE below was CAPTURED VERBATIM from a real
    `gh pr view <n> --json closingIssuesReferences` run on 2026-08-27. Only the
    owner and repository names are placeholders; every key, every nesting level
    and every id format is exactly what GitHub returned. The shape is the part
    that was load-bearing, and it is untouched. The capture returned:

        [{"id": "I_kwDORb7AlM8AAAABOY8AkQ", "number": 35,
          "repository": {"id": "R_kgDORb7AlA", "name": "canonical-repo-name",
                         "owner": {"id": "MDQ6VXNlcjY2MjMyNzk=", "login": "lneninger"}},
          "url": "https://github.com/lneninger/canonical-repo-name/issues/35"}]

    It is NESTED under `repository`. There is no flat owner/repo pair. An
    earlier revision of this suite invented a flat shape and the subject was
    written to match it, so all 122 checks passed while every real PR would
    have failed -- suite and subject wrong in the same direction. A
    hand-written approximation of GitHub's JSON is not a fixture.
    """
    return {
        "id": "I_kwDORb7AlM8AAAABOY8AkQ",
        "number": number,
        "repository": {"id": "R_kgDORb7AlA", "name": repo,
                       "owner": {"id": "MDQ6VXNlcjY2MjMyNzk=", "login": owner}},
        "url": "https://github.com/%s/%s/issues/%d" % (owner, repo, number),
    }


MATCHING = [resolved_link(39)]
FOREIGN = [resolved_link(12)]
# Case 10 negative control: same NUMBER, different OWNER. Must not count.
SAME_NUMBER_OTHER_OWNER = [resolved_link(39, owner="someone-else")]

PLAIN_BODY = "## Summary\n\nsome work.\n"


def write_conventions(root, block="default"):
    """Fixture conventions file. block=None omits the issueLink block."""
    payload = {"issueTitle": {}, "prTitle": {}}
    if block == "default":
        payload["issueLink"] = ISSUE_LINK_BLOCK
    elif block is not None:
        payload["issueLink"] = block
    path = root / "work-item-conventions.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_brief(root, name="brief.md", **fields):
    """Fixture Work Item Brief. Pass a field as None to omit the key."""
    base = {
        "id": "39",
        "title": "PR mechanism must close its issue",
        "type": "IMPROVEMENT",
        "repo": REPO,
        "status": "implementing",
    }
    base.update(fields)
    lines = ["---"]
    for key, value in base.items():
        if value is None:
            continue
        lines.append("%s: %s" % (key, value))
    lines += ["---", "", "# Body", ""]
    path = root / name
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def gh_stub(
    pr_state="OPEN",
    base="master",
    body=PLAIN_BODY,
    closing=None,
    issue_state="OPEN",
    default_branch="master",
    canonical=CANONICAL,
    version_rc=0,
    version_err="",
    pr_rc=0,
    pr_err="",
    pr_stdout=None,
    issue_rc=0,
    recorder=None,
):
    """An injectable run_gh returning captured-shape GitHub JSON.

    Fixture shape captured verbatim from a real
    `gh pr view <n> --json closingIssuesReferences,baseRefName,state,body`
    run against lneninger/legacy-repo-name PR #40 and PR #36 on
    2026-08-27 (see the suite's provenance note in case 1).
    """

    def run_gh(args):
        if recorder is not None:
            recorder.append(list(args))
        if args and args[0] == "--version":
            return (version_rc, "gh version 2.96.0\n", version_err)
        if args[:2] == ["repo", "view"]:
            # gh reports the CANONICAL name, which differs from the brief's alias.
            return (0, json.dumps({"nameWithOwner": canonical,
                                   "defaultBranchRef": {"name": default_branch}}), "")
        if args[:2] == ["pr", "view"]:
            if pr_rc != 0:
                return (pr_rc, pr_stdout or "", pr_err)
            return (
                0,
                json.dumps(
                    {
                        "number": 40,
                        "state": pr_state,
                        "baseRefName": base,
                        "body": body,
                        "closingIssuesReferences": closing or [],
                    }
                ),
                "",
            )
        if args[:2] == ["issue", "view"]:
            if issue_rc != 0:
                return (issue_rc, "", "could not resolve to an Issue")
            return (0, json.dumps({"state": issue_state}), "")
        return (1, "", "unexpected argv: %r" % (args,))

    return run_gh


def verify(brief, conv, run_gh, pr=40, repair_attempted=False):
    return V.verify(
        brief_path=brief,
        pr_number=pr,
        repo=REPO,
        conventions_path=conv,
        run_gh=run_gh,
        repair_attempted=repair_attempted,
    )


def tmp():
    return tempfile.TemporaryDirectory()


# ==========================================================================
# Case 1 -- linked
# ==========================================================================
def case_01_linked():
    name = "1  linked: resolved ref matches (owner, repo, number)"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root), write_conventions(root), gh_stub(closing=MATCHING))
        check(name, r["verdict"] == "linked", "got %r" % r["verdict"])
        check("1  linked writes issue_link: closes",
              r.get("issue_link") == "closes", "got %r" % r.get("issue_link"))
        check("1  linked does not halt", r.get("halt") is False, "got %r" % r.get("halt"))


# ==========================================================================
# Case 2 -- not-applicable, FOUR separate checks (no any-match)
# ==========================================================================
def case_02_not_applicable():
    for token, label in (("none", "none"), ("None", "None"),
                         ("", "empty string"), (None, "missing key")):
        name = "2  not-applicable: id %s" % label
        if need_subject(name):
            continue
        with tmp() as d:
            root = Path(d)
            brief = write_brief(root, id=token)
            r = verify(brief, write_conventions(root), gh_stub())
            check(name, r["verdict"] == "not-applicable", "got %r" % r["verdict"])
            check("2  id %s writes issue_link: none" % label,
                  r.get("issue_link") == "none", "got %r" % r.get("issue_link"))
            check("2  id %s proceeds (does not halt)" % label,
                  r.get("halt") is False, "got %r" % r.get("halt"))


# ==========================================================================
# Case 2b -- unresolved-id (D-2). The pair that catches the Rev 1 collapse.
# ==========================================================================
def case_02b_unresolved_id():
    for token in ("UNKNOWN", "unknown"):
        name = "2b unresolved-id: id %s halts" % token
        if need_subject(name):
            continue
        with tmp() as d:
            root = Path(d)
            r = verify(write_brief(root, id=token), write_conventions(root), gh_stub())
            check(name, r["verdict"] == "unresolved-id", "got %r" % r["verdict"])
            check("2b id %s halts" % token, r.get("halt") is True, "got %r" % r.get("halt"))
            check("2b id %s reason names the unresolved id" % token,
                  token in (r.get("reason") or ""), "reason=%r" % r.get("reason"))
            check("2b id %s is NOT not-applicable" % token,
                  r["verdict"] != "not-applicable", "got %r" % r["verdict"])

    # POSITIVE CONTROL: identical fixture with id: none must proceed.
    name = "2b POSITIVE CONTROL: identical fixture with id none -> not-applicable"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root, id="none"), write_conventions(root), gh_stub())
        check(name, r["verdict"] == "not-applicable", "got %r" % r["verdict"])
        check("2b POSITIVE CONTROL proceeds", r.get("halt") is False, "got %r" % r.get("halt"))


# ==========================================================================
# Case 3 / 4 -- partial handling
# ==========================================================================
def case_03_exempt_partial():
    name = "3  exempt-partial: partial true, no matching link"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root, partial="true"), write_conventions(root),
                   gh_stub(body="## Summary\n\nRefs #39\n"))
        check(name, r["verdict"] == "exempt-partial", "got %r" % r["verdict"])
        check("3  exempt-partial writes issue_link: refs",
              r.get("issue_link") == "refs", "got %r" % r.get("issue_link"))
        check("3  exempt-partial proceeds", r.get("halt") is False, "got %r" % r.get("halt"))


def case_04_unexpected_closing_ref():
    name = "4  unexpected-closing-ref: partial true BUT matching link present"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root, partial="true"), write_conventions(root),
                   gh_stub(closing=MATCHING))
        check(name, r["verdict"] == "unexpected-closing-ref", "got %r" % r["verdict"])
        check("4  unexpected-closing-ref halts", r.get("halt") is True, "got %r" % r.get("halt"))


# ==========================================================================
# Case 5 -- absent-repairable, exact proposedBody
# ==========================================================================
def case_05_absent_repairable():
    name = "5  absent-repairable: same repo, default base, empty refs, no Refs line"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root), write_conventions(root), gh_stub(body=PLAIN_BODY))
        check(name, r["verdict"] == "absent-repairable", "got %r" % r["verdict"])
        expected = PLAIN_BODY.rstrip("\n") + "\n\nCloses #39\n"
        check("5  proposedBody is the EXACT expected string",
              r.get("proposedBody") == expected,
              "got %r expected %r" % (r.get("proposedBody"), expected))
        # "single-line change" means one line of CONTENT. The repair also adds a
        # blank separator, without which the keyword would join the preceding
        # markdown paragraph. Assert that precisely rather than loosely: exactly
        # one non-blank addition, equal to the closing line, and NOTHING removed.
        diff_lines = (r.get("bodyDiff") or "").splitlines()
        added = [ln for ln in diff_lines
                 if ln.startswith("+") and not ln.startswith("+++")]
        removed = [ln for ln in diff_lines
                   if ln.startswith("-") and not ln.startswith("---")]
        content_added = [ln for ln in added if ln[1:].strip()]
        check("5  bodyDiff adds exactly one line of content, and it is the closing line",
              len(content_added) == 1 and content_added[0] == "+Closes #39",
              "content_added=%r (all additions %r)" % (content_added, added))
        check("5  bodyDiff removes nothing -- a repair only appends",
              removed == [], "removed=%r" % (removed,))


# ==========================================================================
# Case 6 -- undeclared-target, two checks
# ==========================================================================
def case_06_undeclared_target():
    name = "6a undeclared-target: cross-repo id"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root, id="other/repo#7"), write_conventions(root), gh_stub())
        check(name, r["verdict"] == "undeclared-target", "got %r" % r["verdict"])
        check("6a cross-repo halts with ZERO repairs",
              r.get("halt") is True and r.get("proposedBody") is None,
              "halt=%r proposedBody=%r" % (r.get("halt"), r.get("proposedBody")))

    name = "6b undeclared-target: base is not the declared base"
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root), write_conventions(root),
                   gh_stub(base="develop", default_branch="master"))
        check(name, r["verdict"] == "undeclared-target", "got %r" % r["verdict"])
        check("6b non-default base halts with ZERO repairs",
              r.get("halt") is True and r.get("proposedBody") is None,
              "halt=%r proposedBody=%r" % (r.get("halt"), r.get("proposedBody")))


# ==========================================================================
# Case 7 -- still-absent (the one halting verdict that WRITES, INV-14)
# ==========================================================================
def case_07_still_absent():
    name = "7  still-absent: re-query after repair still empty"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root), write_conventions(root),
                   gh_stub(body="## Summary\n\nCloses #39\n"), repair_attempted=True)
        check(name, r["verdict"] == "still-absent", "got %r" % r["verdict"])
        check("7  still-absent halts", r.get("halt") is True, "got %r" % r.get("halt"))
        check("7  still-absent WRITES issue_link: unresolved (INV-14)",
              r.get("issue_link") == "unresolved", "got %r" % r.get("issue_link"))


# ==========================================================================
# Case 8 -- malformed-id, three separate spellings
# ==========================================================================
def case_08_malformed_id():
    for token in ("39a", "TBD", "#"):
        name = "8  malformed-id: id %r halts" % token
        if need_subject(name):
            continue
        with tmp() as d:
            root = Path(d)
            r = verify(write_brief(root, id=token), write_conventions(root),
                       gh_stub(closing=MATCHING))
            check(name, r["verdict"] == "malformed-id", "got %r" % r["verdict"])
            check("8  id %r halts" % token, r.get("halt") is True, "got %r" % r.get("halt"))
            check("8  id %r does NOT coerce to 39" % token,
                  (r.get("issueRef") or {}).get("number") != 39,
                  "issueRef=%r" % (r.get("issueRef"),))


# ==========================================================================
# Case 9 -- unverifiable, FIVE separate causes with literal remediations
# ==========================================================================
def case_09_unverifiable():
    specs = [
        ("gh-missing", "winget install",
         dict(version_rc=127, version_err="'gh' is not recognized")),
        ("gh-unauthenticated", "gh auth login",
         dict(version_rc=1, version_err="You are not logged into any GitHub hosts")),
        ("query-failed", "Retry",
         dict(pr_rc=1, pr_err="dial tcp: lookup api.github.com: no such host")),
        ("pr-not-found", "--pr",
         dict(pr_rc=1, pr_err="Could not resolve to a PullRequest with the number of 9999")),
    ]
    for cause, literal, kwargs in specs:
        name = "9  unverifiable cause=%s" % cause
        if need_subject(name):
            continue
        with tmp() as d:
            root = Path(d)
            r = verify(write_brief(root), write_conventions(root), gh_stub(**kwargs))
            check(name, r["verdict"] == "unverifiable", "got %r" % r["verdict"])
            check("9  %s exact cause" % cause, r.get("cause") == cause, "got %r" % r.get("cause"))
            check("9  %s exits non-zero" % cause, r.get("exit_code", 0) != 0,
                  "exit_code=%r" % r.get("exit_code"))
            check("9  %s remediation contains %r" % (cause, literal),
                  literal in (r.get("remediation") or ""),
                  "remediation=%r" % r.get("remediation"))
            check("9  %s does NOT silently return not-applicable" % cause,
                  r["verdict"] != "not-applicable", "got %r" % r["verdict"])

    # (e) conventions-missing -- INV-9's third state.
    name = "9  unverifiable cause=conventions-missing"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root, block=None)  # file exists, no issueLink block
        r = verify(write_brief(root), conv, gh_stub())
        check(name, r["verdict"] == "unverifiable", "got %r" % r["verdict"])
        check("9  conventions-missing exact cause",
              r.get("cause") == "conventions-missing", "got %r" % r.get("cause"))
        check("9  conventions-missing exits non-zero",
              r.get("exit_code", 0) != 0, "exit_code=%r" % r.get("exit_code"))
        check("9  conventions-missing remediation names the block",
              "issueLink" in (r.get("remediation") or ""),
              "remediation=%r" % r.get("remediation"))
        check("9  conventions-missing does NOT silently return not-applicable",
              r["verdict"] != "not-applicable", "got %r" % r["verdict"])


# ==========================================================================
# Case 9b -- the four states Rev 1 left unmapped
# ==========================================================================
def case_09b_unmapped_states():
    name = "9b pr-not-open: merged PR with empty refs"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root), write_conventions(root),
                   gh_stub(pr_state="MERGED", body=PLAIN_BODY))
        check(name, r["verdict"] == "pr-not-open", "got %r" % r["verdict"])
        # Rev 1's failure: this input satisfied absent-repairable and produced a repair.
        check("9b pr-not-open produces NO proposedBody",
              r.get("proposedBody") is None, "got %r" % r.get("proposedBody"))
        check("9b pr-not-open halts", r.get("halt") is True, "got %r" % r.get("halt"))

    name = "9b foreign-closing-ref: resolved ref names issue 12 while shipping 39"
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root), write_conventions(root), gh_stub(closing=FOREIGN))
        check(name, r["verdict"] == "foreign-closing-ref", "got %r" % r["verdict"])
        check("9b foreign-closing-ref produces NO proposedBody",
              r.get("proposedBody") is None, "got %r" % r.get("proposedBody"))
        check("9b foreign-closing-ref halts", r.get("halt") is True, "got %r" % r.get("halt"))

    name = "9b issue-already-closed"
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root), write_conventions(root),
                   gh_stub(issue_state="CLOSED"))
        check(name, r["verdict"] == "issue-already-closed", "got %r" % r["verdict"])
        check("9b issue-already-closed halts", r.get("halt") is True, "got %r" % r.get("halt"))

    name = "9b issue-unreachable"
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root), write_conventions(root), gh_stub(issue_rc=1))
        check(name, r["verdict"] == "issue-unreachable", "got %r" % r["verdict"])
        check("9b issue-unreachable halts with ZERO repairs",
              r.get("halt") is True and r.get("proposedBody") is None,
              "halt=%r proposedBody=%r" % (r.get("halt"), r.get("proposedBody")))


# ==========================================================================
# Case 10 -- NEGATIVE CONTROL: goes RED if comparison weakens to number-only
# ==========================================================================
def case_10_negative_control():
    name = "10 NEGATIVE CONTROL: same number, different owner is NOT linked"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root), write_conventions(root),
                   gh_stub(closing=SAME_NUMBER_OTHER_OWNER))
        check(name, r["verdict"] != "linked",
              "number-only comparison would return linked; got %r" % r["verdict"])
        check("10 NEGATIVE CONTROL does not write issue_link: closes",
              r.get("issue_link") != "closes", "got %r" % r.get("issue_link"))


# ==========================================================================
# Case 11 -- brief-reading corpus, measured in THIS worktree at Rev 2
# ==========================================================================
def case_11_brief_corpus():
    # id: 11 distinct values across 14 briefs -- none x4 plus ten numbers.
    for token in ("6", "8", "9", "11", "14", "18", "25", "33", "35", "39"):
        name = "11 id %r normalizes to kind=number, value %s" % (token, token)
        if need_subject(name):
            continue
        with tmp() as d:
            root = Path(d)
            reading = V.read_brief_id(write_brief(root, id=token).read_text(encoding="utf-8"),
                                      ISSUE_LINK_BLOCK, REPO)
            check(name,
                  reading.get("kind") == "number"
                  and (reading.get("issueRef") or {}).get("number") == int(token),
                  "got %r" % (reading,))

    name = "11 id none normalizes to kind=absent"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        reading = V.read_brief_id(write_brief(root, id="none").read_text(encoding="utf-8"),
                                  ISSUE_LINK_BLOCK, REPO)
        check(name, reading.get("kind") == "absent", "got %r" % (reading,))

    # pr: ALL SIX spellings observed in-tree, each its own check. Kinds are the
    # contract's declared closed set: url | placeholder | absent | malformed.
    # NOTE `UNKNOWN` is a PLACEHOLDER here, not `unresolved`. That asymmetry with
    # read_brief_id is deliberate: an unresolved *issue id* must halt, because it
    # decides a verdict; an unfilled *pr:* decides nothing (/ship passes --pr).
    pr_specs = [
        ("https://github.com/lneninger/legacy-repo-name/pull/23", "url", False),
        ("https://github.com/lneninger/legacy-repo-name/pull/23 (draft)", "url", True),
        ("pending", "placeholder", False),
        ("UNKNOWN", "placeholder", False),
        ("<filled by /ship>", "placeholder", False),
        ("none", "absent", False),
    ]
    for raw, kind, is_draft in pr_specs:
        name = "11 pr %r -> kind=%s" % (raw, kind)
        with tmp() as d:
            root = Path(d)
            reading = V.read_brief_pr(write_brief(root, pr=raw).read_text(encoding="utf-8"))
            check(name, reading.get("kind") == kind, "got %r" % (reading,))
            if is_draft:
                check("11 pr %r sets isDraftSuffix true" % raw,
                      reading.get("isDraftSuffix") is True, "got %r" % (reading,))

    name = "11 pr malformed emits briefPrNote"
    with tmp() as d:
        root = Path(d)
        reading = V.read_brief_pr(write_brief(root, pr="ftp://nope").read_text(encoding="utf-8"))
        check(name, reading.get("kind") == "malformed", "got %r" % (reading,))
        check("11 malformed pr carries a briefPrNote",
              bool(reading.get("briefPrNote")), "got %r" % (reading,))


# ==========================================================================
# Case 12 -- READ-ONLY PROOF (INV-10): observe the HAZARD, not the seam
# ==========================================================================
def case_12_read_only_proof():
    name = "12 read-only: no subprocess/os.system/open bypasses the run_gh seam"
    if need_subject(name):
        return
    import builtins
    import os
    import subprocess

    bypass = []

    def recorder(label):
        def _rec(*a, **kw):
            bypass.append((label, a, kw))
            raise AssertionError("%s bypassed the run_gh seam" % label)
        return _rec

    # The subject reads through pathlib, which routes to io.open -- NOT
    # builtins.open. Patching builtins alone recorded ZERO opens across a whole
    # run, so `opened_write == []` could not fail and a Path.write_text
    # violation was invisible. Patch BOTH: io.open for pathlib, builtins.open
    # for any direct open() a future edit might add.
    import io

    real_io_open = io.open
    opened_write = []

    def open_spy(file, mode="r", *a, **kw):
        if any(ch in mode for ch in "wxa+"):
            opened_write.append((file, mode))
        return real_io_open(file, mode, *a, **kw)

    saved = (subprocess.run, subprocess.Popen, os.system, builtins.open, io.open)
    gh_calls = []
    with tmp() as d:
        root = Path(d)
        # Build the fixtures BEFORE the spy is installed. Writing them inside
        # the patched window records the harness's own writes and makes the
        # assertion fail for a reason that has nothing to do with the subject.
        brief_path = write_brief(root)
        conv_path = write_conventions(root)
        try:
            io.open = open_spy
            V.subprocess.run = recorder("subprocess.run")       # type: ignore[attr-defined]
            V.subprocess.Popen = recorder("subprocess.Popen")   # type: ignore[attr-defined]
            V.os.system = recorder("os.system")                 # type: ignore[attr-defined]
            builtins.open = open_spy
            try:
                verify(brief_path, conv_path,
                       gh_stub(closing=MATCHING, recorder=gh_calls))
            except AssertionError:
                # A bypass recorder fired. Swallow it HERE so the assertions
                # below still run and report against the recorders, which is
                # what the contract specifies -- otherwise the case aborts and
                # the failure surfaces as a generic function-level error.
                pass
        finally:
            subprocess.run, subprocess.Popen, os.system, builtins.open, io.open = saved
            V.subprocess.run, V.subprocess.Popen = saved[0], saved[1]  # type: ignore[attr-defined]
            V.os.system = saved[2]                                     # type: ignore[attr-defined]

    check(name, bypass == [], "bypass recorder fired: %r" % (bypass,))
    mutating = [c for c in gh_calls
                if c[:2] in (["pr", "edit"], ["issue", "create"], ["issue", "comment"],
                             ["issue", "close"])]
    check("12 read-only: seam recorded NO mutating gh argv",
          mutating == [], "mutating=%r" % (mutating,))
    check("12 read-only: seam recorded at least one read (gh pr view)",
          any(c[:2] == ["pr", "view"] for c in gh_calls), "gh_calls=%r" % (gh_calls,))
    check("12 read-only: zero write-mode open() calls",
          opened_write == [], "write opens=%r" % (opened_write,))

    # POSITIVE CONTROLS -- both must exercise THE SUBJECT, not the patched
    # symbol. Calling subprocess.run directly only proves a closure raises when
    # invoked; it proves nothing about whether the wiring observes the module.
    probe = []

    def probe_rec(*a, **kw):
        probe.append((a, kw))
        raise AssertionError("probe")

    saved_run = subprocess.run
    try:
        V.subprocess.run = probe_rec  # type: ignore[attr-defined]
        try:
            V.default_run_gh(["--version"])   # the SUBJECT's own seam
        except AssertionError:
            pass
    finally:
        subprocess.run = saved_run
        V.subprocess.run = saved_run  # type: ignore[attr-defined]
    check("12 POSITIVE CONTROL: the subject's own run_gh trips the bypass recorder",
          probe != [], "recorder never fired via the subject -- the wiring is inert")

    # POSITIVE CONTROL for the write spy: a real pathlib write through the
    # SUBJECT's own Path must be recorded. Without this, `opened_write == []`
    # is unfalsifiable -- which is exactly how it shipped.
    write_probe = []
    saved_io = io.open

    def write_spy(file, mode="r", *a, **kw):
        if any(ch in mode for ch in "wxa+"):
            write_probe.append((file, mode))
        return saved_io(file, mode, *a, **kw)

    try:
        io.open = write_spy
        with tmp() as d:
            V.Path(Path(d) / "probe.txt").write_text("x", encoding="utf-8")
    finally:
        io.open = saved_io
    check("12 POSITIVE CONTROL: a pathlib write IS visible to the write spy",
          write_probe != [],
          "the spy cannot see pathlib writes -- 'zero write-mode opens' is unfalsifiable")


# ==========================================================================
# Case 13 -- INV-3 / AC-4 enforcement (D-3), rule 13
# ==========================================================================
def case_13_refs_without_partial():
    body_with_refs = "## Summary\n\nPartial work.\n\nRefs #39\n"

    name = "13 NEGATIVE: body has Refs #39, brief has no partial key"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root, partial=None), write_conventions(root),
                   gh_stub(body=body_with_refs))
        check(name, r["verdict"] == "refs-without-partial", "got %r" % r["verdict"])
        check("13 NEGATIVE: refs-without-partial produces NO proposedBody",
              r.get("proposedBody") is None, "got %r" % r.get("proposedBody"))

    # POSITIVE CONTROL: identical fixture, Refs line deleted.
    name = "13 POSITIVE CONTROL: same fixture without the Refs line -> absent-repairable"
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root, partial=None), write_conventions(root),
                   gh_stub(body="## Summary\n\nPartial work.\n"))
        check(name, r["verdict"] == "absent-repairable", "got %r" % r["verdict"])
        check("13 POSITIVE CONTROL: proposedBody is NON-EMPTY",
              bool(r.get("proposedBody")), "got %r" % r.get("proposedBody"))

    # DISCRIMINATION CONTROL: Refs to a DIFFERENT issue must not trip rule 13.
    name = "13 DISCRIMINATION: Refs #12 while shipping #39 -> absent-repairable"
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root, partial=None), write_conventions(root),
                   gh_stub(body="## Summary\n\nRefs #12\n"))
        check(name, r["verdict"] == "absent-repairable", "got %r" % r["verdict"])


# ==========================================================================
# Ordering guard -- order IS the enforcement (INV-3 / INV-13)
# ==========================================================================
def case_14_rule_order():
    name = "14 rule order: pr-not-open (7) wins over absent-repairable (14)"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root), write_conventions(root),
                   gh_stub(pr_state="MERGED", body=PLAIN_BODY))
        check(name, r["verdict"] == "pr-not-open", "got %r" % r["verdict"])

    name = "14 rule order: refs-without-partial (13) wins over absent-repairable (14)"
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root, partial=None), write_conventions(root),
                   gh_stub(body="## Summary\n\nRefs #39\n"))
        check(name, r["verdict"] == "refs-without-partial", "got %r" % r["verdict"])

    name = "14 rule order: undeclared-target (12) wins over refs-without-partial (13)"
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root), write_conventions(root),
                   gh_stub(base="develop", body="## Summary\n\nRefs #39\n"))
        check(name, r["verdict"] == "undeclared-target", "got %r" % r["verdict"])


# ==========================================================================
# Coverage guard -- every declared verdict has its own case above
# ==========================================================================
ALL_VERDICTS = [
    "unverifiable", "malformed-id", "unresolved-id", "not-applicable",
    "issue-unreachable", "issue-already-closed", "pr-not-open",
    "foreign-closing-ref", "unexpected-closing-ref", "exempt-partial",
    "deferred-close", "linked", "undeclared-target", "refs-without-partial",
    "absent-repairable", "still-absent",
]
ALL_CAUSES = ["gh-missing", "gh-unauthenticated", "query-failed",
              "pr-not-found", "conventions-missing"]


def case_17_resolver_failure_on_every_gh_read():
    """CRITICAL 1 -- every gh read must map to a failure verdict, not a fallback.

    The rename fix added a THIRD gh read (`gh repo view`) whose return code was
    discarded, so an outage silently substituted the stale repo alias and a
    hardcoded "master". That turned `linked` into `foreign-closing-ref` AND still
    permitted `absent-repairable` to fire a real `gh pr edit` on degraded data.
    """
    def failing_repo_view(inner):
        def run_gh(args):
            if args[:2] == ["repo", "view"]:
                return (1, "", "dial tcp: lookup api.github.com: no such host")
            return inner(args)
        return run_gh

    name = "17 gh repo view failure -> unverifiable, NOT a silent fallback"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root), write_conventions(root),
                   failing_repo_view(gh_stub(closing=MATCHING)))
        check(name, r["verdict"] == "unverifiable", "got %r" % r["verdict"])
        check("17 gh repo view failure carries a cause",
              r.get("cause") in ALL_CAUSES, "got %r" % r.get("cause"))
        check("17 gh repo view failure exits non-zero",
              r.get("exit_code", 0) != 0, "got %r" % r.get("exit_code"))
        check("17 gh repo view failure does NOT report foreign-closing-ref",
              r["verdict"] != "foreign-closing-ref",
              "stale-alias comparison resurfaced; got %r" % r["verdict"])

    name = "17 gh repo view failure NEVER proposes a repair"
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root), write_conventions(root),
                   failing_repo_view(gh_stub(body=PLAIN_BODY)))
        check(name, r.get("proposedBody") is None,
              "a gh pr edit would fire on degraded data; got %r" % r.get("proposedBody"))
        check("17 gh repo view failure halts", r.get("halt") is True,
              "got %r" % r.get("halt"))

    # POSITIVE CONTROL: identical fixture, repo view healthy -> linked.
    name = "17 POSITIVE CONTROL: healthy gh repo view -> linked"
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root), write_conventions(root), gh_stub(closing=MATCHING))
        check(name, r["verdict"] == "linked", "got %r" % r["verdict"])

    # The hardcoded "master" fallback must be gone: a repo whose default branch
    # is `main` must NOT be told its base is not the default branch.
    #
    # `closing=[]` IS THE POINT. Rule 12 is the only rule that reads
    # baseIsDefaultBranch, and it sits BELOW rule 11 (`linked`). An earlier
    # version of this check passed `closing=MATCHING`, so rule 11 fired first
    # and the guarded field was never evaluated -- hardcoding "master" back into
    # the subject left the whole suite green. In a first-match-wins procedure a
    # fixture must be built to REACH the rule under test.
    name = "17 default branch is read from gh, not hardcoded to master"
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root), write_conventions(root),
                   gh_stub(closing=[], base="main", default_branch="main"))
        check(name, r["verdict"] == "absent-repairable",
              "a hardcoded 'master' default would say undeclared-target; got %r" % r["verdict"])

    # NEGATIVE CONTROL: a base that genuinely is NOT the default must still halt,
    # so the fix cannot be "stop checking the base branch at all".
    name = "17 NEGATIVE CONTROL: a genuinely non-default base is still undeclared-target"
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root), write_conventions(root),
                   gh_stub(closing=[], base="master", default_branch="main"))
        check(name, r["verdict"] == "undeclared-target", "got %r" % r["verdict"])

    # gh issue view failing is a RESOLVER failure, not "issue transferred/deleted".
    name = "17 gh issue view transport failure -> unverifiable, not issue-unreachable"
    with tmp() as d:
        root = Path(d)

        def failing_issue_view(args):
            if args[:2] == ["issue", "view"]:
                return (1, "", "dial tcp: lookup api.github.com: no such host")
            return gh_stub(closing=MATCHING)(args)

        r = verify(write_brief(root), write_conventions(root), failing_issue_view)
        check(name, r["verdict"] == "unverifiable",
              "a transport error was diagnosed as a deleted issue; got %r" % r["verdict"])

    # POSITIVE CONTROL: a genuine "no such issue" IS issue-unreachable.
    name = "17 POSITIVE CONTROL: genuine missing issue -> issue-unreachable"
    with tmp() as d:
        root = Path(d)

        def missing_issue(args):
            if args[:2] == ["issue", "view"]:
                return (1, "", "Could not resolve to an Issue with the number of 39.")
            return gh_stub(closing=[])(args)

        r = verify(write_brief(root), write_conventions(root), missing_issue)
        check(name, r["verdict"] == "issue-unreachable", "got %r" % r["verdict"])


def case_18_brief_pr_note_reaches_the_verdict():
    """CRITICAL 2 -- read_brief_pr had no production caller.

    It was fully written and tested directly, so 8 checks were green over code
    that `verify()` never invoked, while ship/SKILL.md told the shipper to print
    a `briefPrNote` the verdict could not carry.
    """
    name = "18 briefPrNote reaches the verdict when pr: is malformed"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root, pr="ftp://nope"), write_conventions(root),
                   gh_stub(closing=MATCHING))
        check(name, bool(r.get("briefPrNote")),
              "read_brief_pr is not wired into verify(); got %r" % r.get("briefPrNote"))

    # The `url` case is the reader's STATED reason to exist: Step 5 is about to
    # overwrite a URL already recorded -- a stale-brief / double-ship signal.
    name = "18 briefPrNote reaches the verdict when pr: already holds a URL"
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root, pr="https://github.com/lneninger/legacy-repo-name/pull/23"),
                   write_conventions(root), gh_stub(closing=MATCHING))
        check(name, bool(r.get("briefPrNote")),
              "the overwrite warning is unimplemented; got %r" % r.get("briefPrNote"))

    # NEGATIVE CONTROL: placeholder and absent must emit NOTHING, so the note
    # cannot be satisfied by always setting it.
    for raw in ("pending", "<filled by /ship>", "UNKNOWN", "none"):
        name = "18 NEGATIVE CONTROL: pr: %r emits no briefPrNote" % raw
        with tmp() as d:
            root = Path(d)
            r = verify(write_brief(root, pr=raw), write_conventions(root),
                       gh_stub(closing=MATCHING))
            check(name, not r.get("briefPrNote"), "got %r" % r.get("briefPrNote"))

    # The reading must not change the verdict -- it is bookkeeping only.
    name = "18 a malformed pr: does not change the verdict"
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root, pr="ftp://nope"), write_conventions(root),
                   gh_stub(closing=MATCHING))
        check(name, r["verdict"] == "linked", "got %r" % r["verdict"])


def case_19_declared_sets_match_the_conventions_file():
    """WARN -- three unsynchronized copies of one closed set.

    The JSON's `verdicts`/`unverifiableCauses` arrays were decorative: nothing
    read them, the script kept its own list, and the suite compared against a
    third hand-written copy. This is the drift INV-8 exists to prevent.
    """
    name = "19 subject VERDICTS == the conventions file's verdicts array"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root)
        block, cause = V.read_conventions(conv)
        check("19 fixture conventions load cleanly", cause is None, "cause=%r" % cause)
        check(name, list(V.VERDICTS) == list(block.get("verdicts") or []),
              "python=%r json=%r" % (list(V.VERDICTS), block.get("verdicts")))
        check("19 subject UNVERIFIABLE_CAUSES == the conventions file's array",
              list(V.UNVERIFIABLE_CAUSES) == list(block.get("unverifiableCauses") or []),
              "python=%r json=%r" % (list(V.UNVERIFIABLE_CAUSES),
                                     block.get("unverifiableCauses")))


def case_20_real_corpus_integration():
    """WARN -- nothing parsed the REAL conventions file or the REAL briefs.

    Every verdict case is fixture-isolated and stays that way. This ONE case is
    deliberately non-isolated: it reads the shipped conventions file and every
    real brief, because a typo'd key in the shipped JSON otherwise falls through
    to a hardcoded default instead of failing loud -- and because hand-transcribed
    corpus tokens are the same posture that produced the invented fixture shape.
    """
    name = "20 the REAL conventions file carries a loadable issueLink block"
    if need_subject(name):
        return
    block, cause = V.read_conventions()  # no argument -> the real locator
    check(name, cause is None and bool(block), "cause=%r" % cause)
    if not block:
        return
    check("20 the REAL conventions file agrees with the subject's VERDICTS",
          list(V.VERDICTS) == list(block.get("verdicts") or []),
          "json=%r" % (block.get("verdicts"),))

    briefs = sorted(V.work_items_dir().glob("*.md"))
    check("20 the real work-items dir is non-empty (positive control)",
          len(briefs) > 0, "found %d" % len(briefs))

    tally = {"number": 0, "absent": 0, "unresolved": 0, "malformed": 0, "skipped": 0}
    for b in briefs:
        text = b.read_text(encoding="utf-8", errors="ignore")
        if "id" not in V.parse_frontmatter(text):
            tally["skipped"] += 1      # e.g. SESSION-HANDOFF, which is not a brief
            continue
        tally[V.read_brief_id(text, block, CANONICAL)["kind"]] += 1

    check("20 every real brief's id: parses to a declared kind (none malformed)",
          tally["malformed"] == 0, "tally=%r" % (tally,))
    check("20 the real corpus contains at least one absent and one number id",
          tally["absent"] > 0 and tally["number"] > 0, "tally=%r" % (tally,))

    # The `pr:` axis, not just `id:`. This is the axis a previous revision got
    # WRONG -- its "five spellings" claim was falsified by a sixth living in
    # this very tree -- and the axis this changeset itself moved when the #6
    # backfill flipped `pr: pending` to a URL. Auditing only `id:` leaves the
    # error-prone half hand-transcribed, which is the posture that produced the
    # invented fixture shape.
    pr_tally = {"url": 0, "placeholder": 0, "absent": 0, "malformed": 0}
    for b in briefs:
        text = b.read_text(encoding="utf-8", errors="ignore")
        if "pr" not in V.parse_frontmatter(text):
            continue
        pr_tally[V.read_brief_pr(text)["kind"]] += 1

    check("20 every real brief's pr: parses to a declared kind (none malformed)",
          pr_tally["malformed"] == 0, "tally=%r" % (pr_tally,))
    check("20 the real corpus exercises url, placeholder AND absent pr: spellings",
          all(pr_tally[k] > 0 for k in ("url", "placeholder", "absent")),
          "tally=%r" % (pr_tally,))


def case_21_fail_open_and_relative_brief():
    """INV-9's fail-OPEN half, and the locator R-14 added for it.

    Every fail-LOUD cause has its own case (case 9, five of them). The opposite
    branch had none -- so an edit that made a missing brief HALT would break
    `/ship` on every free-text branch with nothing going RED. The relative-path
    resolution through `work_items_dir()` is the whole reason that locator
    exists (INV-12's word "every"), and it was equally unpinned.
    """
    name = "21 INV-9 fail-OPEN: a missing brief file proceeds, exit 0"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        conv = write_conventions(root)
        r = verify(root / "no-such-brief.md", conv, gh_stub(closing=MATCHING))
        check(name, r["verdict"] == "not-applicable", "got %r" % r["verdict"])
        check("21 fail-open does NOT halt", r.get("halt") is False, "got %r" % r.get("halt"))
        check("21 fail-open exits 0", r.get("exit_code", 0) == 0,
              "got %r" % r.get("exit_code"))

    # NEGATIVE CONTROL: a missing RESOLVER still fails LOUD. Without this pair,
    # "fail open on absence" could be implemented as "never fail at all".
    name = "21 NEGATIVE CONTROL: a missing RESOLVER still fails loud"
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root), write_conventions(root),
                   gh_stub(version_rc=127, version_err="'gh' is not recognized"))
        check(name, r["verdict"] == "unverifiable" and r.get("exit_code", 0) != 0,
              "got %r exit=%r" % (r["verdict"], r.get("exit_code")))

    # A relative --brief resolves through work_items_dir() (INV-12).
    name = "21 a relative --brief resolves through work_items_dir()"
    real_briefs = sorted(V.work_items_dir().glob("*.md"))
    check("21 work_items_dir() resolves to a populated real directory (positive control)",
          len(real_briefs) > 0, "found %d" % len(real_briefs))
    if real_briefs:
        target = next((b for b in real_briefs if "pr-issue-close-linkage" in b.name),
                      real_briefs[0])
        with tmp() as d:
            conv = write_conventions(Path(d))
            r = verify(Path(target.name), conv, gh_stub(closing=MATCHING))
            check(name, r["verdict"] != "not-applicable",
                  "bare filename did not resolve through work_items_dir(); got %r"
                  % r["verdict"])


def case_16_rename_and_real_shape():
    """Regression cases for two bugs that ALL fixture-only tests missed."""
    # (a) The renamed repo. Brief says the alias; gh reports canonical.
    name = "16 renamed repo: brief alias + canonical resolved link -> linked"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        r = verify(write_brief(root, repo=REPO), write_conventions(root),
                   gh_stub(closing=MATCHING, canonical=CANONICAL))
        check(name, r["verdict"] == "linked",
              "alias-vs-canonical comparison broke; got %r" % r["verdict"])

    # (b) NEGATIVE CONTROL for (a): a genuinely different repo must NOT match,
    #     so the fix cannot be "compare the number and ignore the repo".
    name = "16 NEGATIVE CONTROL: a genuinely different repo is not linked"
    with tmp() as d:
        root = Path(d)
        other = [resolved_link(39, owner="lneninger", repo="SomeOtherProject")]
        r = verify(write_brief(root, repo=REPO), write_conventions(root),
                   gh_stub(closing=other, canonical=CANONICAL))
        check(name, r["verdict"] != "linked",
              "repo identity is being ignored entirely; got %r" % r["verdict"])

    # (c) Case-insensitivity -- GitHub treats owner/repo case-insensitively.
    name = "16 case-insensitive owner/repo still resolves as linked"
    with tmp() as d:
        root = Path(d)
        shouty = [resolved_link(39, owner=OWNER.upper(), repo=REPO_NAME.upper())]
        r = verify(write_brief(root, repo=REPO), write_conventions(root),
                   gh_stub(closing=shouty, canonical=CANONICAL))
        check(name, r["verdict"] == "linked", "got %r" % r["verdict"])

    # (d) The REAL nested shape is what normalize_resolved_link reads. A flat
    #     hand-invented dict must NOT normalize to a usable key -- that is the
    #     shape the first revision wrongly assumed.
    name = "16 normalize_resolved_link reads GitHub's NESTED shape"
    flat = {"owner": OWNER, "repo": REPO_NAME, "number": 39}
    nested = resolved_link(39)
    got_nested = V.normalize_resolved_link(nested)
    got_flat = V.normalize_resolved_link(flat)
    check(name,
          got_nested == {"owner": OWNER, "repo": REPO_NAME, "number": 39},
          "got %r" % (got_nested,))
    check("16 NEGATIVE CONTROL: the invented FLAT shape yields no repo identity",
          got_flat.get("repo") == "" and got_flat.get("owner") == "",
          "flat shape produced a usable key %r -- the bug would be invisible again"
          % (got_flat,))


def case_15_declared_sets():
    name = "15 subject declares exactly the 16 contract verdicts"
    if need_subject(name):
        return
    check(name, list(V.VERDICTS) == ALL_VERDICTS,
          "got %r" % (list(getattr(V, "VERDICTS", [])),))
    check("15 subject declares exactly the 5 unverifiable causes",
          list(V.UNVERIFIABLE_CAUSES) == ALL_CAUSES,
          "got %r" % (list(getattr(V, "UNVERIFIABLE_CAUSES", [])),))


# ==========================================================================
# Case 22-27 -- deferred-close, the sixteenth verdict.
#
# Contract: .claude/concepts/2026-09-19-flow-parent-subissue-topology.md,
# sub-task 3 ("Base aware closing link verifier"). New rule, ONE only,
# inserted immediately before rule 11 (linked), between rule 10
# (exempt-partial) and rule 11:
#
#   sameRepo and baseIsDeclaredBase and not baseIsDefaultBranch and (
#       relation == "match"
#       or (bodyHasClosingRefToThisIssue and not bodyHasRefsToThisIssue)
#   )
#
# verify() and compute_expectation() each gain ONE new keyword-defaulted
# parameter, declared_base=None, appended LAST. Before that parameter exists,
# every case below fails on TypeError -- reported as a named FAILED CHECK by
# _try_verify_declared, never an uncaught traceback.
# ==========================================================================
def verify_declared(brief, conv, run_gh, declared_base, pr=40, repair_attempted=False):
    """Like verify() above, but forwards declared_base.

    A SEPARATE wrapper, not an edit to verify(): that function is exercised
    by every existing case and sits outside the forced-edit table, so a new
    keyword belongs in a new function, never inserted into the old one.
    """
    return V.verify(
        brief_path=brief,
        pr_number=pr,
        repo=REPO,
        conventions_path=conv,
        run_gh=run_gh,
        repair_attempted=repair_attempted,
        declared_base=declared_base,
    )


def _try_verify_declared(name, brief, conv, run_gh, declared_base,
                         pr=40, repair_attempted=False):
    """Call verify_declared, turning a not-yet-existing signature into a named
    FAILED check instead of letting TypeError abort the whole case function.

    Returns the result dict, or None when the call could not even be made --
    callers must return early in that case, since there is nothing left to
    assert against.
    """
    try:
        return verify_declared(brief, conv, run_gh, declared_base, pr=pr,
                               repair_attempted=repair_attempted)
    except TypeError as exc:
        check(name, False,
              "V.verify() has no declared_base parameter yet -- %s" % exc)
        return None


def case_22_deferred_close_headline():
    """Headline behaviour AND the ordering pin, as one pair.

    The SAME resolved-link fixture must return "linked" when the base is the
    default branch, and "deferred-close" -- never "linked" -- the moment the
    base becomes the work item's DECLARED non-default target. The pairing is
    what proves the new rule now wins over rule 11 for exactly this slice of
    input space: a headline check alone would pass just as well if
    deferred-close had quietly replaced linked everywhere.
    """
    name = "22 deferred-close: resolved link + non-default DECLARED base"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        r = _try_verify_declared(
            name, write_brief(root), write_conventions(root),
            gh_stub(closing=MATCHING, base="feature/160-parent", default_branch="master"),
            declared_base="feature/160-parent",
        )
        if r is None:
            return
        check(name, r["verdict"] == "deferred-close", "got %r" % r["verdict"])
        check("22 deferred-close is NOT linked -- the new rule wins the position",
              r["verdict"] != "linked", "got %r" % r["verdict"])
        check("22 deferred-close writes issue_link: deferred",
              r.get("issue_link") == "deferred", "got %r" % r.get("issue_link"))
        check("22 deferred-close does not halt", r.get("halt") is False,
              "got %r" % r.get("halt"))

    name = "22 PAIRED CONTROL: identical fixture, base IS the default branch -> linked"
    with tmp() as d:
        root = Path(d)
        r = _try_verify_declared(
            name, write_brief(root), write_conventions(root),
            gh_stub(closing=MATCHING, base="master", default_branch="master"),
            declared_base="master",
        )
        if r is None:
            return
        check(name, r["verdict"] == "linked", "got %r" % r["verdict"])


def case_23_deferred_close_guard_same_repo():
    """POSITIVE CONTROL for the sameRepo term.

    Cross-repo, but the base matches what was declared and is non-default,
    and the reference resolves. Dropping sameRepo from the new rule's
    condition would wrongly return deferred-close instead of the cross-repo
    halt that must still fire.
    """
    name = "23 GUARD sameRepo: cross-repo resolved link on a declared non-default base"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        other = [resolved_link(7, owner="other-owner", repo="other-repo")]
        r = _try_verify_declared(
            name, write_brief(root, id="other-owner/other-repo#7"), write_conventions(root),
            gh_stub(closing=other, base="feature/non-default", default_branch="master"),
            declared_base="feature/non-default",
        )
        if r is None:
            return
        check(name, r["verdict"] == "undeclared-target", "got %r" % r["verdict"])
        check("23 GUARD sameRepo: still halts with ZERO repairs",
              r.get("halt") is True and r.get("proposedBody") is None,
              "halt=%r proposedBody=%r" % (r.get("halt"), r.get("proposedBody")))


def case_24_deferred_close_guard_declared_base():
    """POSITIVE CONTROL for the baseIsDeclaredBase term.

    Same repo, resolved link, a non-default actual base -- but the PR is NOT
    aimed at the base the work item declared. Dropping baseIsDeclaredBase
    from the condition would wrongly return deferred-close instead of
    halting as undeclared-target.
    """
    name = "24 GUARD baseIsDeclaredBase: resolved link on an UNDECLARED non-default base"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        r = _try_verify_declared(
            name, write_brief(root), write_conventions(root),
            gh_stub(closing=MATCHING, base="random-topic-branch", default_branch="master"),
            declared_base="feature/160-parent",
        )
        if r is None:
            return
        check(name, r["verdict"] == "undeclared-target", "got %r" % r["verdict"])
        check("24 GUARD baseIsDeclaredBase: still halts with ZERO repairs",
              r.get("halt") is True and r.get("proposedBody") is None,
              "halt=%r proposedBody=%r" % (r.get("halt"), r.get("proposedBody")))


def case_25_deferred_close_guard_default_branch():
    """POSITIVE CONTROL for the not-baseIsDefaultBranch term.

    Resolved link, base IS the default branch and IS the declared base --
    linked really does fire here and must stay reachable. Dropping
    not-baseIsDefaultBranch would wrongly return deferred-close instead.
    Also proves declared_base=None resolves to the default branch INSIDE
    compute_expectation, not at the call site.
    """
    name = "25 GUARD not-baseIsDefaultBranch: declared base IS the default branch -> linked"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        r = _try_verify_declared(
            name, write_brief(root), write_conventions(root),
            gh_stub(closing=MATCHING, base="master", default_branch="master"),
            declared_base="master",
        )
        if r is None:
            return
        check(name, r["verdict"] == "linked", "got %r" % r["verdict"])

    name = "25 GUARD not-baseIsDefaultBranch: declared_base=None falls back to default -> linked"
    with tmp() as d:
        root = Path(d)
        r = _try_verify_declared(
            name, write_brief(root), write_conventions(root),
            gh_stub(closing=MATCHING, base="master", default_branch="master"),
            declared_base=None,
        )
        if r is None:
            return
        check(name, r["verdict"] == "linked", "got %r" % r["verdict"])


def case_26_deferred_close_guard_refs_residue():
    """POSITIVE CONTROL for the stale-parse-residue term.

    Body carries BOTH a closing keyword and a reference keyword for THIS
    issue on a declared non-default base, and GitHub has resolved neither
    (relation == "none"). Rule 13 must still win this input as
    refs-without-partial. Weakening the residue term
    (bodyHasClosingRefToThisIssue and not bodyHasRefsToThisIssue) to drop its
    second half would wrongly return deferred-close and swallow rule 13's
    halt for a body carrying both keywords.
    """
    name = "26 GUARD residue: body carries BOTH Closes AND Refs -> refs-without-partial"
    if need_subject(name):
        return
    with tmp() as d:
        root = Path(d)
        body = "## Summary\n\nRefs #39\n\nCloses #39\n"
        r = _try_verify_declared(
            name, write_brief(root, partial=None), write_conventions(root),
            gh_stub(closing=[], body=body, base="feature/160-parent",
                    default_branch="master"),
            declared_base="feature/160-parent",
        )
        if r is None:
            return
        check(name, r["verdict"] == "refs-without-partial", "got %r" % r["verdict"])
        check("26 GUARD residue: still produces NO proposedBody",
              r.get("proposedBody") is None, "got %r" % r.get("proposedBody"))


def case_27_deferred_close_is_non_halting():
    """deferred-close is NOT a member of HALTING, and the exit code says so.

    A closed-set membership property, pinned directly against HALTING rather
    than read only off one fixture's halt flag.
    """
    name = "27 deferred-close is NOT a member of HALTING"
    if need_subject(name):
        return
    check(name, "deferred-close" not in getattr(V, "HALTING", set()),
          "HALTING=%r" % (getattr(V, "HALTING", None),))

    name = "27 deferred-close exit code is 0 end to end"
    with tmp() as d:
        root = Path(d)
        r = _try_verify_declared(
            name, write_brief(root), write_conventions(root),
            gh_stub(closing=MATCHING, base="feature/160-parent", default_branch="master"),
            declared_base="feature/160-parent",
        )
        if r is None:
            return
        check(name, r.get("exit_code", 0) == 0, "got %r" % r.get("exit_code"))
        check("27 deferred-close halt flag is False",
              r.get("halt") is False, "got %r" % r.get("halt"))


def case_28_undeclared_target_rename_is_complete():
    """The retired verdict name must not survive anywhere this sub-task owns.

    Three spellings: the verdict string itself ("not-linkable"), the Python
    identifier form ("not_linkable"), and a COMMENT in prose with a SPACE
    ("not linkable") that a hyphen-only search misses. Scoped to
    .claude/scripts/ (recursively) and .claude/work-item-conventions.json --
    NOT .claude/concepts/, NOT docs/handbook/ (the retired name is kept there
    on purpose, a recorded Non-Goal) and NOT .claude/skills/ (sub-task 6's
    half of the rename). THIS FILE IS EXCLUDED from the scan: it necessarily
    carries the three search patterns as literal strings in this very
    docstring and case name, which would otherwise make it match itself
    forever, even after the rename lands everywhere else.
    """
    name = "28 rename complete: no retired verdict name anywhere this sub-task owns"
    if need_subject(name):
        return
    this_file = Path(__file__).resolve()
    conventions_path = Path(V.work_item_conventions_path())
    targets = [p for p in sorted(SCRIPTS_DIR.rglob("*.py"))
              if p.resolve() != this_file and "__pycache__" not in p.parts]
    targets.append(conventions_path)

    patterns = ["not-linkable", "not_linkable", "not linkable"]
    hits = []
    for path in targets:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in patterns:
            if pattern in text:
                hits.append("%s: %r" % (path, pattern))

    check(name, hits == [], "found the retired verdict name: %r" % (hits,))


def main():
    for fn in (
        case_01_linked, case_02_not_applicable, case_02b_unresolved_id,
        case_03_exempt_partial, case_04_unexpected_closing_ref,
        case_05_absent_repairable, case_06_undeclared_target, case_07_still_absent,
        case_08_malformed_id, case_09_unverifiable, case_09b_unmapped_states,
        case_10_negative_control, case_11_brief_corpus,
        case_12_read_only_proof, case_13_refs_without_partial,
        case_14_rule_order, case_15_declared_sets,
        case_16_rename_and_real_shape,
        case_17_resolver_failure_on_every_gh_read,
        case_18_brief_pr_note_reaches_the_verdict,
        case_19_declared_sets_match_the_conventions_file,
        case_20_real_corpus_integration,
        case_21_fail_open_and_relative_brief,
        case_22_deferred_close_headline,
        case_23_deferred_close_guard_same_repo,
        case_24_deferred_close_guard_declared_base,
        case_25_deferred_close_guard_default_branch,
        case_26_deferred_close_guard_refs_residue,
        case_27_deferred_close_is_non_halting,
        case_28_undeclared_target_rename_is_complete,
    ):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            check(fn.__name__, False, "raised %s: %s" % (type(exc).__name__, exc))

    failed = [r for r in _RESULTS if not r[0]]
    for ok, name, detail in _RESULTS:
        if not ok:
            print("FAIL  %s%s" % (name, ("  -- " + detail) if detail else ""))
    print("")
    print("%d checks, %d passed, %d failed" %
          (len(_RESULTS), len(_RESULTS) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
