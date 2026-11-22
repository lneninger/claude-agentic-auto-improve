"""Fail when a change to shipped plugin files does not raise the plugin version (CLAUDE.md rule).

Usage: ``py -3 .claude/scripts/check_version_bump.py [--base origin/master] [--default-branch master]
[--head-ref task/<slug>/<id>]``, or ``--exact`` / ``--raise`` (the landing of a parent-branch contract).

Modes: default (today's check); parent (a ``task/<slug>/<id>`` head into a non-default base must NOT raise: its
version equals the base's, or the one at merge-base(origin/<default>, HEAD)); exact (minor + 1, patch 0,
relative to origin/<default>, all entries agree); ``--raise`` writes that exact version into every manifest and commits it.

A head that is not ``task/*`` into a non-default base is not checked (exit 0); default-branch bases keep the default rules.

Counts (contract 2026-11-14-manifest-counts-landing-refresh): ``--counts`` checks the skill, agent and hook counts of
the manifest descriptions against HEAD's tree (no version, no base, no origin ref, writes nothing). ``--manifest-counts``
rides on ``--raise`` (rewrites the numbers of those counts from the tree in the same commit as the version, all or
nothing) or ``--exact`` (also checks them). Without either flag every mode above is unchanged.

Exit 0: no shipped file changed, or the version was raised and the five manifest entries agree; with the count
        flags, every count equals the tree.
Exit 1: shipped files changed without a higher version, or the manifests disagree; with the count flags, a count
        differs from the tree or a description cannot be refreshed (a ``description`` Count refusal).
Exit 2: the check could not run (never an allow); with the count flags, also a ``read`` Count refusal (the tree
        listing failed, or a measure reads zero). With ``--exact --manifest-counts`` the higher of the two codes.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

MANIFESTS = ("plugin.json", ".claude-plugin/plugin.json", ".cursor-plugin/plugin.json",
             ".claude-plugin/marketplace.json")
# A file plugin_doctor copies into user projects is shipped, so it must not be listed here;
# enforced by test_check_version_bump.py.
EXEMPT_PREFIXES = (".claude/work-items/", ".claude/scripts/tests/", ".github/", ".claude/concepts/",
                   ".claude/north-stars/", ".claude/orchestrator/results/",
                   ".claude/reviews/")
EXEMPT_NAMES = ("CLAUDE.md", "README.md", "CONTRIBUTING.md", "LICENSE", ".gitignore")


def is_shipped(path: str) -> bool:
    """True when ``path`` is a file the plugin ships, so changing it needs a version bump."""
    if path in MANIFESTS or path in EXEMPT_NAMES or path.endswith(".md") and "/" not in path:
        return False
    return not path.startswith(EXEMPT_PREFIXES)


def parse_version(text: str) -> Optional[Tuple[int, ...]]:
    try:
        return tuple(int(p) for p in text.split("."))
    except (ValueError, AttributeError):
        return None


def versions_in(manifests: dict) -> List[str]:
    """Every version string in the manifests, in file order (marketplace holds two)."""
    found: List[str] = []
    for name in MANIFESTS:
        data = json.loads(manifests[name])
        if "version" in data:
            found.append(data["version"])
        for entry in data.get("plugins", []) if isinstance(data.get("plugins"), list) else []:
            if "version" in entry:
                found.append(entry["version"])
    return found


def evaluate(changed: List[str], base_versions: List[str], head_versions: List[str]) -> Tuple[int, str]:
    shipped = [p for p in changed if is_shipped(p)]
    if not shipped:
        return 0, "no shipped plugin file changed; no version bump needed"
    if len(set(head_versions)) != 1:
        return 1, "the manifests disagree on the version: %s" % ", ".join(head_versions)
    head, base = parse_version(head_versions[0]), parse_version(base_versions[0] if base_versions else "")
    if head is None or base is None:
        return 2, "a version could not be read (base %s, head %s)" % (base_versions, head_versions)
    if head <= base:
        return 1, ("shipped files changed (%s) but the plugin version is still %s; raise it in all manifests"
                   % (", ".join(shipped[:3]), head_versions[0]))
    return 0, "version raised to %s" % head_versions[0]


TASK_HEAD = re.compile(r"^task/[^/]+/.+")
VERSION_FIELD = re.compile(r'("version"\s*:\s*")[^"]*(")')


def evaluate_parent(head_versions: List[str], allowed_versions: List[str]) -> Tuple[int, str]:
    """A sub-task pull request into a parent branch never raises: head == base's or merge-base's version."""
    if len(set(head_versions)) != 1:
        return 1, "the manifests disagree on the version: %s" % ", ".join(head_versions)
    if head_versions[0] in allowed_versions:
        return 0, "sub-task pull request keeps version %s; the landing raises it" % head_versions[0]
    return 1, ("a sub-task pull request must not raise the plugin version (head %s, allowed %s); "
               "the landing raises it once" % (head_versions[0], ", ".join(sorted(set(allowed_versions)))))


def exact_version(default_versions: List[str]) -> Optional[str]:
    """The landing version for a default branch at ``default_versions``: minor + 1, patch 0."""
    parsed = [parse_version(v) for v in default_versions]
    if not parsed or any(p is None or len(p) != 3 for p in parsed):
        return None
    major, minor, _patch = max(parsed)
    return "%d.%d.0" % (major, minor + 1)


def evaluate_exact(default_versions: List[str], head_versions: List[str]) -> Tuple[int, str]:
    wanted = exact_version(default_versions)
    if wanted is None:
        return 2, "a version could not be read (default branch %s)" % default_versions
    if len(set(head_versions)) != 1:
        return 1, "the manifests disagree on the version: %s" % ", ".join(head_versions)
    if head_versions[0] != wanted:
        return 1, "the landing version must be exactly %s (minor + 1, patch 0), found %s" % (wanted, head_versions[0])
    return 0, "version is exactly %s" % wanted


def raise_manifests(wanted: str, refreshed: Optional[Dict[str, str]] = None) -> bool:
    """Rewrite every ``"version"`` field of every manifest to ``wanted`` (byte-preserving otherwise) and commit
    it, so ``--exact`` and a later merge see it. Returns False, committing nothing, when already at ``wanted``.

    ``refreshed`` (the ``texts`` of a ``CountPlan`` with no refusal) also writes the count rewrites, in the same
    commit; the message says which of the two changed. Without it the behaviour is the version-only raise."""
    version_changed = counts_changed = False
    for name in MANIFESTS:
        with open(name, encoding="utf-8", newline="") as handle:
            text = handle.read()
        base = text
        if refreshed is not None and refreshed.get(name, text) != text:
            counts_changed, base = True, refreshed[name]
        updated = VERSION_FIELD.sub(lambda m: m.group(1) + wanted + m.group(2), base)
        version_changed = version_changed or updated != base
        if updated != text:
            with open(name, "w", encoding="utf-8", newline="") as handle:
                handle.write(updated)
    if version_changed or counts_changed:
        if version_changed and counts_changed:
            message = "chore: raise the plugin version to %s and refresh the manifest counts at the landing" % wanted
        elif counts_changed:
            message = "chore: refresh the manifest counts at the landing"
        else:
            message = "chore: raise the plugin version to %s at the landing" % wanted
        _git("add", "--", *MANIFESTS)
        _git("commit", "-q", "--no-verify", "-m", message, "--", *MANIFESTS)
    return version_changed or counts_changed


#: C13: the absolute git program ``--git-program`` named (validated by ``main`` before anything runs); None when
#: the flag is absent.
_git_program: Optional[str] = None


def _git_command(*args: str) -> List[str]:
    """The argv of every git process this script starts: the ``--git-program`` path when it was given, the bare
    name only when the flag is absent (the one place this script names git)."""
    if _git_program:
        return [_git_program, *args]
    return ["git", *args]


def _git(*args: str, cwd: Optional[str] = None) -> str:
    return subprocess.run(_git_command(*args), capture_output=True, text=True, check=True, cwd=cwd).stdout


def is_non_default_base(base_ref: Optional[str], default_ref: Optional[str]) -> bool:
    """The one base comparison: a base that is not ``default_ref``; an absent base is not the default."""
    return base_ref != default_ref


def is_parent_mode(head_ref: str, base_ref: Optional[str], default_ref: str) -> bool:
    """True for a ``task/<slug>/<id>`` head whose base is not ``default_ref``; an absent base is not the default."""
    return bool(head_ref) and bool(TASK_HEAD.match(head_ref)) and is_non_default_base(base_ref, default_ref)


def count_pin_deferred(head_ref: str, base_ref: Optional[str], default_ref: Optional[str]) -> bool:
    """True when the manifest count pin only checks that the counts are refreshable (Count deferral).

    That is a pull request into a non-default base: a ``task/<slug>/<id>`` head (parent mode, an absent base
    included) or any head with a named base that is not the default branch. An unknown default branch (None,
    empty or blank) never defers: without this guard ``None != ""`` would make every pull request look like
    one into a parent branch. All three values come in one form (bare branch names, or all ``origin/`` refs).
    """
    default_known = default_ref is not None and bool(default_ref.strip())
    return default_known and (is_parent_mode(head_ref, base_ref, default_ref)
                              or (base_ref is not None and is_non_default_base(base_ref, default_ref)))


def parent_allowed_versions(base_ref: Optional[str], default_ref: str, cwd: Optional[str] = None) -> List[str]:
    """The versions at ``base_ref`` (skipped when None) then at merge-base(default_ref, HEAD); git failures raise."""
    merge_base = _git("merge-base", default_ref, "HEAD", cwd=cwd).strip()
    allowed: List[str] = []
    for ref in (base_ref, merge_base):
        if ref is None:
            continue
        allowed += versions_in({m: _git("show", "%s:%s" % (ref, m), cwd=cwd) for m in MANIFESTS})
    return allowed


# ---------------------------------------------------------------------------
# Manifest counts (contract 2026-11-14-manifest-counts-landing-refresh, I-1)
#
# The three path rules, the git listing and the claim reader live HERE, once. test_repo_consistency.py
# imports the reader and keeps only a disk listing; it never holds a second copy of a rule.
# ---------------------------------------------------------------------------
SKILLS_ROOT = "skills/"
AGENTS_ROOT = "agents/"
HOOKS_ROOT = ".claude/hooks/"
GATE_LAUNCHER = "gate-launch.py"
COUNT_MEASURES = ("skills", "agents", "hooks")


def is_counted_hook_name(name: str) -> bool:
    """A hook file: ``*.py``, not a ``_`` helper, not the gate launcher."""
    return name.endswith(".py") and not name.startswith("_") and name != GATE_LAUNCHER


def counted_paths(measure: str, paths: Iterable[str]) -> List[str]:
    """The paths among ``paths`` (repository-relative, ``/`` separators, case-sensitive) that ``measure`` counts.

    skills: ``skills/<one segment>/SKILL.md``. agents: ``agents/<name>.md``. hooks: ``.claude/hooks/<name>.py``
    directly, see ``is_counted_hook_name``. Never touches disk or git.
    """
    if measure not in COUNT_MEASURES:
        raise ValueError("unknown count measure %r" % (measure,))
    found = set()
    for path in paths:
        if measure == "skills":
            parts = path[len(SKILLS_ROOT):].split("/") if path.startswith(SKILLS_ROOT) else []
            if len(parts) == 2 and parts[0] and parts[1] == "SKILL.md":
                found.add(path)
        elif measure == "agents":
            rest = path[len(AGENTS_ROOT):] if path.startswith(AGENTS_ROOT) else ""
            if rest.endswith(".md") and "/" not in rest:
                found.add(path)
        elif measure == "hooks":
            rest = path[len(HOOKS_ROOT):] if path.startswith(HOOKS_ROOT) else ""
            if rest and "/" not in rest and is_counted_hook_name(rest):
                found.add(path)
        else:
            raise ValueError("unknown count measure %r" % (measure,))
    return sorted(found)


def measure_count(measure: str, paths: Iterable[str]) -> int:
    return len(counted_paths(measure, paths))


def tree_paths(cwd: Optional[str] = None) -> List[str]:
    """Every tracked path at HEAD, byte-exact: ``git ls-tree -r -z --name-only HEAD`` read as raw bytes.

    ``-z`` stops git quoting a path that holds a non-ASCII byte, a quote or a backslash, and the bytes are
    decoded as UTF-8 with ``surrogateescape`` rather than through ``_git``'s locale text decoding (D4).
    A git failure raises ``subprocess.CalledProcessError``.
    """
    raw = subprocess.run(_git_command("ls-tree", "-r", "-z", "--name-only", "HEAD"), capture_output=True,
                         check=True, cwd=cwd).stdout
    return [chunk.decode("utf-8", "surrogateescape") for chunk in raw.split(b"\0") if chunk]


WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen twenty".split())}
_NUM = r"(\d+|" + "|".join(w for w in WORDS if w != "zero") + r")"
# <number> [up to three words] hooks | hook files. The noun is exact so "9 hook test suites" never matches.
# A gap word may not itself be a digit string or a spelled number, so the number taken is the one nearest the noun.
_GAP_WORD = r"(?!(?:\d|(?:" + "|".join(w for w in WORDS if w != "zero") + r")\b))\w+"
_COUNT_RE = re.compile(r"(?i)(?<![\w.])" + _NUM + r"[ \t]+(?:" + _GAP_WORD + r"[ \t]+){0,3}?(?:hooks|hook files)\b(?!/)")

# Each noun a count claim can name maps to one measure. The skill measure and the agent measure are separate;
# "subagents" is the Claude Code word for the agent files, so it reads the agent measure.
_ORACLE_NOUNS = (
    ("working agreements", "agreements"), ("subagents", "agents"), ("skills", "skills"), ("agents", "agents"),
    ("hooks", "hooks"), ("shared helper modules", "helpers"), ("generic data files", "data_files"),
    ("document templates", "templates"), ("reference documents", "references"), ("add-ons", "addons"),
)
_CLAIM_RE = re.compile(
    r"(?i)(?<![\w.])(\d+|" + "|".join(w for w in WORDS if w != "zero") + r")[ \t]+(?:[\w-]+[ \t]+){0,2}?("
    + "|".join(re.escape(n) for n, _ in _ORACLE_NOUNS) + r")\b")
_NOUN_MEASURE = dict(_ORACLE_NOUNS)

# Nouns each manifest's descriptions must state (so a check proves it read a count). The marketplace's
# top-level description has no count; the requirement is met by any description of the file.
MANIFEST_COUNT_NOUNS = {
    "plugin.json": ("skills",),
    ".claude-plugin/plugin.json": ("skills", "agents", "hooks"),
    ".claude-plugin/marketplace.json": ("skills", "agents", "hooks"),
    ".cursor-plugin/plugin.json": ("skills", "subagents"),
}


def mask_count_numbers(text: str) -> str:
    """``text`` with the number of every count claim replaced by ``#``: two texts that mask equal differ only
    in the numbers of their count claims (the landing's R-3 uses this, so it reads claims as this script does)."""
    return _CLAIM_RE.sub(lambda m: m.group(0)[:m.start(1) - m.start()] + "#" + m.group(0)[m.end(1) - m.start():], text)


def _counts(regex: "re.Pattern[str]", text: str) -> List[Tuple[str, int]]:
    found = []
    for m in regex.finditer(text):
        if re.search(r"(?i)retired\s+$", text[max(0, m.start() - 12):m.start()]):
            continue
        tok = m.group(1).lower()
        found.append((re.sub(r"\s+", " ", m.group(0)), int(tok) if tok.isdigit() else WORDS[tok]))
    return found


def manifest_descriptions(data: dict) -> List[str]:
    out = [data["description"]] if isinstance(data.get("description"), str) else []
    for p in data.get("plugins", []) or []:
        if isinstance(p, dict) and isinstance(p.get("description"), str):
            out.append(p["description"])
    return out


# --- the Count verdict and the Landing count refresh (I-2 to I-5) ----------------------------------------
_SPELLED = {i: w for w, i in WORDS.items() if i >= 1}


class CountRefusal(NamedTuple):
    """One named reason the counts cannot be refreshed. ``kind`` is ``description`` or ``read`` (I-4's exit map)."""
    reason: str
    kind: str
    manifest: str
    detail: str


class CountPlan(NamedTuple):
    """The refresh plan for all manifests, computed before anything is written. Only an empty ``refusals``
    list lets ``texts`` be written; ``mismatches`` are claims that differ from the tree (the plan rewrites them)."""
    texts: Dict[str, str]
    rewrites: List[Tuple[str, str, int, int]]  # (manifest, measure, old number, new number)
    refusals: List[CountRefusal]
    mismatches: List[str]


def _spell_like(value: int, token: str) -> str:
    """The word for ``value`` in the case style of ``token`` (lower, Capitalised or UPPER)."""
    word = _SPELLED[value]
    if token.isupper():
        return word.upper()
    return word.capitalize() if token[:1].isupper() else word


def plan_counts(texts: Dict[str, str], measures: Optional[Dict[str, int]], oracle_error: str = "") -> CountPlan:
    """The one Count verdict: equality of every claim with its measure (by both readers), noun presence, and the
    refusals that stop a refresh. Changes only the number of a claim inside a description value (I-2).

    ``measures`` maps skills, agents and hooks to their counts; None means the tree listing failed
    (``oracle_error`` says why). A manifest that is not JSON raises ``ValueError`` (the check could not run).
    """
    out_texts = dict(texts)
    rewrites: List[Tuple[str, str, int, int]] = []
    refusals: List[CountRefusal] = []
    mismatches: List[str] = []
    if measures is None:
        refusals.append(CountRefusal("oracle-unreadable", "read", "-", oracle_error or "the tree listing failed"))
        return CountPlan(out_texts, rewrites, refusals, mismatches)
    usable: Dict[str, int] = {}
    for measure in COUNT_MEASURES:
        if measures.get(measure, 0) > 0:
            usable[measure] = measures[measure]
        else:
            refusals.append(CountRefusal("oracle-empty", "read", "-", "the tree lists no %s" % measure))
    for name, text in texts.items():
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("%s is not a JSON object" % name)
        stated = set()
        for description in manifest_descriptions(data):
            matches = list(_CLAIM_RE.finditer(description))
            if not matches and not _counts(_COUNT_RE, description):
                continue
            usable_edits: List[Tuple[int, int, str, str, int, int]] = []
            claim_hooks = [WORDS[m.group(1).lower()] if not m.group(1).isdigit() else int(m.group(1))
                           for m in matches if _NOUN_MEASURE[m.group(2).lower()] == "hooks"]
            hook_read = _counts(_COUNT_RE, description)
            disagree = [n for _t, n in hook_read] != claim_hooks
            if disagree:
                refusals.append(CountRefusal(
                    "count-reader-disagreement", "description", name,
                    "the hook reader reads %s, the claim reader reads %s, in %r"
                    % ([t for t, _n in hook_read], claim_hooks, description)))
                if "hooks" in usable:
                    mismatches += ["%s: says '%s' (%d) but .claude/hooks/ has %d hook files" % (name, t, n, usable["hooks"])
                                   for t, n in hook_read if n != usable["hooks"]]
            for m in matches:
                noun = m.group(2).lower()
                stated.add(noun)
                measure = _NOUN_MEASURE[noun]
                if measure not in COUNT_MEASURES:
                    refusals.append(CountRefusal(
                        "count-unrefreshable-noun", "description", name,
                        "'%s' is a claim of the %s measure, which no refresh can write"
                        % (re.sub(r"\s+", " ", m.group(0)), measure)))
                    continue
                if measure not in usable:
                    continue
                token = m.group(1)
                value = int(token) if token.isdigit() else WORDS[token.lower()]
                expected = usable[measure]
                if value == expected:
                    continue
                mismatches.append("%s: says '%s' (%d) but the tree has %d %s"
                                  % (name, re.sub(r"\s+", " ", m.group(0)), value, expected, measure))
                if token.isdigit():
                    written = str(expected)
                elif 1 <= expected <= max(WORDS.values()):
                    written = _spell_like(expected, token)
                else:
                    refusals.append(CountRefusal(
                        "count-unwritable", "description", name,
                        "'%s' is spelled out and %d has no word (one to twenty only); write the count in digits"
                        % (re.sub(r"\s+", " ", m.group(0)), expected)))
                    continue
                usable_edits.append((m.start(1), m.end(1), written, measure, value, expected))
            candidates = {json.dumps(description, ensure_ascii=False), json.dumps(description)}
            found = [(c, text.count(c)) for c in sorted(candidates)]
            total = sum(n for _c, n in found)
            if total != 1:
                refusals.append(CountRefusal(
                    "description-not-located", "description", name,
                    "the description %r is found %d times in the file text (exactly once is required)"
                    % (description, total)))
                continue
            if disagree or not usable_edits:
                continue
            updated = description
            for start, end, written, _measure, _old, _new in sorted(usable_edits, reverse=True):
                updated = updated[:start] + written + updated[end:]
            old_encoded = next(c for c, n in found if n == 1)
            new_encoded = json.dumps(updated, ensure_ascii=(old_encoded == json.dumps(description)))  # same spelling
            out_texts[name] = out_texts[name].replace(old_encoded, new_encoded, 1)
            rewrites += [(name, measure, old, new) for _s, _e, _w, measure, old, new in sorted(usable_edits)]
        for noun in MANIFEST_COUNT_NOUNS.get(name, ()):
            if noun not in stated:
                refusals.append(CountRefusal("count-missing", "description", name,
                                             "no description states a count for '%s'" % noun))
    return CountPlan(out_texts, rewrites, refusals, mismatches)


def count_exit_code(plan: CountPlan) -> int:
    """I-4: 2 for a ``read`` refusal; 1 for any other refusal or an equality failure; 0 when the verdict holds."""
    if any(r.kind == "read" for r in plan.refusals):
        return 2
    return 1 if plan.refusals or plan.mismatches else 0


def tree_measures(cwd: Optional[str] = None) -> Tuple[Optional[Dict[str, int]], str]:
    """(measures, "") from HEAD's tree, or (None, why) when the listing fails."""
    try:
        paths = tree_paths(cwd)
    except (subprocess.CalledProcessError, OSError) as exc:
        stderr = getattr(exc, "stderr", None) or b""
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", "replace")
        return None, "%s: %s" % (exc, stderr.strip())
    return {measure: measure_count(measure, paths) for measure in COUNT_MEASURES}, ""


def _head_manifest_texts(cwd: Optional[str] = None) -> Dict[str, str]:
    """Each manifest as HEAD holds it, decoded as UTF-8 (a decode failure is a ``ValueError``)."""
    return {name: subprocess.run(_git_command("show", "HEAD:" + name), capture_output=True, check=True,
                                 cwd=cwd).stdout.decode("utf-8") for name in MANIFESTS}


def _disk_manifest_texts() -> Dict[str, str]:
    texts = {}
    for name in MANIFESTS:
        with open(name, encoding="utf-8", newline="") as handle:
            texts[name] = handle.read()
    return texts


def report_plan(plan: CountPlan, label: str) -> None:
    """Print every refusal (and, for a check, every equality failure) in one line each."""
    for refusal in plan.refusals:
        print("VERSION BUMP: %s (%s): %s: %s" % (label, refusal.reason, refusal.manifest, refusal.detail))


def head_count_verdict(cwd: Optional[str] = None) -> int:
    """The Count verdict on HEAD's manifests and HEAD's tree, printed; the exit code per I-4."""
    try:
        texts = _head_manifest_texts(cwd)
        measures, error = tree_measures(cwd)
        plan = plan_counts(texts, measures, error)
    except (subprocess.CalledProcessError, OSError, ValueError, KeyError) as exc:
        print("VERSION BUMP: the count check could not run: %s" % exc)
        return 2
    report_plan(plan, "count check refused")
    for line in plan.mismatches:
        print("VERSION BUMP: count differs from the tree: " + line)
    code = count_exit_code(plan)
    if code == 0 and measures is not None:
        print("VERSION BUMP: manifest counts match the tree (%s)"
              % ", ".join("%d %s" % (measures[m], m) for m in COUNT_MEASURES))
    return code


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="origin/master")
    parser.add_argument("--default-branch", default="master")
    parser.add_argument("--head-ref", default="")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--exact", action="store_true")
    modes.add_argument("--raise", dest="raise_version", action="store_true")
    modes.add_argument("--counts", action="store_true")
    parser.add_argument("--manifest-counts", action="store_true")
    parser.add_argument("--git-program", default=None,
                        help="the absolute path of the git program every git process of this script starts")
    args = parser.parse_args(argv)
    global _git_program
    _git_program = None
    if args.git_program is not None:
        # C13: an absolute path to an existing file, or nothing runs: a relative one would be looked up from the
        # working folder, which is the planted-program case this option closes.
        if not (os.path.isabs(args.git_program) and os.path.isfile(args.git_program)):
            print("VERSION BUMP: --git-program must be the absolute path of an existing file: %s" % args.git_program)
            return 2
        _git_program = args.git_program
    if args.manifest_counts and not (args.exact or args.raise_version):
        print("VERSION BUMP: --manifest-counts rides on --raise or --exact only (use --counts to check the counts alone)")
        return 2
    if args.counts:
        return head_count_verdict()  # HEAD's manifests and HEAD's tree: no version, no base, no origin ref
    args.default_branch = args.default_branch.strip()  # one value for the ref and the check
    if not args.default_branch:
        # origin/ would make every base "non-default" and skip the check: the check could not run, never an allow.
        print("VERSION BUMP: the default branch is unknown (--default-branch is empty)")
        return 2
    default_ref = "origin/" + args.default_branch
    if args.exact and args.manifest_counts:
        # The version verdict and the Count verdict are both printed; the exit is the higher of the two codes (I-4).
        try:
            default = {m: _git("show", "%s:%s" % (default_ref, m)) for m in MANIFESTS}
            head = {m: _git("show", "HEAD:" + m) for m in MANIFESTS}
            code, message = evaluate_exact(versions_in(default), versions_in(head))
        except (subprocess.CalledProcessError, OSError, ValueError, KeyError) as exc:
            code, message = 2, "the version check could not run: %s" % exc
        print("VERSION BUMP: " + message)
        return max(code, head_count_verdict())
    try:
        if args.exact or args.raise_version:
            default = {m: _git("show", "%s:%s" % (default_ref, m)) for m in MANIFESTS}
            refreshed = None
            plan = None
            if args.raise_version:
                wanted = exact_version(versions_in(default))
                if wanted is None:
                    code, message = 2, "a version could not be read (default branch %s)" % versions_in(default)
                else:
                    if args.manifest_counts:
                        measures, error = tree_measures()
                        plan = plan_counts(_disk_manifest_texts(), measures, error)
                        if plan.refusals:
                            report_plan(plan, "count refresh refused")
                            return 2 if any(r.kind == "read" for r in plan.refusals) else 1
                        refreshed = plan.texts
                    raised = raise_manifests(wanted, refreshed)
                    code, message = 0, "manifests %s %s" % ("raised to" if raised else "already at", wanted)
                    if plan is not None and plan.rewrites:
                        message += "; refreshed %s" % ", ".join(
                            "%s %s %d -> %d" % (m, measure, old, new) for m, measure, old, new in plan.rewrites)
            else:
                head = {m: _git("show", "HEAD:" + m) for m in MANIFESTS}
                code, message = evaluate_exact(versions_in(default), versions_in(head))
            print("VERSION BUMP: " + message)
            return code
        if args.head_ref and not TASK_HEAD.match(args.head_ref) and is_non_default_base(args.base, default_ref):
            print("VERSION BUMP: %s is not a task branch and its base is not %s; not checked" % (args.head_ref, default_ref))
            return 0
        if is_parent_mode(args.head_ref, args.base, default_ref):
            allowed = parent_allowed_versions(args.base, default_ref)
            head = {m: _git("show", "HEAD:" + m) for m in MANIFESTS}
            code, message = evaluate_parent(versions_in(head), allowed)
            print("VERSION BUMP: " + message)
            return code
        changed = [ln for ln in _git("diff", "--name-only", args.base + "...HEAD").splitlines() if ln]
        base = {m: _git("show", "%s:%s" % (args.base, m)) for m in MANIFESTS}
        head = {m: _git("show", "HEAD:" + m) for m in MANIFESTS}
        code, message = evaluate(changed, versions_in(base), versions_in(head))
    except (subprocess.CalledProcessError, OSError, ValueError, KeyError) as exc:
        code, message = 2, "the version check could not run: %s" % exc
    print("VERSION BUMP: " + message)
    return code


if __name__ == "__main__":
    sys.exit(main())
