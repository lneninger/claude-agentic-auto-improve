#!/usr/bin/env python3
"""
protected_names_check.py -- the command line of the Protected-name check.

    protected_names_check.py --project <dir> [--working-ref <git ref> | disk] [--default-ref <git ref>] [--fetch]

It compares the ``protected_databases`` strings of a working copy of the project's database-guard rules
file (``.claude/hooks/db-destructive-guard.rules.json``) with the same file at the tip of the default
branch. The logic lives in ``../hooks/_protected_names.py``; read its docstring for the verdicts.

  --working-ref  a commit whose COMMITTED rules file is the working side (read with git, never the disk);
                 ``disk`` (the default) reads the working copy.
  --default-ref  a commit for the default-branch side; by default the detected ``origin/<default>``.
  --fetch        first run an explicit-destination ``git fetch`` of the default branch and compare the ref with
                 ``git ls-remote`` (20 seconds each). Refused together with ``--default-ref``. If the fetch
                 fails, or leaves the ref different from what the remote advertises, the local ref is used
                 and ``fetched`` is false.

THE RESULT
----------
Standard output holds exactly ONE JSON object: ``verdict``, ``missing`` (the strings), ``working_ref``,
``default_ref`` (a commit id), ``fetched``, ``reason``. Human-readable text goes to standard error.

Exit codes: 0 ``kept`` or ``first-install``; 10 ``names-removed``; 11 ``working-malformed`` or
``reference-malformed``; 12 ``unverifiable``. They never collide with Python's own exit 1 (an uncaught
exception or an import failure) or exit 2 (a usage error). A catch-all prints an ``unverifiable`` result
and exits 12.

SELF-CONTAINED: standard library only. It imports every standard-library module first, then puts this file's
folder at the front of ``sys.path`` and appends a sibling ``hooks`` folder at the END, only when its own
folder holds no ``_protected_names.py``; so it runs the same in the plugin layout, in a consuming
repository's layout and in one folder holding both files, also under ``-I``.
"""
# Every standard-library module this file or its helper uses is imported BEFORE sys.path is edited, so no
# file beside or above this one can stand in for one of them (contract 2026-10-13, Commands, Import order).
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path  # noqa: F401 -- imported for the helper

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
# A sibling ``../hooks`` folder is a fallback, appended LAST and only when this folder holds no helper.
if not os.path.isfile(os.path.join(_HERE, "_protected_names.py")):
    _SIBLING_HOOKS = os.path.join(os.path.dirname(_HERE), "hooks")
    if os.path.isdir(_SIBLING_HOOKS):
        sys.path.append(_SIBLING_HOOKS)

# An import failure (a missing or broken helper) is an uncaught exception: Python's own exit 1, never a verdict.
import _protected_names  # noqa: E402

UNVERIFIABLE_CODE = 12


def _emit(result):
    sys.stdout.write(json.dumps(result) + "\n")
    sys.stdout.flush()


def _unverifiable(reason):
    return {"verdict": "unverifiable", "missing": [], "working_ref": "", "default_ref": "",
            "fetched": None, "reason": reason}


def _parser():
    parser = argparse.ArgumentParser(prog="protected_names_check.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--project", required=True, help="the project (git working tree) to check")
    parser.add_argument("--working-ref", default="disk",
                        help="a git ref whose committed rules file is the working side; 'disk' reads the file")
    parser.add_argument("--default-ref", default=None, help="a git ref for the default-branch side")
    parser.add_argument("--fetch", action="store_true", help="fetch the default branch first (20 seconds)")
    return parser


def _say(result, project):
    """The human-readable text, on standard error."""
    verdict = result["verdict"]
    lines = []
    if verdict == "names-removed":
        lines.append("protected-name check: %d protected database name(s) of the default branch are missing "
                     "from %s: %s" % (len(result["missing"]), project, ", ".join(repr(n) for n in result["missing"])))
        lines.append("only a person removes a protected database name: change only the rules file in its own "
                     "pull request and merge it by hand.")
    elif verdict in ("working-malformed", "reference-malformed"):
        lines.append("protected-name check: %s: %s" % (verdict, result["reason"]))
    elif verdict == "unverifiable":
        lines.append("protected-name check: unverifiable: %s" % result["reason"])
    else:
        lines.append("protected-name check: %s" % verdict)
    if result.get("fetched") is False:
        when = result.get("default_date") or "an unknown date"
        lines.append("the fetch failed, so the local default-branch ref was used (its commit is dated %s)." % when)
    sys.stderr.write("\n".join(lines) + "\n")


def main(argv=None):
    args = _parser().parse_args(argv)  # a usage error exits 2, as argparse does
    if args.fetch and args.default_ref is not None:
        _parser().error("--fetch cannot be combined with --default-ref (an explicit commit is never fetched)")
    try:
        working_ref = None if args.working_ref in (None, "", "disk") else args.working_ref
        result = _protected_names.check(args.project, working_ref=working_ref, default_ref=args.default_ref,
                                        fetch=args.fetch)
        _emit({key: result[key] for key in ("verdict", "missing", "working_ref", "default_ref", "fetched",
                                            "reason")})
        try:
            _say(result, args.project)
        except Exception:  # noqa: BLE001 -- the prose never changes the verdict
            pass
        return _protected_names.EXIT_CODES.get(result["verdict"], UNVERIFIABLE_CODE)
    except Exception as exc:  # noqa: BLE001 -- a crash must never look like a verdict
        try:
            _emit(_unverifiable("the check failed: %r" % (exc,)))
            sys.stderr.write("protected-name check: unverifiable: %r\n" % (exc,))
        except Exception:  # noqa: BLE001
            pass
        return UNVERIFIABLE_CODE


if __name__ == "__main__":
    sys.exit(main())
