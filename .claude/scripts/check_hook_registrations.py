"""The Hook registration check: judge a project's settings file against its Hook registration profile.

Usage (read-only; nothing is written):
  py -3 -B .claude/scripts/check_hook_registrations.py --project <root> [--json]
  py -3 -B .claude/scripts/check_hook_registrations.py --settings <path> --hook-registration-profile <path> [--json]

Exit codes: 0 every Registration rule passed, 1 at least one rule failed, 2 the check could not run.
Exit 2 is never a pass: a missing, unreadable or unimportable input is refused by name.

The five Registration rules (one pure function each, evaluated together, never short-circuited):
  row-count-unchanged, rows-unchanged-apart-from-if, if-keys-unchanged,
  every-registration-profiled-or-excluded, every-exclusion-matches-a-row.

A vendored copy needs five files in one folder: check_hook_registrations.py,
auto_improve_finish_install.py, pr_merged.py, plugin_doctor.py and check_version_bump.py.
The Hook registration profile is written by ``auto_improve_finish_install.py record-registrations``.
This module also owns the one Settings shape validator (``load_settings``) that the recorder reuses.
"""
import sys

# Statement one: nothing below may leave a __pycache__ beside a vendored copy. The flag has to be
# set before the guarded dependency load, because that load caches the installer module otherwise.
sys.dont_write_bytecode = True

import argparse
import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# The checker's own folder holds its four dependencies (a one-shot process; the folder is its own).
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

VENDORED_FILES: Tuple[str, ...] = (
    "check_hook_registrations.py",
    "auto_improve_finish_install.py",
    "pr_merged.py",
    "plugin_doctor.py",
    "check_version_bump.py",
)

_IMPORT_FAILURE: Optional[BaseException] = None
_iter_hooks: Any = None
_hook_key: Any = None
_compare_extras: Any = None
try:
    from auto_improve_finish_install import _iter_hooks, _hook_key, _compare_extras  # noqa: E402
except Exception as _exc:  # ImportError is the expected case; anything else is an internal error
    _IMPORT_FAILURE = _exc

# --- Constants -------------------------------------------------------------------------

EXIT_PASS: int = 0
EXIT_FAIL: int = 1
EXIT_COULD_NOT_CHECK: int = 2

PROFILE_FORMAT: int = 1
SETTINGS_PATH_VALUE: str = ".claude/settings.json"
PROFILE_FILE_NAME: str = ".claude/hook-registration-profile.json"

REFUSAL_CODES: Tuple[str, ...] = (
    "paths-not-given",
    "settings-missing",
    "settings-unreadable",
    "hook-registration-profile-missing",
    "hook-registration-profile-unreadable",
    "checker-dependency-missing",
    "checker-internal-error",
)

RECORD_COMMAND: str = "py -3 .claude/scripts/auto_improve_finish_install.py record-registrations --project <root>"

# --- Errors ----------------------------------------------------------------------------


class SettingsError(Exception):
    """The one error ``load_settings`` raises: a kind (encoding, json, duplicate-key, not-object,
    shape) and the JSON path of the breach."""

    def __init__(self, kind: str, path: str, message: str) -> None:
        super().__init__("%s at %s" % (message, path))
        self.kind = kind
        self.path = path
        self.detail = message


class ProfileError(Exception):
    """The Hook registration profile cannot be read (an RP invariant or the file itself)."""


# --- Strict JSON reading ---------------------------------------------------------------


class _DupDict(dict):
    """A parsed object that had a repeated key; only ever seen between parse and refusal."""

    dup_key: str = ""


def _pairs(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    dup: Optional[str] = None
    for key, value in pairs:
        if key in out and dup is None:
            dup = key
        out[key] = value
    if dup is None:
        return out
    marked = _DupDict(out)
    marked.dup_key = dup
    return marked


def _find_duplicate(value: Any, path: str) -> Optional[Tuple[str, str]]:
    if isinstance(value, _DupDict):
        return path, value.dup_key
    if isinstance(value, dict):
        for key, child in value.items():
            found = _find_duplicate(child, "%s.%s" % (path, key))
            if found:
                return found
    elif isinstance(value, list):
        for i, child in enumerate(value):
            found = _find_duplicate(child, "%s[%d]" % (path, i))
            if found:
                return found
    return None


def _parse_json(data: bytes) -> Any:
    """Parse UTF-8 JSON (a byte-order mark is accepted), refusing a duplicate key at any level."""
    try:
        text = bytes(data).decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SettingsError("encoding", "$", "the file is not UTF-8 text (%s)" % exc.reason)
    if "\x00" in text:
        raise SettingsError("encoding", "$", "the file holds NUL characters (UTF-16 text?); save it as UTF-8")
    try:
        value = json.loads(text, object_pairs_hook=_pairs)
    except (ValueError, RecursionError) as exc:
        raise SettingsError("json", "$", "the file is not valid JSON (%s)" % exc)
    found = _find_duplicate(value, "$")
    if found:
        raise SettingsError("duplicate-key", found[0], "the key %r appears twice" % found[1])
    return value


# --- The Settings shape validator ------------------------------------------------------


def _shape(path: str, message: str) -> SettingsError:
    return SettingsError("shape", path, message)


def load_settings(data: bytes) -> Dict[str, Any]:
    """The one reader of the Settings shape. Validates the whole ``hooks`` tree before any row is read.

    A file with no ``hooks`` key is valid and has zero rows. Group keys other than ``matcher`` and
    ``hooks`` are not judged."""
    settings = _parse_json(data)
    if not isinstance(settings, dict):
        raise SettingsError("not-object", "$", "the settings file must be a JSON object")
    if "hooks" not in settings:
        return settings
    hooks = settings["hooks"]
    if not isinstance(hooks, dict):
        raise _shape("$.hooks", "hooks must be an object")
    for event, groups in hooks.items():
        epath = "$.hooks.%s" % event
        if not isinstance(groups, list):
            raise _shape(epath, "an event value must be a list of groups")
        for gi, group in enumerate(groups):
            gpath = "%s[%d]" % (epath, gi)
            if not isinstance(group, dict):
                raise _shape(gpath, "a group must be an object")
            if "matcher" in group and not isinstance(group["matcher"], str):
                raise _shape(gpath + ".matcher", "matcher must be a string")
            if "hooks" not in group:
                raise _shape(gpath + ".hooks", "a group must carry a hooks list")
            if not isinstance(group["hooks"], list):
                raise _shape(gpath + ".hooks", "a group's hooks must be a list")
            for hi, handler in enumerate(group["hooks"]):
                hpath = "%s.hooks[%d]" % (gpath, hi)
                if not isinstance(handler, dict):
                    raise _shape(hpath, "a handler must be an object")
                if not isinstance(handler.get("type"), str):
                    raise _shape(hpath + ".type", "a handler needs a string type")
                if handler["type"] != "command":
                    continue
                if not isinstance(handler.get("command"), str):
                    raise _shape(hpath + ".command", "a command handler needs a string command")
                if "args" in handler:
                    args = handler["args"]
                    if not isinstance(args, list):
                        raise _shape(hpath + ".args", "args must be a list of strings")
                    for ai, arg in enumerate(args):
                        if not isinstance(arg, str):
                            raise _shape("%s.args[%d]" % (hpath, ai), "each arg must be a string")
    return settings


# --- Registration rows -----------------------------------------------------------------


@dataclass(frozen=True)
class Row:
    """One handler object inside ``hooks.<event>[n].hooks[]``."""

    event: str
    matcher: str
    identity: str
    occurrence: int
    hook: Dict[str, Any] = field(compare=False)

    @property
    def key(self) -> Tuple[str, str, str, int]:
        return (self.event, self.matcher, self.identity, self.occurrence)


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _identity_text(event: str, hook: Dict[str, Any]) -> str:
    hook_type = hook.get("type")
    if hook_type == "command":
        parsed = _hook_key(hook)
        if parsed is not None:
            return "|".join((event, parsed[0]) + tuple(_compare_extras(parsed[1])))
        parts = [str(hook.get("command"))]
        if isinstance(hook.get("args"), list):
            parts += [str(a) for a in hook["args"]]
        return "command:" + " ".join(parts)
    return "%s:%s" % (hook_type, _canon({k: v for k, v in hook.items() if k != "if"}))


def read_rows(settings: Any) -> List[Row]:
    """Every registration row of a validated settings object, in file order."""
    seen: Dict[Tuple[str, str, str], int] = {}
    rows: List[Row] = []
    for event, matcher, hook in _iter_hooks(settings):
        matcher_text = matcher if isinstance(matcher, str) else ""
        identity = _identity_text(event, hook)
        triple = (event, matcher_text, identity)
        seen[triple] = seen.get(triple, 0) + 1
        rows.append(Row(event, matcher_text, identity, seen[triple], hook))
    return rows


# --- The Hook registration profile -----------------------------------------------------


def _matches(exclusion: Dict[str, Any], event: str, matcher: str, identity: str) -> bool:
    return (exclusion["event"] == event and exclusion["identity"] == identity
            and ("matcher" not in exclusion or exclusion["matcher"] == matcher))


def _row_without_if(row: Row) -> Dict[str, Any]:
    return {k: copy.deepcopy(v) for k, v in row.hook.items() if k != "if"}


def build_hook_registration_profile(settings: Any, previous: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Pure function of the settings rows and the existing Exclusions (kept verbatim, stale ones too)."""
    rows = read_rows(settings)
    excluded = copy.deepcopy(previous["excluded"]) if previous else []
    registrations: List[Dict[str, Any]] = []
    for row in rows:
        if any(_matches(ex, row.event, row.matcher, row.identity) for ex in excluded):
            continue
        profiled: Dict[str, Any] = {
            "event": row.event, "matcher": row.matcher, "identity": row.identity,
            "occurrence": row.occurrence, "row": _row_without_if(row),
        }
        if "if" in row.hook:
            profiled["if"] = copy.deepcopy(row.hook["if"])
        registrations.append(profiled)
    return {
        "format": PROFILE_FORMAT,
        "settings_path": SETTINGS_PATH_VALUE,
        "row_count": len(rows),
        "registrations": registrations,
        "excluded": excluded,
    }


def serialise(hook_registration_profile: Dict[str, Any]) -> bytes:
    """RP-2: UTF-8 without a byte-order mark, two-space indent, keys in order, one trailing newline."""
    return (json.dumps(hook_registration_profile, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _is_int(value: Any) -> bool:
    return type(value) is int


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise ProfileError(message)


def _validate_profile(profile: Any) -> Dict[str, Any]:
    _need(isinstance(profile, dict), "the hook registration profile must be a JSON object")
    for name in ("format", "settings_path", "row_count", "registrations", "excluded"):
        _need(name in profile, "the hook registration profile lacks the field %r" % name)
    _need(_is_int(profile["format"]) and profile["format"] == PROFILE_FORMAT,
          "the hook registration profile has an unknown format %r" % (profile["format"],))
    _need(profile["settings_path"] == SETTINGS_PATH_VALUE, "settings_path must be %r" % SETTINGS_PATH_VALUE)
    _need(_is_int(profile["row_count"]) and profile["row_count"] >= 0, "row_count must be an integer >= 0")
    _need(isinstance(profile["registrations"], list), "registrations must be a list")
    _need(isinstance(profile["excluded"], list), "excluded must be a list")
    seen = set()
    for i, e in enumerate(profile["registrations"]):
        where = "registrations[%d]" % i
        _need(isinstance(e, dict), where + " must be an object")
        for name in ("event", "matcher", "identity", "occurrence", "row"):
            _need(name in e, "%s lacks the field %r" % (where, name))
        _need(all(isinstance(e[n], str) for n in ("event", "matcher", "identity")),
              where + ": event, matcher and identity must be strings")
        _need(_is_int(e["occurrence"]) and e["occurrence"] >= 1, where + ": occurrence must be an integer >= 1")
        _need(isinstance(e["row"], dict), where + ": row must be an object")
        key = (e["event"], e["matcher"], e["identity"], e["occurrence"])
        _need(key not in seen, "%s repeats an identity already profiled (RP-4): %s" % (where, e["identity"]))
        seen.add(key)
    exclusions = profile["excluded"]
    for i, ex in enumerate(exclusions):
        where = "excluded[%d]" % i
        _need(isinstance(ex, dict), where + " must be an object")
        for name in ("event", "identity"):
            _need(isinstance(ex.get(name), str), "%s lacks the string field %r" % (where, name))
        _need("matcher" not in ex or isinstance(ex["matcher"], str), where + ": matcher must be a string")
        _need(isinstance(ex.get("reason"), str) and ex["reason"].strip() != "",
              where + " needs a non-empty reason (RP-5)")
        for e in profile["registrations"]:
            _need(not _matches(ex, e["event"], e["matcher"], e["identity"]),
                  "%s excludes a row the profile expects (RP-6): %s" % (where, e["identity"]))
    for i, a in enumerate(exclusions):
        for j in range(i + 1, len(exclusions)):
            b = exclusions[j]
            if a["event"] == b["event"] and a["identity"] == b["identity"] and (
                    "matcher" not in a or "matcher" not in b or a["matcher"] == b["matcher"]):
                raise ProfileError("excluded[%d] and excluded[%d] can match the same row (RP-7): %s"
                                   % (i, j, a["identity"]))
    return profile


def load_hook_registration_profile(data: bytes) -> Dict[str, Any]:
    """Parse and validate a Hook registration profile; anything unreadable raises ProfileError."""
    try:
        parsed = _parse_json(data)
    except SettingsError as exc:
        raise ProfileError("%s: %s" % (exc.kind, exc))
    return _validate_profile(parsed)


# --- Registration rules ----------------------------------------------------------------

Finding = Dict[str, str]


@dataclass
class RuleResult:
    rule: str
    status: str
    findings: List[Finding] = field(default_factory=list)

    def to_json(self) -> Dict[str, Any]:
        return {"rule": self.rule, "status": self.status, "findings": self.findings}


def _finding(identity: str, detail: str) -> Finding:
    return {"identity": identity, "detail": detail}


def _rows_by_key(rows: List[Row]) -> Dict[Tuple[str, str, str, int], Row]:
    return {r.key: r for r in rows}


def _rule_row_count(rows: List[Row], profile: Dict[str, Any]) -> List[Finding]:
    if len(rows) == profile["row_count"]:
        return []
    return [_finding(SETTINGS_PATH_VALUE, "settings hold %d rows, the hook registration profile records %d"
                     % (len(rows), profile["row_count"]))]


def _rule_rows_unchanged(rows: List[Row], profile: Dict[str, Any]) -> List[Finding]:
    by_key = _rows_by_key(rows)
    out: List[Finding] = []
    for e in profile["registrations"]:
        row = by_key.get((e["event"], e["matcher"], e["identity"], e["occurrence"]))
        if row is None:
            out.append(_finding(e["identity"], "missing (event %s, matcher %r, occurrence %d)"
                                % (e["event"], e["matcher"], e["occurrence"])))
            continue
        now = _row_without_if(row)
        if _canon(now) != _canon(e["row"]):
            keys = sorted(k for k in set(now) | set(e["row"])
                          if k not in now or k not in e["row"] or _canon(now[k]) != _canon(e["row"][k]))
            out.append(_finding(e["identity"], "differs from the recorded row in: " + ", ".join(keys)))
    return out


def _rule_if_keys(rows: List[Row], profile: Dict[str, Any]) -> List[Finding]:
    by_key = _rows_by_key(rows)
    out: List[Finding] = []
    for e in profile["registrations"]:
        row = by_key.get((e["event"], e["matcher"], e["identity"], e["occurrence"]))
        if row is None:
            continue
        recorded = _canon(e["if"]) if "if" in e else "absent"
        current = _canon(row.hook["if"]) if "if" in row.hook else "absent"
        if recorded != current:
            out.append(_finding(e["identity"], "if was %s, now %s" % (recorded, current)))
    return out


def _rule_every_row_profiled(rows: List[Row], profile: Dict[str, Any]) -> List[Finding]:
    profiled = {(e["event"], e["matcher"], e["identity"], e["occurrence"]) for e in profile["registrations"]}
    out: List[Finding] = []
    for row in rows:
        if row.key in profiled:
            continue
        if any(_matches(ex, row.event, row.matcher, row.identity) for ex in profile["excluded"]):
            continue
        out.append(_finding(row.identity, "not in the hook registration profile (event %s, matcher %r, "
                            "occurrence %d); record it or exclude it" % (row.event, row.matcher, row.occurrence)))
    return out


def _rule_every_exclusion_matches(rows: List[Row], profile: Dict[str, Any]) -> List[Finding]:
    out: List[Finding] = []
    for ex in profile["excluded"]:
        if not any(_matches(ex, r.event, r.matcher, r.identity) for r in rows):
            out.append(_finding(ex["identity"], "excluded (event %s%s) but no settings row matches; "
                                "remove it from the hook registration profile"
                                % (ex["event"], ", matcher %r" % ex["matcher"] if "matcher" in ex else "")))
    return out


# The extension seam: a new rule is one entry here, one pure function, and one test pair.
RULES: Tuple[Tuple[str, Callable[[List[Row], Dict[str, Any]], List[Finding]]], ...] = (
    ("row-count-unchanged", _rule_row_count),
    ("rows-unchanged-apart-from-if", _rule_rows_unchanged),
    ("if-keys-unchanged", _rule_if_keys),
    ("every-registration-profiled-or-excluded", _rule_every_row_profiled),
    ("every-exclusion-matches-a-row", _rule_every_exclusion_matches),
)


def check(settings: Any, hook_registration_profile: Dict[str, Any]) -> List[RuleResult]:
    """Evaluate all five rules, never short-circuiting."""
    rows = read_rows(settings)
    results: List[RuleResult] = []
    for name, rule in RULES:
        findings = rule(rows, hook_registration_profile)
        results.append(RuleResult(name, "fail" if findings else "pass", findings))
    return results


# --- Report and command line -----------------------------------------------------------


def _remedy_for_failure() -> str:
    return ("If the registration change is deliberate, re-record the hook registration profile with `%s` "
            "(preview, then --apply) and commit it in the same pull request; otherwise revert the change. "
            "A stale Exclusion is removed by hand." % RECORD_COMMAND)


def _report(status: str, settings: Optional[Path], profile: Optional[Path],
            rules: Optional[List[RuleResult]] = None, refusal: Optional[Dict[str, str]] = None,
            remedy: str = "") -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "status": status,
        "settings": str(settings) if settings is not None else None,
        "hook_registration_profile": str(profile) if profile is not None else None,
        "rules": [r.to_json() for r in rules or []],
    }
    if refusal is not None:
        report["refusal"] = refusal
    report["remedy"] = remedy
    return report


def _text(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    if "refusal" in report:
        lines.append("COULD-NOT-CHECK %s: %s" % (report["refusal"]["code"], report["refusal"]["message"]))
    for r in report["rules"]:
        if r["status"] == "pass":
            lines.append("PASS " + r["rule"])
        else:
            lines.append("FAIL %s: %s" % (r["rule"], "; ".join("%s: %s" % (f["identity"], f["detail"])
                                                               for f in r["findings"])))
    if report["remedy"]:
        lines.append("Remedy: " + report["remedy"])
    return "\n".join(lines)


def _refuse(code: str, message: str, path: Optional[Path], remedy: str,
            settings: Optional[Path], profile: Optional[Path]) -> Dict[str, Any]:
    return _report("could-not-check", settings, profile,
                   refusal={"code": code, "message": message, "path": str(path) if path is not None else ""},
                   remedy=remedy)


def _dependency_refusal(exc: BaseException, settings: Optional[Path], profile: Optional[Path]) -> Dict[str, Any]:
    if isinstance(exc, ImportError):
        module = getattr(exc, "name", None) or str(exc)
        return _refuse(
            "checker-dependency-missing",
            "cannot import the module %r that this check needs. Vendor all five files together into one "
            "folder: %s" % (module, ", ".join(VENDORED_FILES)),
            None, "Copy the five files listed above next to check_hook_registrations.py, then rerun.",
            settings, profile)
    return _refuse("checker-internal-error", "%s: %s" % (type(exc).__name__, exc), None,
                   "Report this failure; the check could not run.", settings, profile)


def _read(path: Path) -> Tuple[Optional[bytes], str]:
    """(bytes, "") or (None, "missing" / "unreadable")."""
    try:
        return path.read_bytes(), ""
    except (FileNotFoundError, NotADirectoryError):
        return None, "missing"
    except OSError:
        return None, "unreadable"


def _run(args: argparse.Namespace) -> Tuple[int, Dict[str, Any]]:
    settings_path = Path(args.settings) if args.settings else (
        Path(args.project) / ".claude" / "settings.json" if args.project else None)
    profile_path = Path(args.hook_registration_profile) if args.hook_registration_profile else (
        Path(args.project) / ".claude" / "hook-registration-profile.json" if args.project else None)
    if settings_path is None or profile_path is None:
        return EXIT_COULD_NOT_CHECK, _refuse(
            "paths-not-given", "give --project <root>, or both --settings and --hook-registration-profile; "
            "no environment variable or working directory is consulted", None,
            "Run: py -3 -B .claude/scripts/check_hook_registrations.py --project <root>", settings_path, profile_path)
    if _IMPORT_FAILURE is not None:
        return EXIT_COULD_NOT_CHECK, _dependency_refusal(_IMPORT_FAILURE, settings_path, profile_path)

    def refuse(code: str, message: str, path: Path, remedy: str) -> Tuple[int, Dict[str, Any]]:
        return EXIT_COULD_NOT_CHECK, _refuse(code, message, path, remedy, settings_path, profile_path)

    data, problem = _read(settings_path)
    if data is None:
        if problem == "missing":
            return refuse("settings-missing", "the settings file does not exist: %s" % settings_path, settings_path,
                          "Create .claude/settings.json, or point --project at the right folder.")
        return refuse("settings-unreadable", "the settings file cannot be read: %s" % settings_path, settings_path,
                      "Fix the file permissions, then rerun.")
    try:
        settings = load_settings(data)
    except SettingsError as exc:
        return refuse("settings-unreadable", "%s (%s): %s" % (settings_path, exc.kind, exc), settings_path,
                      "Fix the settings file (UTF-8 JSON, no repeated keys, valid hooks tree), then rerun.")

    data, problem = _read(profile_path)
    if data is None:
        if problem == "missing":
            return refuse("hook-registration-profile-missing",
                          "the hook registration profile does not exist: %s" % profile_path, profile_path,
                          "Record it with `%s`, review it, and commit it." % RECORD_COMMAND)
        return refuse("hook-registration-profile-unreadable",
                      "the hook registration profile cannot be read: %s" % profile_path, profile_path,
                      "Fix the file permissions, then rerun.")
    try:
        profile = load_hook_registration_profile(data)
    except ProfileError as exc:
        return refuse("hook-registration-profile-unreadable", "%s: %s" % (profile_path, exc), profile_path,
                      "Repair the hook registration profile by hand; never delete it, which would lose its "
                      "Exclusions. A fresh `%s` refuses to overwrite an unreadable file." % RECORD_COMMAND)

    results = check(settings, profile)
    failed = any(r.status == "fail" for r in results)
    report = _report("fail" if failed else "pass", settings_path, profile_path, results,
                     remedy=_remedy_for_failure() if failed else "")
    return (EXIT_FAIL if failed else EXIT_PASS), report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_hook_registrations.py",
        description="Judge a project's .claude/settings.json against its hook registration profile.")
    parser.add_argument("--project", help="project root holding .claude/settings.json and the profile")
    parser.add_argument("--settings", help="path to the settings file")
    parser.add_argument("--hook-registration-profile", help="path to the hook registration profile")
    parser.add_argument("--json", action="store_true", help="print the check report as JSON")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        code, report = _run(args)
    except Exception as exc:  # one line with type and message, never a traceback
        code = EXIT_COULD_NOT_CHECK
        report = _refuse("checker-internal-error", "%s: %s" % (type(exc).__name__, exc), None,
                         "Report this failure; the check could not run.", None, None)
    print(json.dumps(report, indent=2) if args.json else _text(report))
    return code


if __name__ == "__main__":
    sys.exit(main())
