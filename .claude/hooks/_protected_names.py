#!/usr/bin/env python3
"""
_protected_names.py -- the Protected-name check (helper; never registered as a hook).

WHAT IT IS
----------
The database guard (``db-destructive-guard.py``) refuses destructive or writing commands aimed at the
databases listed under ``protected_databases`` in the project's rules file,
``.claude/hooks/db-destructive-guard.rules.json``. That file is an ordinary file, so the safety rests on
an OUTCOME check: the names in a working copy of the file must include every name the same file holds at
the tip of the default branch (the default-branch list). A removed name, a respelled name, an added space
and a letter-case change all fail. Only a person shortens the list, by merging a pull request by hand.

This module holds the logic. ``../scripts/protected_names_check.py`` is the command line; the turn-end
warning (``protected-names-warning.py``) imports it too.

THE VERDICT (a closed set, decided in this order, first match wins)
-------------------------------------------------------------------
  1. ``unverifiable``       no remote named ``origin``, or no default branch, or a git call fails or runs
                            past its limit, or the listing of the default-branch commit fails.
  2. ``first-install``      the listing of that commit succeeds and does not hold the rules file, and the
                            working reading is absent or parsed. Passes.
  3. ``reference-malformed`` the default-branch reading is malformed.
  4. ``working-malformed``  the working reading is malformed, or the working file is absent while the
                            default-branch list is not empty.
  5. ``names-removed``      some default-branch string is not, as an exact string, among the working strings.
  6. ``kept``               every default-branch string is present. Passes.

A names reading is parsed as follows: the bytes decoded as strict UTF-8; a leading byte order mark is
malformed (the guard's own loader cannot read it); JSON with a duplicate key ANYWHERE rejected; the top
level must be an object; ``protected_databases`` absent counts as an empty list; present, it must be a list
of strings. No string is trimmed, case-folded, normalised or skipped (blank strings included).

NO EXEMPTION reads the tree under check: the plugin's own checkout is compared like any other.

STANDARD LIBRARY ONLY. It imports no path-bridge helper of this plugin: the landing gate runs it from a
folder that holds nothing else but its command line. Git runs through ``subprocess`` with a 5-second limit per call;
the only network call is the explicit ``git fetch`` a caller asks for (20 seconds).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

#: The rules file, relative to a project root, with forward slashes (a git path).
RULES_REL = ".claude/hooks/db-destructive-guard.rules.json"

#: The key that holds the protected names.
NAMES_KEY = "protected_databases"

#: The closed set of verdicts.
VERDICTS = ("kept", "first-install", "names-removed", "working-malformed", "reference-malformed",
            "unverifiable")

#: Verdict -> exit code of the command line. Never 1 or 2 (Python's own crash and usage codes).
EXIT_CODES = {
    "kept": 0, "first-install": 0,
    "names-removed": 10,
    "working-malformed": 11, "reference-malformed": 11,
    "unverifiable": 12,
}

#: Seconds each git call may take, and the one explicit fetch.
GIT_TIMEOUT = 5
FETCH_TIMEOUT = 20

#: The default-branch refs tried after ``refs/remotes/origin/HEAD``, in this order.
FALLBACK_DEFAULT_REFS = ("refs/remotes/origin/master", "refs/remotes/origin/main")


class GitFailure(Exception):
    """A git call failed, could not start, or ran past its limit."""


# ---------------------------------------------------------------------------
# Names reading
# ---------------------------------------------------------------------------
def _reject_duplicate_keys(pairs):
    seen = set()
    for key, _value in pairs:
        if key in seen:
            raise ValueError("duplicate key %r" % (key,))
        seen.add(key)
    return dict(pairs)


def read_names(data):
    """Parse the bytes of a rules file (or ``None`` for an absent file) into a Names reading.

    Returns ``{"state": "absent" | "parsed" | "malformed", "names": [str, ...], "reason": str}``.
    """
    if data is None:
        return {"state": "absent", "names": [], "reason": "the file is absent"}
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return {"state": "malformed", "names": [], "reason": "not valid UTF-8: %s" % exc}
    if text.startswith("﻿"):
        return {"state": "malformed", "names": [],
                "reason": "a byte order mark begins the file (the guard cannot read it)"}
    try:
        parsed = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except Exception as exc:  # noqa: BLE001 -- any parse problem is "malformed"
        return {"state": "malformed", "names": [], "reason": "not valid JSON: %s" % exc}
    if not isinstance(parsed, dict):
        return {"state": "malformed", "names": [], "reason": "the top level is not an object"}
    if NAMES_KEY not in parsed:
        return {"state": "parsed", "names": [], "reason": ""}
    value = parsed[NAMES_KEY]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return {"state": "malformed", "names": [],
                "reason": "%s is not a list of strings" % NAMES_KEY}
    return {"state": "parsed", "names": list(value), "reason": ""}


# ---------------------------------------------------------------------------
# git
# ---------------------------------------------------------------------------
def _git_env():
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git(project, args, timeout=GIT_TIMEOUT):
    """Run ``git <args>`` in ``project``. Returns ``(returncode, stdout_bytes)``.

    Raises ``GitFailure`` when git cannot start or runs past its limit; a non-zero code is returned."""
    try:
        proc = subprocess.run(["git"] + list(args), cwd=str(project), capture_output=True,
                              timeout=timeout, env=_git_env(), stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired as exc:
        raise GitFailure("git %s ran past %d seconds" % (" ".join(args[:2]), timeout)) from exc
    except (OSError, ValueError) as exc:
        raise GitFailure("git could not run: %s" % exc) from exc
    return proc.returncode, proc.stdout


def _git_text(project, args, timeout=GIT_TIMEOUT):
    code, out = git(project, args, timeout)
    return code, out.decode("utf-8", errors="replace").strip()


def has_origin(project):
    """True when a remote named ``origin`` exists. Raises ``GitFailure`` when git cannot say."""
    code, out = _git_text(project, ["remote"])
    if code != 0:
        raise GitFailure("git remote failed (exit %d): not a repository?" % code)
    return "origin" in out.split()


def resolve_commit(project, ref):
    """The commit id ``ref`` names, or ``None`` when it names none."""
    code, out = _git_text(project, ["rev-parse", "--verify", "-q", "%s^{commit}" % ref])
    return out if code == 0 and out else None


def default_branch_ref(project):
    """``(branch_name, full_ref)`` of the default branch: ``refs/remotes/origin/HEAD`` first, then an
    ``origin/master`` or ``origin/main`` ref. ``None`` when there is none (no blind fallback)."""
    candidates = []
    code, out = _git_text(project, ["symbolic-ref", "-q", "refs/remotes/origin/HEAD"])
    if code == 0 and out.startswith("refs/remotes/origin/"):
        candidates.append(out)
    candidates.extend(FALLBACK_DEFAULT_REFS)
    for ref in candidates:
        if resolve_commit(project, ref):
            return ref[len("refs/remotes/origin/"):], ref
    return None


def _branch_name_only(project):
    """The default branch's name even when its remote-tracking ref is missing (for a fetch), else None."""
    code, out = _git_text(project, ["symbolic-ref", "-q", "refs/remotes/origin/HEAD"])
    if code == 0 and out.startswith("refs/remotes/origin/"):
        return out[len("refs/remotes/origin/"):]
    return None


def read_blob(project, commit, rel_path):
    """``(listed, data)``: whether ``commit`` holds ``rel_path`` and its bytes. Raises ``GitFailure`` when
    the listing of the commit fails."""
    code, out = git(project, ["ls-tree", "-z", "--full-tree", commit, "--", rel_path])
    if code != 0:
        raise GitFailure("git ls-tree failed for %s (exit %d)" % (commit, code))
    if not out.strip(b"\0"):
        return False, None
    code, blob = git(project, ["cat-file", "blob", "%s:%s" % (commit, rel_path)])
    if code != 0:
        raise GitFailure("git cat-file failed for %s:%s (exit %d)" % (commit, rel_path, code))
    return True, blob


def commit_date(project, commit):
    code, out = _git_text(project, ["show", "-s", "--format=%cI", commit])
    return out if code == 0 else ""


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------
def _result(verdict, reason, reason_code="", missing=None, working_ref="", default_ref="", fetched=None,
            default_branch="", default_date=""):
    return {
        "verdict": verdict,
        "missing": list(missing or []),
        "working_ref": working_ref,
        "default_ref": default_ref,
        "fetched": fetched,
        "reason": reason,
        "reason_code": reason_code,
        "default_branch": default_branch,
        "default_date": default_date,
    }


def _read_working_disk(project):
    path = Path(project) / Path(*RULES_REL.split("/"))
    try:
        if not path.exists():
            return None
        if not path.is_file():
            return b"\xff"  # not a file: reads as malformed (a folder where the rules file should be)
        return path.read_bytes()
    except OSError:
        return b"\xff"


def check(project, working_ref=None, default_ref=None, fetch=False, rules_rel=RULES_REL):
    """Run one Protected-name check of ``project``. Returns the result dict (see ``_result``).

    ``working_ref``  None reads the working copy from disk; a git ref reads the committed file at it.
    ``default_ref``  None detects ``origin``'s default branch; a git ref names the commit for that side.
    ``fetch``        run one ``git fetch`` of the default branch first (refused with ``default_ref``).
    Never raises: anything unexpected is ``unverifiable``."""
    try:
        return _check(project, working_ref, default_ref, fetch, rules_rel)
    except GitFailure as exc:
        return _result("unverifiable", str(exc), "git-failed")
    except Exception as exc:  # noqa: BLE001 -- the contract: an unreadable run is unverifiable
        return _result("unverifiable", "unexpected error: %r" % (exc,), "error")


def _check(project, working_ref, default_ref, fetch, rules_rel):
    working_label = "disk" if working_ref is None else working_ref
    fetched = None
    default_branch = ""
    default_commit = None

    if default_ref is None:
        if not has_origin(project):
            return _result("unverifiable", "no remote named origin", "no-origin", working_ref=working_label)
        if fetch:
            branch = (default_branch_ref(project) or (None, None))[0] or _branch_name_only(project)
            args = ["fetch", "--quiet", "origin"]
            if branch:
                args.append("+refs/heads/%s:refs/remotes/origin/%s" % (branch, branch))
            try:
                code, _out = git(project, args, FETCH_TIMEOUT)
            except GitFailure:
                code = 1
            fetched = code == 0
        found = default_branch_ref(project)
        if found is None:
            return _result("unverifiable", "origin has no default branch ref (no origin/HEAD, origin/master "
                           "or origin/main)", "no-default-ref", working_ref=working_label, fetched=fetched)
        default_branch, full_ref = found
        default_commit = resolve_commit(project, full_ref)
    else:
        default_commit = resolve_commit(project, default_ref)
        if default_commit is None:
            return _result("unverifiable", "the default ref %r cannot be resolved" % default_ref,
                           "bad-default-ref", working_ref=working_label, default_ref=default_ref)

    working_commit = None
    if working_ref is not None:
        working_commit = resolve_commit(project, working_ref)
        if working_commit is None:
            return _result("unverifiable", "the working ref %r cannot be resolved" % working_ref,
                           "bad-working-ref", working_ref=working_ref, default_ref=default_commit)
        working_label = working_commit

    default_date = commit_date(project, default_commit) if fetched is False else ""

    def done(verdict, reason="", missing=None, code=""):
        return _result(verdict, reason, code, missing, working_label, default_commit, fetched,
                       default_branch, default_date)

    listed, default_bytes = read_blob(project, default_commit, rules_rel)  # may raise GitFailure
    if working_commit is not None:
        _wl, working_bytes = read_blob(project, working_commit, rules_rel)
    else:
        working_bytes = _read_working_disk(project)
    working = read_names(working_bytes)

    if not listed:
        if working["state"] in ("absent", "parsed"):
            return done("first-install", "the default branch holds no rules file yet")
        default = {"state": "absent", "names": [], "reason": ""}
    else:
        default = read_names(default_bytes)
        if default["state"] == "malformed":
            return done("reference-malformed", "the default branch's rules file: " + default["reason"])
    if working["state"] == "malformed":
        return done("working-malformed", "the working rules file: " + working["reason"])
    if working["state"] == "absent" and default["names"]:
        return done("working-malformed", "the working rules file is absent but the default branch lists "
                    "protected names")
    present = set(working["names"])
    missing = []
    for name in default["names"]:
        if name not in present and name not in missing:
            missing.append(name)
    if missing:
        return done("names-removed", "%d protected name(s) of the default branch are missing" % len(missing),
                    missing)
    return done("kept")


def passes(verdict):
    """True for the two verdicts that pass."""
    return verdict in ("kept", "first-install")
