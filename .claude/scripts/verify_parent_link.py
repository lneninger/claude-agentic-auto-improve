#!/usr/bin/env python3
"""
verify_parent_link.py -- does GitHub actually record this sub-issue's parent?

Callers
-------
  * ``/task`` parent-aware mode -- the only production caller. After
    ``gh issue create --parent <n>``, it shells out to this script and
    branches on ``verdict``. On ``no-parent`` it performs at most ONE
    ``gh issue edit <sub> --parent <parent>`` (the one repair this module
    never performs itself), then re-invokes with the same arguments.
  * ``.claude/scripts/tests/test_verify_parent_link.py`` -- injects ``run_gh``.

CLI
---
    py -3 .claude/scripts/verify_parent_link.py --sub <n> --parent <n> [--json]

Contract: .claude/concepts/2026-09-19-flow-parent-subissue-topology.md
(work item #164, sub-task 2).

WHY THIS EXISTS
---------------
Attaching a sub-issue to a parent with ``gh issue create --parent <n>`` is a
REQUEST, not a fact: the command can exit 0 while the link never took. The
repository already carries this doctrine for Closing Links
(``verify_issue_link.py``, contract 2026-08-27, work item #39) -- a keyword
in a body is a request and only GitHub's resolved reference counts. This
module is the same doctrine applied to a different edge: the sub-issue-to-
parent relation, read back with

    gh issue view <sub> --json parent

This is a NEW INSTANCE of the mechanism ``Closing-link verification as an
obligation, not an assertion`` (``.claude/registries/MECHANISMS.md:113``),
not a new mechanism -- its own "Extend by" clause names exactly this
sibling-script shape for a *different* question, rather than a further
verdict bolted onto the existing script.

INVARIANTS THIS FILE OWNS
--------------------------
INV-1  Only GitHub's own read-back proves a link. Never the create command's
       exit code.
INV-9  A missing or unreadable conventions block fails LOUD (``unverifiable``,
       cause ``conventions-missing``), never a quiet pass and never a
       hard-coded fallback vocabulary.
INV-10 This module performs NO mutation of any GitHub object. Its only route
       to a subprocess is ``run_gh``; the one repair belongs to the ``/task``
       skill, never to this script.

THE ORDER IS THE ENFORCEMENT
-----------------------------
``evaluate`` implements four rules, first match wins. ``unverifiable`` is
first because a resolver that cannot be reached must never be read as an
answer. The rule for a mismatched parent sits before the good case so a
wrong parent can never fall through to a pass -- the good case is reached
only by falling through every halting rule, not by an early exit. There is
deliberately no fifth verdict for "the parent does not list the child back":
GitHub's sub-issue relation is a single edge, so both directions derive from
the same read and such a verdict would be unreachable in this script (the
parent-side roll-up is a separate, run-level concern owned by the caller).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _claude_paths import work_item_conventions_path  # noqa: E402


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
# Vocabulary source. The verdict names and the read-back command live in
# work-item-conventions.json -> issueLink.parentLink, written once by
# sub-task 3 -- this module restates neither, and a test asserts the
# agreement rather than the script re-deriving the closed set from the file
# at every call (the same discipline verify_issue_link.py's own hard-coded
# VERDICTS carries, enforced there by an equivalent equality test).
# --------------------------------------------------------------------------
def read_conventions(conventions_path=None):
    """Load the ``issueLink.parentLink`` block.

    Returns ``(block, cause)``. ``cause`` is ``conventions-missing`` when the
    file is absent or unreadable, when it carries no outer ``issueLink``
    block, or when that block carries no nested ``parentLink`` block --
    INV-9's failure state, which fails LOUD rather than defaulting to a
    hard-coded keyword.

    ``maxRepairAttempts`` is deliberately read from the OUTER ``issueLink``
    block, never from the nested ``parentLink`` block -- sub-task 3's own
    ``$comment`` in the conventions file says this explicitly, because that
    constant is the single source of truth for both the Closing Link and the
    Parent Link. A value planted on the nested block must never win.
    """
    path = Path(conventions_path) if conventions_path else work_item_conventions_path()
    if not path.exists():
        return (None, "conventions-missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return (None, "conventions-missing")
    outer = payload.get("issueLink")
    if not isinstance(outer, dict) or not outer:
        return (None, "conventions-missing")
    nested = outer.get("parentLink")
    if not isinstance(nested, dict) or not nested:
        return (None, "conventions-missing")
    block = dict(nested)
    block["maxRepairAttempts"] = outer.get("maxRepairAttempts")
    return (block, None)


def _classify_gh_failure(stderr):
    blob = (stderr or "").lower()
    if "not logged" in blob or "authentication" in blob or "gh auth login" in blob:
        return "gh-unauthenticated"
    return "query-failed"


def _read_back_argv(block, sub_issue):
    """Build the read-back ``gh`` argv FROM the conventions block's
    ``readCommand`` template (e.g. ``"gh issue view <sub> --json parent"``),
    rather than restating a literal argv in this module -- the same
    single-source-of-truth discipline ``read_conventions`` already applies
    to the verdict vocabulary. Substitutes ``<sub>`` with the real sub-issue
    number and drops the leading ``"gh"`` token, since ``run_gh`` already
    supplies it.

    Falls back to the known-good literal shape when the template is absent
    or does not parse into a usable command -- a malformed template must
    degrade the read-back, never crash it.
    """
    default = ["issue", "view", str(sub_issue), "--json", "parent"]
    template = (block or {}).get("readCommand")
    if not isinstance(template, str) or not template.strip():
        return default
    parts = template.replace("<sub>", str(sub_issue)).split()
    if parts and parts[0] == "gh":
        parts = parts[1:]
    return parts or default


# --------------------------------------------------------------------------
# The ordered decision procedure -- four rules, first match wins.
# --------------------------------------------------------------------------
def evaluate(exp):
    """Map a Parent Link Expectation onto exactly one of four verdicts.

    ``exp`` carries ``subIssue``, ``expectedParent``, ``reportedParent |
    null``, ``repairAttempted`` and ``resolverCause | null`` (the contract's
    Data Shapes -> Value Objects table).

    CLOSURE: rule 1 reads ``resolverCause``; rules 2-4 read ``reportedParent``
    and ``expectedParent``; ``subIssue`` is read in the reason text of rules
    2-4. ``repairAttempted`` is read by ``out()`` on every rule -- echoed on
    the returned verdict rather than consulted by any rule, because this
    four-verdict script (unlike the sixteen-verdict sibling
    ``verify_issue_link.py``, whose rules 14-15 DO partition it) has no
    verdict whose meaning depends on whether a repair was already attempted;
    the caller owns that budget, not this script. Every field of the tuple
    is read somewhere in this function, so the fall-through set is empty.
    """

    def out(verdict, reason, **extra):
        result = {
            "verdict": verdict,
            "reason": reason,
            "halt": verdict in HALTING,
            "repairAttempted": exp.get("repairAttempted"),
        }
        result.update(extra)
        return result

    # 1 -- resolver unavailable. Fails LOUD. Never a fallthrough pass.
    if exp.get("resolverCause"):
        cause = exp["resolverCause"]
        return out(
            "unverifiable",
            "Cannot reach the resolver: %s." % cause,
            cause=cause,
            remediation=REMEDIATION.get(cause, ""),
        )

    reported = exp.get("reportedParent")
    expected = exp.get("expectedParent")

    # 2 -- no parent reported at all (the measured gh shape for an unlinked
    #      sub-issue: {"parent": null}).
    if reported is None:
        return out(
            "no-parent",
            "Sub-issue #%s reports no parent." % exp.get("subIssue"),
        )

    # 3 -- a parent that names a DIFFERENT issue. Halts before the good case
    #      so a wrong parent can never be read as a pass. Never re-parented
    #      automatically -- that is a destructive tracker mutation with no
    #      undo, and it belongs to the caller, not this script.
    if reported != expected:
        return out(
            "foreign-parent",
            "Sub-issue #%s reports parent #%s, but the expected parent is #%s."
            % (exp.get("subIssue"), reported, expected),
        )

    # 4 -- the good case. Reached only by falling through both halting rules
    #      above, never by an early exit.
    return out(
        "linked",
        "Sub-issue #%s reports parent #%s, as expected." % (exp.get("subIssue"), expected),
    )


# --------------------------------------------------------------------------
# Closed sets. VERDICTS is asserted verbatim, in order, against the real
# work-item-conventions.json -> issueLink.parentLink.verdicts by this
# module's own test suite -- the same discipline verify_issue_link.py's
# hard-coded VERDICTS carries against issueLink.verdicts.
# --------------------------------------------------------------------------
VERDICTS = ["unverifiable", "no-parent", "foreign-parent", "linked"]

HALTING = frozenset({"unverifiable", "no-parent", "foreign-parent"})

# Causes reused verbatim from verify_issue_link.py's own unverifiableCauses
# vocabulary -- the nested parentLink block declares no causes array of its
# own, so there is nothing else to read them from. "conventions-missing" is
# the one cause this contract states literally.
UNVERIFIABLE_CAUSES = ["gh-missing", "gh-unauthenticated", "query-failed", "conventions-missing"]

REMEDIATION = {
    "gh-missing": "winget install --id GitHub.cli, then gh auth login.",
    "gh-unauthenticated": "Run gh auth login and retry.",
    "query-failed": "Retry; if it persists, run the parentLink.readCommand by hand and paste the output.",
    "conventions-missing": (
        "Add the issueLink.parentLink block to work-item-conventions.json "
        "(see the contract's Extension Points)."
    ),
}


# --------------------------------------------------------------------------
# The impure driver -- reads conventions, calls gh through the injectable
# seam, and hands the result to evaluate(). Never mutates anything (INV-10).
# --------------------------------------------------------------------------
def verify(sub_issue, expected_parent, conventions_path=None, run_gh=None, repair_attempted=False):
    """Answer "does GitHub report the expected parent for this sub-issue?"

    Reads the resolver's own answer through ``gh issue view <sub> --json
    parent`` and maps it onto exactly one of the four declared verdicts.
    Never issues ``gh issue edit`` or any other mutating command -- the one
    repair belongs to the ``/task`` skill, never to this script.
    """
    run_gh = run_gh or default_run_gh

    def halted(cause):
        return evaluate({
            "subIssue": sub_issue,
            "expectedParent": expected_parent,
            "repairAttempted": repair_attempted,
            "resolverCause": cause,
        })

    # A missing or unreadable conventions block fails LOUD (INV-9). Never a
    # quiet pass and never a hard-coded fallback vocabulary.
    block, cause = read_conventions(conventions_path)
    if cause:
        return halted(cause)

    # A missing RESOLVER fails LOUD (INV-9).
    rc, _, stderr = run_gh(["--version"])
    if rc != 0:
        blob = (stderr or "").lower()
        gh_cause = "gh-unauthenticated" if ("not logged" in blob or "auth" in blob) else "gh-missing"
        return halted(gh_cause)

    rc, stdout, stderr = run_gh(_read_back_argv(block, sub_issue))
    if rc != 0:
        return halted(_classify_gh_failure(stderr))
    try:
        payload = json.loads(stdout or "{}")
    except ValueError:
        return halted("query-failed")

    # CRITICAL-2: a well-formed JSON document whose TOP LEVEL is not an
    # object (e.g. `null`, a bare list) must never reach a dict method call.
    # CRITICAL-1: a payload with no "parent" KEY at all (as opposed to a
    # "parent" key present and explicitly null -- the real gh shape for an
    # unlinked sub-issue) is not a shape this resolver has ever produced;
    # both fail LOUD as unverifiable rather than being silently read as
    # "no parent", which is the verdict that triggers an automatic re-parent
    # one layer up in the /task caller.
    if not isinstance(payload, dict) or "parent" not in payload:
        return halted("query-failed")

    parent = payload["parent"]
    if parent is None:
        # The measured gh shape for an unlinked sub-issue: {"parent": null}.
        reported_parent = None
    elif isinstance(parent, dict) and isinstance(parent.get("number"), int):
        reported_parent = parent["number"]
    else:
        # CRITICAL-1: neither the expected null nor a dict carrying an
        # integer "number" -- a dict with no "number", a bare integer, or
        # any other shape. Never collapses to "no-parent".
        return halted("query-failed")

    return evaluate({
        "subIssue": sub_issue,
        "expectedParent": expected_parent,
        "reportedParent": reported_parent,
        "repairAttempted": repair_attempted,
        "resolverCause": None,
    })


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Verify that GitHub reports the expected parent for a sub-issue.")
    parser.add_argument("--sub", required=True, type=int, help="Sub-issue number.")
    parser.add_argument("--parent", required=True, type=int, help="Expected parent issue number.")
    parser.add_argument("--repair-attempted", action="store_true",
                        help="Set on the re-query after /task's single repair.")
    parser.add_argument("--json", action="store_true", help="Emit the full verdict as JSON.")
    args = parser.parse_args(argv)

    result = verify(args.sub, args.parent, repair_attempted=args.repair_attempted)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("verdict: %s" % result["verdict"])
        if result.get("cause"):
            print("cause:   %s" % result["cause"])
        print("reason:  %s" % result.get("reason", ""))
        if result.get("remediation"):
            print("remediation: %s" % result["remediation"])
    return 2 if result.get("halt") else 0


if __name__ == "__main__":
    sys.exit(main())
