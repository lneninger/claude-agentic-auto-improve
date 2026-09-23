#!/usr/bin/env python3
"""
verify_issue_link.py -- does GitHub actually report a Closing Link for this
pull request and this work item's issue?

Callers
-------
  * ``/ship`` Step 4d ("Verify the closing link") -- the only production
    caller. It branches on ``verdict``, performs at most ONE
    ``gh pr edit --body`` on ``absent-repairable``, then re-invokes with
    ``--repair-attempted``.
  * ``.claude/scripts/tests/test_verify_issue_link.py`` -- injects ``run_gh``.

CLI
---
    py -3 .claude/scripts/verify_issue_link.py --brief <path> --pr <n> [--json]
    py -3 .claude/scripts/verify_issue_link.py --brief <path> --pr <n> --repair-attempted

Contract: .claude/concepts/2026-08-27-pr-issue-close-linkage.md (work item #39).

WHY THIS EXISTS
---------------
A ``Closes #N`` line in a PR body is a REQUEST for a Closing Link, never
evidence of one. GitHub silently ignores the request when the reference is
cross-repo, when the PR's base is not the default branch, or when several
numbers are comma-joined onto one keyword. Measured 2026-08-27: 5 of the
last 12 merged PRs in this repo carried no resolved link, and issue #6 is
still open although PR #30 delivered it.

The only admissible proof is GitHub's own resolved reference (INV-1),
exposed by ``gh pr view --json closingIssuesReferences``. Measured on the
same day, that field DOES populate on OPEN pull requests (23 open PRs in
cli/cli, 10 in home-assistant/core), which is why the repair loop can run
before merge rather than only after it.

INVARIANTS THIS FILE OWNS
-------------------------
INV-1   Only a Resolved Closing Link proves a link. Never body text.
INV-9   A missing DATA FILE fails OPEN (not-applicable, exit 0). A missing
        RESOLVER fails LOUD (unverifiable, non-zero). Never a body-text
        fallback, in either direction.
INV-10  This module performs NO mutation of any GitHub object. Its only
        route to a subprocess is ``run_gh``, and it opens no file for
        writing. Test case 12 proves this by recording bypasses, not by
        observing the seam.
INV-12  Every path resolves through ``_claude_paths``. No ``Path.home()``,
        no drive letter, no absolute path literal.

THE ORDER IS THE ENFORCEMENT
----------------------------
``evaluate`` implements rules 1..16 literally, first match wins. The order
is not stylistic: rule 7 before rule 15 is what stops a ``gh pr edit``
firing against a merged PR, and rule 14 before rule 15 is what stops a
deliberate ``Refs #N`` being repaired into ``Closes #N`` (INV-3 / AC-4).
Do not rearrange these for readability -- the suite's ordering guard
(case 14) will go RED, and it is meant to.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _claude_paths import work_item_conventions_path, work_items_dir  # noqa: E402

# --------------------------------------------------------------------------
# Closed sets. Both are asserted verbatim by test case 15 -- adding a value
# here without adding its own case there is a test-coverage regression.
# --------------------------------------------------------------------------
VERDICTS = [
    "unverifiable",             # 1
    "malformed-id",             # 2
    "unresolved-id",            # 3
    "not-applicable",           # 4
    "issue-unreachable",        # 5
    "issue-already-closed",     # 6
    "pr-not-open",              # 7
    "foreign-closing-ref",      # 8
    "unexpected-closing-ref",   # 9
    "exempt-partial",           # 10
    "deferred-close",           # 11
    "linked",                   # 12
    "undeclared-target",        # 13
    "refs-without-partial",     # 14
    "absent-repairable",        # 15
    "still-absent",             # 16
]

UNVERIFIABLE_CAUSES = [
    "gh-missing",
    "gh-unauthenticated",
    "query-failed",
    "pr-not-found",
    "conventions-missing",
]

REMEDIATION = {
    "gh-missing": "winget install --id GitHub.cli, then gh auth login.",
    "gh-unauthenticated": "Run gh auth login and retry.",
    "query-failed": "Retry; if it persists, run the verifyCommand by hand and paste the output.",
    "pr-not-found": "Caller bug -- check the --pr argument against gh pr view.",
    "conventions-missing": (
        "Add the issueLink block to work-item-conventions.json "
        "(see the contract's Extension Points 1)."
    ),
}

# Which verdicts write the brief's issue_link field, and to what. Every other
# verdict writes nothing -- INV-14 makes still-absent the one halting verdict
# that still records its answer, because an unresolved link that is forgotten
# is the exact failure this work item exists to fix.
ISSUE_LINK_WRITES = {
    "linked": "closes",
    "deferred-close": "deferred",
    "not-applicable": "none",
    "exempt-partial": "refs",
    "still-absent": "unresolved",
}

HALTING = {
    "unverifiable", "malformed-id", "unresolved-id", "issue-unreachable",
    "issue-already-closed", "pr-not-open", "foreign-closing-ref",
    "unexpected-closing-ref", "undeclared-target", "refs-without-partial",
    "still-absent",
}


# --------------------------------------------------------------------------
# The one impure seam. Everything else in this module is pure.
# --------------------------------------------------------------------------
def default_run_gh(args):
    """Run ``gh`` and return ``(returncode, stdout, stderr)``.

    The ONLY route to a subprocess in this module (INV-10). Tests substitute
    a fixture runner; nothing else here may call subprocess, os.system, or
    open a file for writing.
    """
    try:
        proc = subprocess.run(
            ["gh"] + list(args),
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        return (127, "", "gh executable not found")
    return (proc.returncode, proc.stdout, proc.stderr)


# --------------------------------------------------------------------------
# Pure readers
# --------------------------------------------------------------------------
_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.S)


def parse_frontmatter(text):
    """Return the brief's frontmatter as an ordered dict of raw strings."""
    match = _FRONTMATTER.match(text.replace("\r\n", "\n"))
    if not match:
        return {}
    fields = {}
    for line in match.group(1).split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def read_conventions(conventions_path=None):
    """Load the issueLink block.

    Returns ``(block, cause)``. ``cause`` is ``conventions-missing`` when the
    file is absent or carries no issueLink block -- INV-9's third failure
    state, which fails LOUD rather than defaulting to a hardcoded keyword.
    """
    path = Path(conventions_path) if conventions_path else work_item_conventions_path()
    if not path.exists():
        return (None, "conventions-missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return (None, "conventions-missing")
    block = payload.get("issueLink")
    if not isinstance(block, dict) or not block:
        return (None, "conventions-missing")
    return (block, None)


_BARE = re.compile(r"\A#?(\d+)\Z")
_CROSS = re.compile(r"\A([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+)#(\d+)\Z")


def read_brief_id(brief_text, issue_link_block, repo):
    """Normalize the brief's ``id:`` into a Brief Id Reading.

    Four kinds. ``absent`` and ``unresolved`` are DELIBERATELY different
    (D-2): ``none`` means "this work has no issue" and is a success path,
    while ``UNKNOWN`` means "nobody filled this in" and must halt. Rev 1
    folded both onto ``absent`` and the success invariant then blessed the
    dangerous one -- rebuilding the coverage hole inside the mechanism built
    to close it.
    """
    fields = parse_frontmatter(brief_text)
    absent_tokens = issue_link_block.get("absentIdTokens", ["none", "None", ""])
    unresolved_tokens = issue_link_block.get("unresolvedIdTokens", ["UNKNOWN", "unknown"])

    if "id" not in fields:
        return {"kind": "absent", "raw": None}
    raw = fields["id"]
    if raw in absent_tokens:
        return {"kind": "absent", "raw": raw}
    if raw in unresolved_tokens:
        return {"kind": "unresolved", "raw": raw}

    owner, _, repo_name = repo.partition("/")
    bare = _BARE.match(raw)
    if bare:
        return {
            "kind": "number", "raw": raw,
            "issueRef": {"owner": owner, "repo": repo_name, "number": int(bare.group(1))},
            "sameRepo": True,
        }
    cross = _CROSS.match(raw)
    if cross:
        ref = {"owner": cross.group(1), "repo": cross.group(2), "number": int(cross.group(3))}
        return {
            "kind": "number", "raw": raw, "issueRef": ref,
            "sameRepo": (ref["owner"] == owner and ref["repo"] == repo_name),
        }
    return {"kind": "malformed", "raw": raw}


_URL = re.compile(r"\Ahttps://github\.com/[^\s]+/pull/(\d+)\Z")


def read_brief_pr(brief_text):
    """Normalize the brief's ``pr:`` field. Kinds: url | placeholder | absent | malformed.

    SIX spellings are live in this repo, not five: a bare URL, a URL with a
    trailing " (draft)" suffix, ``pending``, ``UNKNOWN``, ``none``, and the
    literal ``<filled by /ship>`` -- the last one falsified an earlier "five
    spellings" claim, which is why this reader has its own required test.

    **This reading decides no verdict.** ``/ship`` passes the PR number it just
    created or edited via ``--pr``, so the brief's ``pr:`` never gates anything.
    Its one job is bookkeeping honesty, via ``briefPrNote``:

    * ``url``       -- Step 5 is about to **overwrite** a URL already recorded.
                       That is a stale-brief or double-ship signal and earns a
                       line in the SHIP REPORT.
    * ``malformed`` -- the brief cannot be parsed; report it and still write the
                       new URL.
    * ``placeholder`` / ``absent`` -- emit nothing. This is the normal path.

    ``UNKNOWN`` is a **placeholder** here, deliberately unlike
    :func:`read_brief_id`, where an unresolved id must halt. The asymmetry is
    the point: an unresolved *issue id* decides a verdict, an unfilled *pr:*
    does not.
    """
    fields = parse_frontmatter(brief_text)
    if "pr" not in fields:
        return {"kind": "absent", "raw": None}
    raw = fields["pr"]
    if raw in ("none", "None", ""):
        return {"kind": "absent", "raw": raw}
    if raw in ("pending", "<filled by /ship>", "UNKNOWN", "unknown"):
        return {"kind": "placeholder", "raw": raw}

    is_draft = raw.endswith(" (draft)")
    candidate = raw[: -len(" (draft)")] if is_draft else raw
    match = _URL.match(candidate)
    if match:
        reading = {
            "kind": "url", "raw": raw, "url": candidate, "number": int(match.group(1)),
            "briefPrNote": "brief already records pr: %s -- /ship is about to overwrite it. "
                           "Check this is not a stale brief or a double-ship." % candidate,
        }
        if is_draft:
            reading["isDraftSuffix"] = True
        return reading
    return {
        "kind": "malformed", "raw": raw,
        "briefPrNote": "pr: %r is not a recognised spelling; /ship will still write the "
                       "new URL over it." % raw,
    }


def read_brief_partial(brief_text, issue_link_block):
    """True only for an explicit truthy ``partial:``. Absent means False."""
    field = issue_link_block.get("partialField", "partial")
    raw = parse_frontmatter(brief_text).get(field)
    return str(raw).strip().lower() in ("true", "yes", "1") if raw is not None else False


# --------------------------------------------------------------------------
# Body helpers
# --------------------------------------------------------------------------
def normalize_resolved_link(raw):
    """Flatten ONE element of ``closingIssuesReferences`` into a comparison key.

    GitHub's real shape is NESTED and was captured verbatim from
    ``gh pr view <n> --json closingIssuesReferences`` on 2026-08-27. Only the
    owner and repository names below are placeholders; every key and every
    nesting level is exactly what GitHub returned::

        {"id": "I_kwDO...", "number": 35,
         "repository": {"id": "R_kgDO...", "name": "canonical-repo-name",
                        "owner": {"id": "MDQ6...", "login": "some-owner"}},
         "url": "https://github.com/some-owner/canonical-repo-name/issues/35"}

    There is no flat ``owner``/``repo`` pair. An earlier revision of this file
    compared against a hand-invented flat shape; every fixture agreed with it
    and every real PR would have failed, because the suite and the subject
    were wrong in the same direction.
    """
    repository = raw.get("repository") or {}
    return {
        "owner": ((repository.get("owner") or {}).get("login") or "").strip(),
        "repo": (repository.get("name") or "").strip(),
        "number": raw.get("number"),
    }


def same_issue(a, b):
    """Compare two issue coordinates, case-insensitively on owner and repo.

    Case-insensitivity handles only CASING -- GitHub treats owner and repo names
    that way. It does **not** resolve an alias: ``legacyname`` never equals
    ``canonicalname`` in any casing.

    What actually makes the rename safe is that :func:`verify` resolves identity
    from ``gh repo view --json nameWithOwner`` and re-reads a bare ``id:``
    against that canonical name. This repo needs it: the git remote and all 14
    briefs say ``lneninger/legacy-repo-name`` while GitHub reports
    ``lneninger/canonical-repo-name`` and answers the old name only by
    redirect.

    **Known limitation.** That canonical re-read helps bare ids only. An
    explicitly cross-repo ``id:`` spelled with the OLD name -- e.g.
    ``lneninger/legacy-repo-name#39`` -- keeps its literal owner/repo through
    ``_CROSS``, fails ``sameRepo``, and reports ``foreign-closing-ref`` on a
    genuinely linked PR. No brief spells an id that way today (all 14 use a bare
    number, measured 2026-08-27), but every brief's ``repo:`` field carries the
    alias, so it is one copy-paste away. Resolving aliases properly means
    comparing against both the declared and the canonical name.
    """
    if not a or not b:
        return False
    return (a.get("owner", "").lower() == b.get("owner", "").lower()
            and a.get("repo", "").lower() == b.get("repo", "").lower()
            and a.get("number") == b.get("number"))


def render_closing_line(issue_ref, same_repo, issue_link_block):
    """The closing line this work item's PR body should carry."""
    keyword = issue_link_block.get("closingKeyword", "Closes")
    if same_repo:
        return "%s #%d" % (keyword, issue_ref["number"])
    return "%s %s/%s#%d" % (keyword, issue_ref["owner"], issue_ref["repo"], issue_ref["number"])


def body_has_reference(body, keyword, number):
    """Does the body carry ``<keyword> #<number>`` on its own line?

    Anchored per line so ``Refs #12`` cannot satisfy a query for #39 -- the
    discrimination control in test case 13 exists to keep this honest.
    """
    pattern = re.compile(
        r"^\s*%s\s+(?:[A-Za-z0-9._-]+/[A-Za-z0-9._-]+)?#%d\s*$" % (re.escape(keyword), number),
        re.I | re.M,
    )
    return bool(pattern.search(body or ""))


def propose_repaired_body(body, closing_line):
    """Append the closing line. Reachable from ONE verdict only.

    ``absent-repairable`` is the sole row whose action mutates anything, and
    every other verdict must return ``proposedBody: None`` so a caller cannot
    repair a state that a body edit could not fix.
    """
    stripped = (body or "").rstrip("\n")
    return stripped + "\n\n" + closing_line + "\n"


def render_diff(before, after):
    """A minimal unified-style diff, enough for /ship to show the user."""
    import difflib
    return "\n".join(
        difflib.unified_diff(
            (before or "").splitlines(), (after or "").splitlines(),
            fromfile="body (current)", tofile="body (proposed)", lineterm="",
        )
    )


# --------------------------------------------------------------------------
# The ordered decision procedure -- rules 1..16, first match wins.
# --------------------------------------------------------------------------
def evaluate(exp):
    """Map a Link Expectation onto exactly one verdict.

    Closure is by construction: rules 1-4 partition the resolver status and
    the four Id Reading kinds; 5-6 partition issueState; 7 partitions
    prState; 8/9/12 partition the resolved-link relation, and rule 11
    (deferred-close) joins that same partition for the declared,
    non-default-base slice, with 9-10 partitioning ``partial`` inside it;
    13 partitions the structural pair (undeclared-target), and ALSO
    consumes the resolved-link relation a second time for that same
    structural-pair slice -- a cross-repo or undeclared-base input can
    still carry a resolved match, and rule 13's wording branches on it
    without changing the verdict; 14 partitions bodyHasRefsToThisIssue;
    15-16 partition repairAttempted, which is boolean. Every rule consumes
    a field of the tuple and the tuple has no unread field, so the
    fall-through set is empty.
    """
    def out(verdict, reason, **extra):
        result = {
            "verdict": verdict,
            "reason": reason,
            "halt": verdict in HALTING,
            "proposedBody": None,
            "bodyDiff": None,
            "issueRef": exp.get("issueRef"),
        }
        if verdict in ISSUE_LINK_WRITES:
            result["issue_link"] = ISSUE_LINK_WRITES[verdict]
        result.update(extra)
        return result

    # 1 -- resolver unavailable. Fails LOUD (INV-9). Never a body-text fallback.
    if exp.get("resolverCause"):
        cause = exp["resolverCause"]
        return out("unverifiable", "Cannot reach the resolver: %s." % cause,
                   cause=cause, remediation=REMEDIATION.get(cause, ""), exit_code=2)

    kind = (exp.get("idReading") or {}).get("kind")

    # 2 -- malformed id. Never coerced into a number.
    if kind == "malformed":
        return out("malformed-id",
                   "Brief id %r is not a recognised issue reference; refusing to guess."
                   % (exp["idReading"].get("raw"),), exit_code=2)

    # 3 -- unresolved id (D-2). Distinct from absent, on purpose.
    if kind == "unresolved":
        return out("unresolved-id",
                   "Brief id is %r -- unresolved, not absent. Say which issue this is, "
                   "or set id: none." % (exp["idReading"].get("raw"),), exit_code=2)

    # 4 -- deliberately no issue. A success path (INV-6).
    if kind == "absent":
        return out("not-applicable", "Brief records no issue; nothing to link.")

    # 5 -- issue transferred, deleted, or in a repo gh cannot see.
    if exp.get("issueState") == "unreachable":
        return out("issue-unreachable",
                   "Issue #%d is unreachable; a body edit cannot fix that."
                   % exp["issueRef"]["number"], exit_code=2)

    # 6 -- already closed. Two opposite live causes, so ask rather than assume.
    if exp.get("issueState") == "closed":
        return out("issue-already-closed",
                   "Issue #%d is already closed -- either the brief's id is stale, or the "
                   "work shipped without a link (the #6 pathology)."
                   % exp["issueRef"]["number"], exit_code=2)

    # 7 -- BEFORE rule 15. A gh pr edit against a merged PR is a remote
    #      mutation with no effect on the merge that already happened.
    if exp.get("prState") != "open":
        return out("pr-not-open",
                   "PR is %s, not open; refusing to edit it." % exp.get("prState"),
                   exit_code=2)

    relation = exp.get("linkRelation")  # "match" | "mismatch" | "none"

    # 8 -- a resolved link names a DIFFERENT issue.
    if relation == "mismatch":
        return out("foreign-closing-ref",
                   "PR resolves a closing link to %s, but this work item is #%d."
                   % (exp.get("foreignRefs"), exp["issueRef"]["number"]), exit_code=2)

    # 9 -- partial work that nonetheless acquired a closing link.
    if exp.get("partial") and relation == "match":
        return out("unexpected-closing-ref",
                   "Brief marks this partial, but GitHub reports a closing link for #%d. "
                   "Auto-closing half-done work is what the exemption exists to prevent."
                   % exp["issueRef"]["number"], exit_code=2)

    # 10 -- partial work, correctly unlinked.
    if exp.get("partial"):
        return out("exempt-partial",
                   "Brief marks this partial; Refs #%d is correct and no closing link is "
                   "expected." % exp["issueRef"]["number"])

    # 11 -- deferred-close: the reference targets a base this work item
    #       DECLARED, and that base is not the default branch. FACT ONE --
    #       CORRECTED 2026-09-19 (see the contract's "FACT ONE -- CORRECTED"
    #       banner): a closing keyword alone does NOT reliably resolve from
    #       a non-default base -- pull request #173 carried one and never
    #       resolved. The one probe that did resolve also carried a
    #       development link, and a second variable was never isolated, so
    #       neither reading is something to build on. Settled instead:
    #       merging into a non-default base does NOT close the issue, even
    #       when the reference DID resolve; that closure is owned by
    #       /pr-merged once the merge lands, not by this script. So this
    #       rule fires on either reading -- a resolved reference
    #       (relation == "match", which would otherwise reach "linked" at
    #       rule 12) or a body carrying an unresolved closing reference
    #       (bodyHasClosingRefToThisIssue) -- deferred-close is reached
    #       either way. sameRepo and baseIsDeclaredBase are required so the
    #       cross-repo halt and the undeclared-base halt at rule 13 are
    #       never repealed by this rule; not baseIsDefaultBranch is required
    #       so "linked" stays reachable on the default branch; the residue
    #       disjunct's "not bodyHasRefsToThisIssue" term is required so a
    #       body carrying both Refs #N and Closes #N still halts at rule 14
    #       as refs-without-partial.
    if (exp.get("sameRepo") and exp.get("baseIsDeclaredBase")
            and not exp.get("baseIsDefaultBranch")
            and (relation == "match"
                 or (exp.get("bodyHasClosingRefToThisIssue")
                     and not exp.get("bodyHasRefsToThisIssue")))):
        if relation == "match":
            why = ("This PR is based on %r, the base this work item declared but not the "
                   "default branch %r. GitHub resolves the closing reference, but "
                   "merging will not close #%d -- /pr-merged records that closure once the "
                   "merge lands."
                   % (exp.get("baseRefName"), exp.get("defaultBranch"),
                      exp["issueRef"]["number"]))
        else:
            why = ("This PR is based on %r, the base this work item declared but not the "
                   "default branch %r. The body carries a closing reference for #%d that "
                   "GitHub has not resolved, and merging will not close it -- /pr-merged "
                   "records that closure once the merge lands."
                   % (exp.get("baseRefName"), exp.get("defaultBranch"),
                      exp["issueRef"]["number"]))
        return out("deferred-close", why)

    # 12 -- the good case. Gated on baseIsDefaultBranch (unchanged meaning:
    #       baseRefName == defaultBranch) because a resolved reference on a
    #       non-default base does NOT mean the merge will close the issue
    #       (Fact Three, measured 2026-09-19) -- rule 11 above already claims
    #       every declared-non-default-base input that has a resolved match,
    #       so this guard only ever turns away the undeclared-base and
    #       cross-repo residue that rule 13 exists to catch.
    if relation == "match" and exp.get("baseIsDefaultBranch"):
        return out("linked",
                   "GitHub reports a closing link for #%d on this PR."
                   % exp["issueRef"]["number"])

    # 13 -- undeclared target: the closing link's target sits outside what
    #       this work item declared -- a different repository, or a base
    #       branch nobody named -- so nothing here can say whether the link
    #       will fire. Zero repairs; a body edit cannot fix where a PR is
    #       aimed.
    if not exp.get("sameRepo") or not exp.get("baseIsDeclaredBase"):
        if not exp.get("sameRepo"):
            if relation == "match":
                # The guard promoted to `linked` (rule 12) now sends this
                # input here instead: GitHub DID resolve it, so the old
                # unconditional "will not resolve" sentence would be false.
                why = ("GitHub resolved a cross-repo closing reference for #%d, but a "
                       "cross-repo target is outside what this work item declared, so "
                       "nothing here can say what merging it would close."
                       % exp["issueRef"]["number"])
            else:
                # Kept VERBATIM (contract 2026-09-19): not covered by the
                # base-branch probe, so its wording is not touched by that
                # measurement.
                why = "GitHub will not resolve a closing link because the issue reference is cross-repo."
        else:
            # FACT ONE -- CORRECTED 2026-09-19: a closing keyword alone does
            # NOT reliably resolve from a non-default base -- pull request
            # #173 carried one and never resolved, and the one probe that
            # did resolve also carried a development link nobody isolated
            # from the resolution. So this rule can make no claim about
            # whether GitHub will resolve the reference at all; the claim it
            # CAN make is only about what can be VERIFIED once it lands
            # here undeclared or cross-repo.
            declared_base = exp.get("declaredBase")
            default_branch = exp.get("defaultBranch")
            if declared_base == default_branch:
                # No --base-branch was declared, so declaredBase fell back to
                # the default branch (see compute_expectation). Naming both
                # here would read "neither master nor master".
                why = ("This PR is based on %r, which is not the default branch %r, so "
                       "nothing here can say what merging it would close."
                       % (exp.get("baseRefName"), default_branch))
            else:
                why = ("This PR is based on %r, which is neither the default branch %r nor "
                       "the base %r this work item declared, so nothing here can say what "
                       "merging it would close."
                       % (exp.get("baseRefName"), default_branch, declared_base))
        return out("undeclared-target", why, exit_code=2)

    # 14 -- BEFORE rule 15. This is INV-3 / AC-4's enforcement (D-3): a body
    #       already carrying Refs #N for THIS issue can never be repaired into
    #       Closes #N. Rule 15 would otherwise do exactly that.
    if exp.get("bodyHasRefsToThisIssue"):
        return out("refs-without-partial",
                   "PR body carries Refs #%d but the brief does not mark this partial. "
                   "Set partial: true, or remove the Refs line -- I will not rewrite it "
                   "into a closing keyword." % exp["issueRef"]["number"], exit_code=2)

    # 15 -- the one repairable state, and the ONLY row that proposes a body.
    if not exp.get("repairAttempted"):
        closing = render_closing_line(exp["issueRef"], exp.get("sameRepo"),
                                      exp.get("issueLinkBlock") or {})
        proposed = propose_repaired_body(exp.get("body"), closing)
        return out("absent-repairable",
                   "No closing link yet; the body can be repaired with %r." % closing,
                   proposedBody=proposed,
                   bodyDiff=render_diff(exp.get("body"), proposed))

    # 16 -- repaired once already and GitHub still reports nothing.
    return out("still-absent",
               "Repaired once and GitHub still reports no closing link for #%d."
               % exp["issueRef"]["number"], exit_code=2)


# --------------------------------------------------------------------------
# Observation + orchestration
# --------------------------------------------------------------------------
def _gh_json(run_gh, args):
    rc, stdout, stderr = run_gh(args)
    if rc != 0:
        return (None, rc, stderr or "")
    try:
        return (json.loads(stdout or "{}"), 0, "")
    except ValueError:
        return (None, 1, "gh returned output that is not JSON")


def _classify_gh_failure(stderr):
    blob = (stderr or "").lower()
    if "not logged" in blob or "authentication" in blob or "gh auth login" in blob:
        return "gh-unauthenticated"
    if "could not resolve to a pullrequest" in blob or "no pull requests found" in blob:
        return "pr-not-found"
    return "query-failed"


def compute_expectation(brief_text, pr_json, default_branch, repo,
                        issue_link_block, issue_state, repair_attempted,
                        declared_base=None):
    """Build the Link Expectation tuple that ``evaluate`` reads.

    ``declared_base`` is the branch this work item declared it would target
    (``--base-branch``). ``None`` means "the repository default branch" and
    is resolved to ``default_branch`` HERE, inside this function, so there is
    exactly one place the fallback lives (never at a call site).
    ``baseIsDefaultBranch`` keeps its present meaning exactly:
    ``baseRefName == default_branch``. It is NOT redefined by the addition of
    ``declaredBase`` / ``baseIsDeclaredBase``.
    """
    id_reading = read_brief_id(brief_text, issue_link_block, repo)
    resolved_declared_base = declared_base if declared_base is not None else default_branch
    exp = {
        "idReading": id_reading,
        "issueRef": id_reading.get("issueRef"),
        "sameRepo": id_reading.get("sameRepo", False),
        "partial": read_brief_partial(brief_text, issue_link_block),
        "repairAttempted": bool(repair_attempted),
        "issueLinkBlock": issue_link_block,
        "issueState": issue_state,
        "defaultBranch": default_branch,
        "declaredBase": resolved_declared_base,
    }
    if pr_json is not None:
        body = pr_json.get("body") or ""
        exp["body"] = body
        exp["prState"] = (pr_json.get("state") or "").lower()
        exp["baseRefName"] = pr_json.get("baseRefName")
        exp["baseIsDefaultBranch"] = pr_json.get("baseRefName") == default_branch
        exp["baseIsDeclaredBase"] = pr_json.get("baseRefName") == resolved_declared_base
        resolved = [normalize_resolved_link(r)
                    for r in (pr_json.get("closingIssuesReferences") or [])]
        exp["resolvedLinks"] = resolved
        ref = exp["issueRef"]
        if ref:
            matches = [r for r in resolved if same_issue(r, ref)]
            others = [r for r in resolved if not same_issue(r, ref)]
            exp["linkRelation"] = "match" if matches else ("mismatch" if others else "none")
            exp["foreignRefs"] = others or None
            exp["bodyHasRefsToThisIssue"] = body_has_reference(
                body, issue_link_block.get("referenceKeyword", "Refs"), ref["number"])
            # Same helper body_has_reference already uses for Refs -- this
            # adds no new matching logic, only a different keyword/field.
            exp["bodyHasClosingRefToThisIssue"] = body_has_reference(
                body, issue_link_block.get("closingKeyword", "Closes"), ref["number"])
    return exp


def verify(brief_path, pr_number, repo, conventions_path=None,
           run_gh=None, repair_attempted=False, declared_base=None):
    """Answer the question, and never mutate anything answering it (INV-10).

    ``declared_base`` is appended last, keyword-defaulted to ``None``: every
    existing caller of this function is positional, and inserting a
    parameter earlier would silently re-bind ``run_gh`` or
    ``repair_attempted``. ``None`` means "the repository default branch" and
    is resolved inside :func:`compute_expectation`, not here.
    """
    run_gh = run_gh or default_run_gh

    block, cause = read_conventions(conventions_path)
    if cause:
        return evaluate({"resolverCause": cause})

    # A missing DATA FILE fails OPEN (INV-9): no brief means no issue to link.
    path = Path(brief_path)
    if not path.is_absolute() and not path.exists():
        path = work_items_dir() / path.name
    if not path.exists():
        return evaluate({"resolverCause": None, "idReading": {"kind": "absent", "raw": None},
                         "issueLinkBlock": block})
    brief_text = path.read_text(encoding="utf-8")

    # A missing RESOLVER fails LOUD (INV-9).
    rc, _, stderr = run_gh(["--version"])
    if rc != 0:
        blob = (stderr or "").lower()
        cause = "gh-unauthenticated" if ("not logged" in blob or "auth" in blob) else "gh-missing"
        return evaluate({"resolverCause": cause})

    id_reading = read_brief_id(brief_text, block, repo)
    if id_reading["kind"] in ("absent", "malformed", "unresolved"):
        return evaluate({"idReading": id_reading, "issueLinkBlock": block})

    # Repo IDENTITY comes from gh, never from the brief's repo: string. This
    # repo was renamed: the git remote and every brief still say
    # "legacy-repo-name" while GitHub reports "canonical-repo-name"
    # and answers the old name only by redirect. Comparing the brief's string
    # against a resolved link would call every genuine link foreign.
    repo_json, rc, stderr = _gh_json(
        run_gh, ["repo", "view", "--json", "nameWithOwner,defaultBranchRef"])
    if repo_json is None:
        # INV-9: a resolver failure fails LOUD. There is deliberately NO
        # fallback here. Falling back to the caller's repo string and a
        # hardcoded "master" produced `foreign-closing-ref` on correctly-linked
        # work -- and still let the single `gh pr edit` fire on information the
        # script already knew was degraded.
        return evaluate({"resolverCause": _classify_gh_failure(stderr)})
    default_branch = (repo_json.get("defaultBranchRef") or {}).get("name")
    canonical_repo = repo_json.get("nameWithOwner")
    if not default_branch or not canonical_repo:
        return evaluate({"resolverCause": "query-failed"})
    if canonical_repo != repo:
        # Re-read the id so a bare "#39" resolves against the CANONICAL repo.
        id_reading = read_brief_id(brief_text, block, canonical_repo)
    repo = canonical_repo

    pr_json, rc, stderr = _gh_json(
        run_gh,
        ["pr", "view", str(pr_number), "--json",
         "closingIssuesReferences,baseRefName,state,body"],
    )
    if pr_json is None:
        return evaluate({"resolverCause": _classify_gh_failure(stderr)})

    ref = id_reading["issueRef"]
    issue_args = ["issue", "view", str(ref["number"]), "--json", "state"]
    if not id_reading.get("sameRepo"):
        issue_args += ["--repo", "%s/%s" % (ref["owner"], ref["repo"])]
    issue_json, rc, stderr = _gh_json(run_gh, issue_args)
    if issue_json is None:
        # Distinguish a TRANSPORT failure from a genuine "no such issue". Both
        # halt, but conflating them tells a user with a flaky network that their
        # issue was transferred or deleted, and offers the wrong remediation.
        blob = (stderr or "").lower()
        if "could not resolve" in blob or "not found" in blob:
            issue_state = "unreachable"
        else:
            return evaluate({"resolverCause": _classify_gh_failure(stderr)})
    else:
        issue_state = (issue_json.get("state") or "unreachable").lower()

    exp = compute_expectation(
        brief_text, pr_json, default_branch, repo, block, issue_state, repair_attempted,
        declared_base)
    result = evaluate(exp)

    # Bookkeeping only -- the brief's pr: decides no verdict (/ship passes the
    # number it just created via --pr). Its one job is honesty in the report:
    # `url` means Step 5 is about to OVERWRITE a URL already recorded, which is
    # a stale-brief or double-ship signal; `malformed` means the brief could not
    # be parsed. placeholder and absent say nothing.
    note = read_brief_pr(brief_text).get("briefPrNote")
    if note:
        result["briefPrNote"] = note
    return result


def _default_repo_seed():
    """Best-effort ``owner/repo`` from the origin remote, for the --repo seed.

    Never authoritative: :func:`verify` overrides it with the canonical name
    from ``gh repo view``. Returns the literal ``"owner/repo"`` when no remote
    can be read, which keeps :func:`read_brief_id`'s ``partition("/")`` well
    formed and matches nothing, so a bare id still resolves through the
    canonical re-read and a cross-repo id still reports as foreign.
    """
    try:
        out = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=10)
    except Exception:
        return "owner/repo"
    url = (out.stdout or "").strip()
    if out.returncode != 0 or not url:
        return "owner/repo"
    if url.endswith(".git"):
        url = url[:-4]
    url = url.rstrip("/")
    parts = url.replace(":", "/").split("/")
    if len(parts) >= 2 and parts[-1] and parts[-2]:
        return "%s/%s" % (parts[-2], parts[-1])
    return "owner/repo"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Verify that GitHub reports a Closing Link for a PR and its work item.")
    parser.add_argument("--brief", required=True,
                        help="Work Item Brief path; resolved via work_items_dir() when relative.")
    parser.add_argument("--pr", required=True, type=int, help="Pull request number.")
    # SEED ONLY, never identity. verify() re-reads the canonical owner/repo from
    # `gh repo view --json nameWithOwner` and overrides whatever arrives here
    # (see the block above the _gh_json call), so a stale or wrong seed
    # self-corrects on every path where gh answers -- and where gh does not
    # answer, the run is `unverifiable` regardless. Hardcoding one project's
    # slug here would therefore buy nothing and would pin a generic script to
    # one repository, so the default is read from the git remote instead.
    parser.add_argument(
        "--repo", default=_default_repo_seed(),
        help="owner/repo seed used to read a bare id: before gh reports the "
             "canonical name. Defaults to the origin remote.")
    parser.add_argument("--repair-attempted", action="store_true",
                        help="Set on the re-query after /ship's single repair (INV-2).")
    parser.add_argument(
        "--base-branch", default=None,
        help="The branch this work item declared it would target. Defaults to the "
             "repository default branch when omitted.")
    parser.add_argument("--json", action="store_true", help="Emit the full verdict as JSON.")
    args = parser.parse_args(argv)

    result = verify(brief_path=args.brief, pr_number=args.pr, repo=args.repo,
                    repair_attempted=args.repair_attempted, declared_base=args.base_branch)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("verdict: %s" % result["verdict"])
        if result.get("cause"):
            print("cause:   %s" % result["cause"])
        print("reason:  %s" % result.get("reason", ""))
        if result.get("issue_link"):
            print("issue_link: %s" % result["issue_link"])
        if result.get("remediation"):
            print("remediation: %s" % result["remediation"])
        if result.get("bodyDiff"):
            print("")
            print(result["bodyDiff"])
    return int(result.get("exit_code", 0))


if __name__ == "__main__":
    sys.exit(main())
