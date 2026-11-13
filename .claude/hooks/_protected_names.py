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
  1. ``unverifiable``       no remote named ``origin``, or no default branch, or no usable git program, or a
                            git call fails or runs past its limit, or the listing of the default-branch commit
                            fails.
  2. ``first-install``      the listing of that commit succeeds and holds neither the rules file nor a
                            rules-path alias, and the working reading is absent or parsed. Passes.
  3. ``reference-malformed`` the default-branch reading is malformed (an alias of the rules path makes it so).
  4. ``working-malformed``  the working reading is malformed (an alias makes it so), or the working file is
                            absent while the default-branch list is not empty.
  5. ``names-removed``      some default-branch string is not, as an exact string, among the working strings.
  6. ``kept``               every default-branch string is present. Passes.

A names reading is parsed as follows: the bytes decoded as strict UTF-8; a leading byte order mark is
malformed (the guard's own loader cannot read it); JSON with a duplicate key ANYWHERE rejected; the top
level must be an object; ``protected_databases`` absent counts as an empty list; present, it must be a list
of strings. No string is trimmed, case-folded, normalised or skipped (blank strings included).

THE ALIAS RULE (contract 2026-10-13, Names reading). A reading of a commit lists the commit's WHOLE tree once
(``git ls-tree -r -z --full-tree``, no pathspec). A rules-path alias is a listed path that is not
byte-for-byte the rules path but has the same number of folders and matches it level by level (letter case
folded, trailing dots and spaces dropped, a ``:``-stream suffix dropped, or an 8.3 short-name shape). Any
alias makes that side's reading malformed, whether or not the exact path exists too. Disk mode applies the
same rule to the whole index (``git ls-files -z --full-name``) and to the directory listing of the project
root and of each folder on the path.

GIT ISOLATION (contract 2026-10-13, Commands). Every git process but the two network calls of ``--fetch``
runs from an absolute program path found by ``resolve_git`` (never from the current folder, an empty or
relative PATH entry, or a tree under check), with an environment built from nothing by ``git_environment``,
``--no-replace-objects`` first, and command-line settings that beat every configuration file.

NO EXEMPTION reads the tree under check: the plugin's own checkout is compared like any other.

STANDARD LIBRARY ONLY. It imports no path-bridge helper of this plugin: the landing gate runs it from a
private folder that holds nothing else but its command line. Git runs through ``subprocess`` with a
5-second limit per call; the only network calls are the explicit ``git fetch`` and ``git ls-remote`` a
caller asks for (20 seconds each).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
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

#: Seconds each git call may take, and the explicit fetch / ls-remote.
GIT_TIMEOUT = 5
FETCH_TIMEOUT = 20

#: The default-branch refs tried after ``refs/remotes/origin/HEAD``, in this order.
FALLBACK_DEFAULT_REFS = ("refs/remotes/origin/master", "refs/remotes/origin/main")

#: The variables copied from the caller into the isolated git environment (the rest is built, not filtered).
COPIED_ENV = ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT")

#: Command-line settings every isolated git call carries. They beat every configuration file.
GIT_SETTINGS = ("core.fsmonitor=false", "core.untrackedCache=false", "index.sparse=false",
                "core.quotePath=false", "core.longpaths=true")


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
# The Alias rule
# ---------------------------------------------------------------------------
#: Characters a full case mapping misses, with the ASCII letter each one matches (either case).
_EXPLICIT_FAMILY = {"İ": "i", "ı": "i", "ſ": "s", "K": "k"}

#: An 8.3 short-name shape: at most 8 characters, a ``~`` and digits, then an optional dot and at most 3.
_SHORT_NAME_RE = re.compile(r"^([^.~]*~[0-9]+)(\.[^.]{0,3})?$")


def _letters_match(a, b):
    if a == b:
        return True
    if a.casefold() == b.casefold() or a.upper() == b.upper() or a.lower() == b.lower():
        return True
    if a in _EXPLICIT_FAMILY and b.lower() == _EXPLICIT_FAMILY[a]:
        return True
    if b in _EXPLICIT_FAMILY and a.lower() == _EXPLICIT_FAMILY[b]:
        return True
    return False


def _fold_component(name):
    """A path component with its stream suffix, then its trailing dots and spaces, dropped."""
    cut = name.find(":")
    if cut >= 0:
        name = name[:cut]
    return name.rstrip(". ")


def _component_matches(candidate, wanted):
    """True when the listed folder or file name ``candidate`` can be written over ``wanted`` on NTFS."""
    short = _SHORT_NAME_RE.match(candidate)
    if short and len(short.group(1)) <= 8:
        return True
    folded = _fold_component(candidate)
    if len(folded) != len(wanted):
        return False
    return all(_letters_match(a, b) for a, b in zip(folded, wanted))


def is_rules_alias(path, rules_rel=RULES_REL):
    """True when ``path`` (a string with ``/`` separators) is NOT byte-for-byte ``rules_rel`` but matches
    it folder by folder."""
    if path == rules_rel:
        return False
    wanted = rules_rel.split("/")
    parts = path.split("/")
    if len(parts) != len(wanted):
        return False
    return all(_component_matches(part, want) for part, want in zip(parts, wanted))


def _decode_path(raw):
    return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# git: program, environment, calls
# ---------------------------------------------------------------------------
#: C8 (contract 2026-10-13, Revision 6): a leading ``\\?\UNC\``, ``\\?\`` or ``\\.\``, and an administrative
#: drive share ``\\<host>\<letter>$`` reached through this computer.
#: C12 (Revision 7): in the first four characters ``/`` and ``\`` are the same character; the prefix is stripped
#: only before a drive letter and a colon, and ``UNC\`` is rewritten to ``\\``. Anything else is a device path.
_DEVICE_RE = re.compile(r"^[\\/]{2}[?.][\\/]")
_DRIVE_PREFIX_RE = re.compile(r"^[\\/]{2}[?.][\\/][A-Za-z]:")
_UNC_PREFIX_RE = re.compile(r"^[\\/]{2}[?.][\\/]UNC\\", re.IGNORECASE)
_ADMIN_SHARE_RE = re.compile(r"^\\\\([^\\]+)\\([A-Za-z])\$(?=\\|$)")


def _strip_prefixes(path):
    """C8 steps 1 and 2: the ``\\\\?\\`` and ``\\\\.\\`` prefixes, and an own-computer drive share, as text."""
    text = str(path)
    if _UNC_PREFIX_RE.match(text):
        text = "\\\\" + text[len("\\\\?\\UNC\\"):]
    elif _DRIVE_PREFIX_RE.match(text):
        text = text[4:]
    match = _ADMIN_SHARE_RE.match(text)
    if match and match.group(1).lower() in ("localhost", "127.0.0.1", socket.gethostname().lower()):
        text = match.group(2) + ":" + text[match.end():]
    return text


def is_device_path(path):
    """C12: True for a path in the device namespace that is not a drive form or a long UNC form
    (``\\\\.\\Volume{GUID}\\``, ``\\\\?\\GLOBALROOT\\``, ``\\\\.\\pipe\\``)."""
    text = str(path)
    return bool(_DEVICE_RE.match(text)) and not _DRIVE_PREFIX_RE.match(text) and not _UNC_PREFIX_RE.match(text)


def comparable_path(path):
    """C8's resolved spelling: steps 1 and 2, ``realpath``, steps 1 and 2 again, ``normcase``. A device path
    (C12), as written or once resolved, is ``normcase`` of its text: no ``realpath``, no ``abspath``."""
    text = str(path)
    if is_device_path(text):
        return os.path.normcase(text)
    resolved = os.path.realpath(_strip_prefixes(text))
    if is_device_path(resolved):
        return os.path.normcase(resolved)
    return os.path.normcase(_strip_prefixes(resolved))


def written_path(path):
    """C8's written spelling: steps 1, 2 and 5 with ``abspath`` for ``realpath`` (no link is followed)."""
    text = str(path)
    if is_device_path(text):
        return os.path.normcase(text)
    return os.path.normcase(os.path.abspath(_strip_prefixes(text)))


def _norm(path):
    return comparable_path(path)


def _inside(folder, root):
    return folder == root or folder.startswith(root.rstrip("\\/") + os.sep)


def resolve_git(path_value, excluded_roots):
    """The absolute path of the git program to run, or ``None``.

    Walks the ``PATH`` entries in order, skipping an empty, relative or ``.`` entry, the current folder, and
    any entry inside an excluded root (the project, the linked worktrees, any tree under check); the first
    ``git.exe`` (``git`` elsewhere) found is the program. Roots and entries both go through C8: an entry is
    skipped when EITHER of its two spellings (written, resolved) lies inside EITHER spelling of a root."""
    name = "git.exe" if os.name == "nt" else "git"
    roots = []
    for root in (excluded_roots or []):
        if root:
            spelled = {written_path(root), comparable_path(root)}
            if any(is_device_path(s) for s in spelled):
                return None  # C12: a device-path root cannot be compared, so the search is unverifiable
            roots.extend(spelled)
    here = comparable_path(os.getcwd())
    for entry in (path_value or "").split(os.pathsep):
        entry = entry.strip().strip('"')
        if not entry or entry == "." or not os.path.isabs(entry):
            continue
        spellings = {written_path(entry), comparable_path(entry)}
        if any(is_device_path(s) for s in spellings):
            continue  # C12: a device-path entry is never compared and never the program
        if comparable_path(entry) == here or any(_inside(s, root) for s in spellings for root in roots):
            continue
        candidate = os.path.join(entry, name)
        if os.path.isfile(candidate) and (os.name == "nt" or os.access(candidate, os.X_OK)):
            return os.path.abspath(candidate)
    return None


def git_environment(private_dir, git_program):
    """The environment of every git process of a run, built from nothing (never the caller's with entries
    removed): ``SYSTEMROOT``, ``WINDIR``, ``COMSPEC`` and ``PATHEXT`` copied from the caller; ``PATH`` the
    folder of ``git_program`` plus ``%SYSTEMROOT%\\System32``; ``TEMP``, ``TMP``, ``TMPDIR``, ``HOME`` and
    ``USERPROFILE`` the private folder; and replace refs off, no system or global configuration file, no
    prompt and no optional locks. Nothing else is present."""
    caller = os.environ
    env = {}
    for key in COPIED_ENV:
        if key in caller:
            env[key] = caller[key]
    folders = [os.path.dirname(str(git_program))]
    if "SYSTEMROOT" in caller:
        folders.append(os.path.join(caller["SYSTEMROOT"], "System32"))
    elif os.name != "nt":
        folders.extend(["/usr/bin", "/bin"])
    env["PATH"] = os.pathsep.join(folders)
    for key in ("TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE"):
        env[key] = str(private_dir)
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


def _read_pointer(path, what):
    """The one-line text of a git pointer file (``.git``, ``commondir``, ``gitdir``). Raises ``GitFailure``
    when it exists but cannot be read, is not a file, or holds nothing."""
    try:
        if not path.is_file():
            raise GitFailure("%s exists but is not a readable file: %s" % (what, path))
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as exc:
        raise GitFailure("%s cannot be read: %s" % (what, exc)) from exc
    if not text:
        raise GitFailure("%s holds no path: %s" % (what, path))
    return text


def linked_worktrees(project):
    """C7 (contract 2026-10-13, Revision 6): the folders a git program found on PATH must never come from,
    read from files with NO git process: ``project``, the main checkout (the parent of the common folder when
    that is named ``.git``, letter case folded), every linked worktree (the parent of each
    ``<common>/worktrees/*/gitdir``) and the common folder. The same set from the main checkout and from a
    linked worktree: ``commondir`` is resolved relative to the git folder. A pointer file that exists but
    cannot be read or parsed raises ``GitFailure`` (unverifiable); a missing ``worktrees`` folder is an empty
    list."""
    root = Path(project)
    roots = [str(root)]
    dot_git = root / ".git"
    if not os.path.lexists(str(dot_git)):
        return roots
    if dot_git.is_dir():
        git_dir = dot_git
    else:
        text = _read_pointer(dot_git, "the .git file")
        if not text.lower().startswith("gitdir:"):
            raise GitFailure("the .git file holds no gitdir line: %s" % dot_git)
        git_dir = Path(root, text[len("gitdir:"):].strip())
        if not git_dir.is_dir():
            raise GitFailure("the gitdir the .git file names is not a folder: %s" % git_dir)
    pointer = git_dir / "commondir"
    if os.path.lexists(str(pointer)):
        common = Path(git_dir, _read_pointer(pointer, "commondir"))
        if not common.is_dir():
            raise GitFailure("the commondir names no folder: %s" % common)
    else:
        common = git_dir
    common = Path(os.path.normpath(str(common)))
    if common.name.lower() == ".git":
        roots.append(str(common.parent))
    try:
        worktrees = common / "worktrees"
        entries = sorted(worktrees.iterdir()) if worktrees.is_dir() else []
    except OSError as exc:
        raise GitFailure("the worktrees folder cannot be read: %s" % exc) from exc
    for entry in entries:
        gitdir = entry / "gitdir"
        if os.path.lexists(str(gitdir)):
            roots.append(str(Path(entry, _read_pointer(gitdir, "a worktree gitdir file")).parent))
    roots.append(str(common))
    return roots


#: The state of the check that is running (set by ``check``): the git program, its environment and the
#: roots excluded from the program search. ``None`` outside a run.
_RUN = None


def _safe_directory(project):
    return os.path.realpath(str(project)).replace("\\", "/")


def git(project, args, timeout=GIT_TIMEOUT, network=False):
    """Run ``git <args>`` in ``project``. Returns ``(returncode, stdout_bytes)``.

    Every call runs the resolved absolute git program with the isolated environment, ``--no-replace-objects``
    first and then the command-line settings (``network=True``, only ``fetch`` and ``ls-remote``, keeps the
    caller's environment because credentials live in the user's configuration). Raises ``GitFailure`` when git
    cannot start or runs past its limit; a non-zero code is returned."""
    run = _RUN
    if run is None:
        raise GitFailure("no git program was resolved for this run")
    if network:
        command = [run["git"]] + list(args)
        env = dict(os.environ)
        env["GIT_TERMINAL_PROMPT"] = "0"
    else:
        command = [run["git"], "--no-replace-objects"]
        for setting in GIT_SETTINGS:
            command += ["-c", setting]
        command += ["-c", "safe.directory=" + _safe_directory(project)] + list(args)
        env = run["env"]
    try:
        proc = subprocess.run(command, cwd=str(project), capture_output=True, timeout=timeout, env=env,
                              stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired as exc:
        raise GitFailure("git %s ran past %d seconds" % (" ".join(args[:2]), timeout)) from exc
    except (OSError, ValueError) as exc:
        raise GitFailure("git could not run: %s" % exc) from exc
    return proc.returncode, proc.stdout


def _git_text(project, args, timeout=GIT_TIMEOUT, network=False):
    code, out = git(project, args, timeout, network)
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


def read_rules(project, commit, rules_rel):
    """``(listed, data, aliases, copies, backslashed)`` of ``commit``: whether it holds ``rules_rel`` byte for
    byte, that file's bytes, every listed path that is a rules-path alias, how many times the exact path is
    listed, and every listed path that holds a ``\\`` (C11, Revision 7).
    The whole tree is listed once from the root with no pathspec; the blob is read by the object id from that
    listing. With ``copies`` above one (a duplicate entry of the file or of a folder on its path) nothing is
    read: ``data`` is ``None`` and the caller reports the side as malformed (``duplicate-entry``). Raises
    ``GitFailure`` when the listing fails."""
    code, out = git(project, ["ls-tree", "-r", "-z", "--full-tree", commit])
    if code != 0:
        raise GitFailure("git ls-tree failed for %s (exit %d)" % (commit, code))
    exact = rules_rel.encode("utf-8")
    oids = []
    aliases = []
    backslashed = []
    for entry in out.split(b"\0"):
        if not entry:
            continue
        meta, _tab, raw = entry.partition(b"\t")
        if b"\\" in raw:
            backslashed.append(_decode_path(raw))  # C11: any path holding a backslash makes the side malformed
        if raw == exact:
            fields = meta.split()
            oids.append(fields[2].decode("ascii") if len(fields) == 3 else "")
        elif is_rules_alias(_decode_path(raw), rules_rel):
            aliases.append(_decode_path(raw))
    if not oids:
        return False, None, aliases, 0, backslashed
    if len(oids) > 1:
        return True, None, aliases, len(oids), backslashed
    if not oids[0]:
        raise GitFailure("git ls-tree gave no object id for %s:%s" % (commit, rules_rel))
    code, blob = git(project, ["cat-file", "blob", oids[0]])
    if code != 0:
        raise GitFailure("git cat-file failed for %s:%s (exit %d)" % (commit, rules_rel, code))
    return True, blob, aliases, 1, backslashed


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


def _read_working_disk(project, rules_rel=RULES_REL):
    path = Path(project) / Path(*rules_rel.split("/"))
    try:
        if not path.exists():
            return None
        if not path.is_file():
            return b"\xff"  # not a file: reads as malformed (a folder where the rules file should be)
        return path.read_bytes()
    except OSError:
        return b"\xff"


def _disk_aliases(project, rules_rel):
    """Rules-path aliases of the working copy: the whole index (``git ls-files -z --full-name``) and the
    directory listing of the project root and of each folder on the path."""
    aliases = []
    backslashed = []
    code, out = git(project, ["ls-files", "-z", "--full-name"])
    if code != 0:
        raise GitFailure("git ls-files failed (exit %d)" % code)
    for raw in out.split(b"\0"):
        if raw and b"\\" in raw:
            backslashed.append(_decode_path(raw))  # C11
        if raw and is_rules_alias(_decode_path(raw), rules_rel):
            aliases.append(_decode_path(raw))
    wanted = rules_rel.split("/")
    level = [(str(project), False)]
    for want in wanted:
        following = []
        for folder, differs in level:
            try:
                names = os.listdir(folder)
            except OSError:
                continue
            for name in names:
                if _component_matches(name, want):
                    following.append((os.path.join(folder, name), differs or name != want))
        level = following
    for folder, differs in level:
        if differs:
            aliases.append(os.path.relpath(folder, str(project)).replace("\\", "/"))
    return aliases, backslashed


def check(project, working_ref=None, default_ref=None, fetch=False, rules_rel=RULES_REL):
    """Run one Protected-name check of ``project``. Returns the result dict (see ``_result``).

    ``working_ref``  None reads the working copy from disk; a git ref reads the committed file at it.
    ``default_ref``  None detects ``origin``'s default branch; a git ref names the commit for that side.
    ``fetch``        run the explicit fetch of the default branch first (refused with ``default_ref``).
    Never raises: anything unexpected is ``unverifiable``."""
    global _RUN
    previous = _RUN
    private = None
    try:
        excluded = [str(project)] + linked_worktrees(project)
        program = resolve_git(os.environ.get("PATH", ""), excluded)
        if program is None:
            return _result("unverifiable", "no usable git program: no PATH entry outside the trees under check "
                           "holds one", "no-git")
        private = tempfile.mkdtemp(prefix="pn-git-")
        _RUN = {"git": program, "env": git_environment(private, program)}
        return _check(project, working_ref, default_ref, fetch, rules_rel)
    except GitFailure as exc:
        return _result("unverifiable", str(exc), "git-failed")
    except Exception as exc:  # noqa: BLE001 -- the contract: an unreadable run is unverifiable
        return _result("unverifiable", "unexpected error: %r" % (exc,), "error")
    finally:
        _RUN = previous
        if private:
            shutil.rmtree(private, ignore_errors=True)


def _fetch_default(project, branch):
    """The explicit-destination fetch and the ``ls-remote`` comparison. Returns ``(fetched, reason_code)``:
    ``(True, "")`` only when the local ref equals the commit the remote advertises."""
    if not branch:
        return False, "fetch-failed"
    destination = "+refs/heads/%s:refs/remotes/origin/%s" % (branch, branch)
    try:
        code, _out = git(project, ["fetch", "--quiet", "--no-tags", "--no-write-fetch-head", "origin", destination],
                         FETCH_TIMEOUT, network=True)
        if code != 0:
            return False, "fetch-failed"
        code, text = _git_text(project, ["ls-remote", "origin", "refs/heads/%s" % branch], FETCH_TIMEOUT,
                               network=True)
    except GitFailure:
        return False, "fetch-failed"
    lines = [line for line in text.splitlines() if line.strip()]
    if code != 0 or not lines:
        return False, "fetch-failed"
    advertised = lines[0].split()[0]
    local = resolve_commit(project, "refs/remotes/origin/%s" % branch)
    if local is None or local != advertised:
        return False, "ref-not-updated"
    return True, ""


def _check(project, working_ref, default_ref, fetch, rules_rel):
    working_label = "disk" if working_ref is None else working_ref
    fetched = None
    fetch_code = ""
    default_branch = ""
    default_commit = None

    if default_ref is None:
        if not has_origin(project):
            return _result("unverifiable", "no remote named origin", "no-origin", working_ref=working_label)
        if fetch:
            branch = (default_branch_ref(project) or (None, None))[0] or _branch_name_only(project)
            fetched, fetch_code = _fetch_default(project, branch)
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
        if fetched is False:
            reason = ("%s; the fetch did not give a fresh ref (%s), so the local default-branch ref dated %s was "
                      "compared" % (reason, fetch_code or "fetch-failed", default_date or "an unknown date")
                      ).lstrip("; ")
        return _result(verdict, reason, code, missing, working_label, default_commit, fetched,
                       default_branch, default_date)

    listed, default_bytes, default_aliases, default_copies, default_backslashed = read_rules(
        project, default_commit, rules_rel)  # may raise GitFailure
    working_copies = 0
    if working_commit is not None:
        _wl, working_bytes, working_aliases, working_copies, working_backslashed = read_rules(
            project, working_commit, rules_rel)
    else:
        working_bytes = _read_working_disk(project, rules_rel)
        working_aliases, working_backslashed = _disk_aliases(project, rules_rel)
    working = read_names(working_bytes)
    if working_backslashed:
        working = {"state": "malformed", "names": [],
                   "reason": "backslash-in-path: the tree lists a path holding a backslash: %s"
                             % ", ".join(repr(a) for a in working_backslashed[:3])}
    if working_aliases:
        working = {"state": "malformed", "names": [],
                   "reason": "a path that is an alias of the rules file exists beside it: %s"
                             % ", ".join(repr(a) for a in working_aliases[:3])}
    if working_copies > 1:
        working = {"state": "malformed", "names": [],
                   "reason": "duplicate-entry: the rules path is listed %d times in the tree" % working_copies}

    if default_backslashed:
        return done("reference-malformed", "backslash-in-path: the default branch lists a path holding a "
                    "backslash: %s" % ", ".join(repr(a) for a in default_backslashed[:3]))
    if default_copies > 1:
        return done("reference-malformed", "duplicate-entry: the default branch lists the rules path %d times"
                    % default_copies)
    if default_aliases:
        return done("reference-malformed", "the default branch holds an alias of the rules file path: %s"
                    % ", ".join(repr(a) for a in default_aliases[:3]))
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
