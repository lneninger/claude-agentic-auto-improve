#!/usr/bin/env python3
"""The memory adapter: the one place that knows the Central Memory System's tool names and shapes.

Contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md (Data Shapes, Commands, Failure Modes).

A Central Memory System is a separate product reached over MCP. This script never calls it: a Python script
cannot use the session's MCP connections, so the model makes the call and this script renders the request,
neutralises the response, selects what may be sent back, and records the outcome in the Work Item Brief.

Subcommands (every one takes --project explicitly; no profile and no token list is ever searched for):

    status           --project P                                    always exits 0; disabled prints no line
    retrieve-request --project P --brief B
    normalise        --project P --input F
    capture-candidates --project P --contract SLUG --run-report F [--default-branch NAME]
    capture-request  --project P --candidate F
    record           --project P --brief B --outcome F [--receipts --run-report F]
    check-contract   --project P --brief B --contract C
    changed-items    --project P --input F

Output is one JSON object on stdout. A refusal prints {"refused": "<name>", "detail": ...} and exits 1. Whatever a
caller sees, a non-zero exit, a crash, a timeout or a missing script reads as "memory off".

Only `record` writes, and only the one brief it is given (replace-then-rename). With memory disabled it refuses
`not-enabled` and writes nothing, so a project that never switched memory on sees no change in any brief. With
memory unconfigured it writes the one `Memory: unconfigured (<reason>)` line, the reason read from the profile.

The registry readers (entry_blocks, journal_entries), the registry file lister (registry_files_in), the profile slot
reader (load_slot), the brief selector (select_linked_brief) and the shipped-path test (is_shipped) are other scripts'
functions. They are bound fail-soft with getattr, so a missing or stale one degrades to a refusal, never a crash. This
file parses no registry text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Append, never insert: a script that shares a name with a library must not shadow it.
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.append(_SCRIPTS_DIR)


def _bind(module_name: str, *names: str) -> Dict[str, Any]:
    try:
        module = __import__(module_name)
    except Exception:  # a stale or missing sibling script must not take the adapter down
        return {name: None for name in names}
    return {name: getattr(module, name, None) for name in names}


_PR = _bind("pr_merged", "load_slot", "select_linked_brief", "parse_brief_frontmatter", "default_branch_or_none")
_GRD = _bind("generate_registry_digest", "entry_blocks", "journal_entries", "BULLET")
_RL = _bind("_registry_layout", "registry_files_in")
_CVB = _bind("check_version_bump", "is_shipped")

# --- shape profiles ----------------------------------------------------------------------------------------------
# A new response shape is one new entry here plus a `memory.shape` slot value. v0 is PROVISIONAL: the Central Memory
# System's schema does not exist yet, so v0 is the adapter's best statement of it and is replaced, not extended.
SHAPES: Dict[str, Dict[str, Any]] = {
    "v0": {
        "provisional": True,
        "default_retrieve_tool": "memory_retrieve",
        "default_capture_tool": "memory_capture",
        "supports_deadline": True,
        "deadline_seconds": 20,
        "limit": 8,
    },
}

MAX_ITEMS = 8
MAX_QUERY_CHARS = 1500
MAX_TITLE = 120
MAX_SUMMARY = 600
MAX_CONFLICTS = 10
SCOPES = ("global", "project")
STATUSES = ("proposed", "validated", "superseded", "conflicting")
PROVENANCES = ("user-decision", "source-code-fact", "test-confirmed", "ai-hypothesis")
CAPTURABLE = ("user-decision", "source-code-fact")
DECISIONS = ("applies", "does-not-apply")
REPORT_KINDS = ("changed", "conflicting", "superseded")
STATES = ("enabled", "unconfigured", "unavailable")
REASONS = ("profile-absent", "slot-unset", "shape-unknown", "tool-absent", "call-failed", "timeout",
           "malformed-response")
REJECTIONS = ("not-an-object", "invalid-id", "invalid-version", "invalid-scope", "invalid-status", "duplicate",
              "over-limit")
SAFE_TOKEN = re.compile(r"[A-Za-z0-9._:/-]{1,128}")        # no "@": <id>@<version> always splits at its one "@"
KEY_RE = re.compile(r"[0-9a-f]{40}")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
SECTION = "## Memory used"
_TOKEN = r"[A-Za-z0-9._:/-]{1,128}"
RETRIEVED_LINE = re.compile(r"^Retrieved:[ \t]+(%s)@(%s)[ \t]*\|[ \t]*[a-z]+[ \t]*\|[ \t]*[a-z]+[ \t]*\|[ \t]*"
                            r"(applies|does-not-apply)\b" % (_TOKEN, _TOKEN), re.M)
RECEIPT_KEY_LINE = re.compile(r"^(?:Captured|Not sent):[ \t]+([0-9a-f]{40})\b", re.M)
MEMORY_ITEM_LINE = re.compile(r"Memory item[ \t]+(%s)@(%s)" % (_TOKEN, _TOKEN))


class Refusal(Exception):
    """A named, expected refusal. Exits 1; the caller treats it as 'not done', never as a crash."""

    def __init__(self, name: str, detail: str = "") -> None:
        super().__init__(name)
        self.name = name
        self.detail = detail


class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # argparse would print and exit; we want a value
        raise UsageError(message)


def today() -> str:
    return date.today().isoformat()


# --- field rules (every field a server returns is untrusted) -------------------------------------------------------
def safe_token(value: Any) -> Optional[str]:
    """An id, version or reference part that matches the safe pattern, else None. Never contains '@'."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        value = str(value)
    if isinstance(value, str) and SAFE_TOKEN.fullmatch(value):
        return value
    return None


def clean_text(value: Any, limit: int) -> str:
    """One line of data: separators and control characters removed, leading markers stripped, capped.

    Pipes and backticks inside the text are replaced too, because the text is later placed between pipe
    separators on one brief line and must not break out of its field.
    """
    if not isinstance(value, str):
        return ""
    chars = []
    for ch in value:
        category = unicodedata.category(ch)
        if category in ("Cc", "Zl", "Zp"):
            chars.append(" ")
        elif category == "Cf":
            continue
        else:
            chars.append(ch)
    text = " ".join("".join(chars).split()).lstrip("#>|-` \t")
    text = text.replace("|", "/").replace("`", "'")
    return text[:limit].rstrip()


def safe_date(value: Any) -> str:
    return value if isinstance(value, str) and DATE_RE.fullmatch(value) else today()


def split_reference(value: Any) -> Optional[str]:
    """'id@version' with both parts safe, else None. 'none', empty and missing read as no reference."""
    if value is None or (isinstance(value, str) and value.strip().lower() in ("", "none")):
        return "none"
    if isinstance(value, str) and value.count("@") == 1:
        left, right = value.split("@")
        if safe_token(left) and safe_token(right):
            return value
    return None


# --- configuration -----------------------------------------------------------------------------------------------
def tool_id(server: str, tool: str) -> str:
    # ASSUMED host form mcp__<server>__<tool>; verified by the stub-server trial before memory.shape is set.
    return "mcp__%s__%s" % (server, tool)


def _slot(profile_text: str, name: str) -> str:
    load_slot = _PR["load_slot"]
    values = load_slot(profile_text, name) if load_slot else ()
    return values[0].strip() if values and values[0].strip() else ""


def read_config(project: Path) -> Dict[str, Any]:
    """The Memory exchange outcome derived from the profile: disabled, unconfigured or enabled."""
    cfg: Dict[str, Any] = {"state": "disabled", "reason": "", "server": "", "retrieve_tool": "", "capture_tool": "",
                           "shape": "", "project_key": "", "capture": False, "date": today(), "line": ""}
    profile = Path(project) / ".claude" / "project-profile.md"
    try:
        text = profile.read_text(encoding="utf-8", errors="replace")
    except OSError:
        cfg["reason"] = "profile-absent"
        return cfg
    if _PR["load_slot"] is None:
        cfg["reason"] = "profile-absent"
        return cfg
    cfg["server"] = _slot(text, "memory.server")
    if not cfg["server"]:
        cfg["reason"] = "slot-unset"
        return cfg
    cfg["retrieve_tool"] = _slot(text, "memory.retrieve-tool")
    cfg["capture_tool"] = _slot(text, "memory.capture-tool")
    cfg["shape"] = _slot(text, "memory.shape")
    cfg["project_key"] = _slot(text, "memory.project-key")
    shape = SHAPES.get(cfg["shape"])
    if shape is None:
        cfg.update(state="unconfigured", reason="shape-unknown")
        cfg["line"] = "Memory: unconfigured (shape-unknown): set memory.shape to one of %s" % ", ".join(sorted(SHAPES))
        return cfg
    if not cfg["retrieve_tool"]:
        cfg.update(state="unconfigured", reason="tool-absent")
        cfg["line"] = ("Memory: unconfigured (tool-absent): set memory.retrieve-tool (shape %s default: %s)"
                       % (cfg["shape"], shape["default_retrieve_tool"]))
        return cfg
    cfg.update(state="enabled", capture=bool(cfg["capture_tool"]))
    cfg["line"] = "Memory: enabled (server %s, shape %s%s, capture %s)" % (
        cfg["server"], cfg["shape"], " provisional" if shape["provisional"] else "", "on" if cfg["capture"] else "off")
    return cfg


def public_status(cfg: Dict[str, Any]) -> Dict[str, Any]:
    shape = SHAPES.get(cfg["shape"]) or {}
    out = {"state": cfg["state"], "reason": cfg["reason"], "date": cfg["date"], "line": cfg["line"],
           "capture": cfg["capture"], "shape": cfg["shape"], "shape_provisional": bool(shape.get("provisional"))}
    if cfg["state"] == "enabled":
        out["server"] = cfg["server"]
        out["retrieve_tool_id"] = tool_id(cfg["server"], cfg["retrieve_tool"])
        if cfg["capture"]:
            out["capture_tool_id"] = tool_id(cfg["server"], cfg["capture_tool"])
        out["project_key"] = cfg["project_key"]
    return out


def require_enabled(cfg: Dict[str, Any]) -> None:
    if cfg["state"] != "enabled":
        raise Refusal("not-enabled", "memory state is %s" % cfg["state"])


def require_capture(cfg: Dict[str, Any]) -> None:
    if cfg["state"] != "enabled" or not cfg["capture"]:
        raise Refusal("capture-not-enabled", "memory.capture-tool is unset or memory is not enabled")


def _read_text(path: Path) -> Optional[str]:
    try:
        # Bytes, not read_text: universal newlines would hide a CRLF brief and rewrite its endings.
        return Path(path).read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return None


def _read_json(path: Path) -> Any:
    text = _read_text(path)
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def _resolve(project: Path, given: str) -> Path:
    path = Path(given)
    return path if path.is_absolute() else Path(project) / path


def _rel(project: Path, path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(Path(project).resolve()).as_posix()
    except (ValueError, OSError):
        return Path(path).as_posix()


# --- status ----------------------------------------------------------------------------------------------------
def cmd_status(args: argparse.Namespace) -> Tuple[int, Dict[str, Any]]:
    return 0, public_status(read_config(Path(args.project)))


# --- retrieve-request --------------------------------------------------------------------------------------------
def build_query(brief_text: str) -> str:
    """Brief title plus acceptance criteria plus affected areas, capped."""
    parse = _PR["parse_brief_frontmatter"]
    title = (parse(brief_text) or {}).get("title", "") if parse else ""
    parts: List[str] = [clean_text(title, 300)] if title else []
    in_criteria = False
    for line in brief_text.replace("\r\n", "\n").split("\n"):
        if line.startswith("## "):
            in_criteria = bool(re.match(r"##\s+Acceptance criteria", line, re.I))
            continue
        bullet = re.match(r"\s*[-*]\s+(?:\[[ xX]\]\s*)?(.+)$", line)
        if in_criteria and bullet:
            parts.append(clean_text(bullet.group(1), 400))
        elif "Affected areas" in line and ":" in line:
            parts.append("Affected areas: " + clean_text(line.split(":", 1)[1], 300))
    return "\n".join(p for p in parts if p)[:MAX_QUERY_CHARS]


def render_retrieve_request(cfg: Dict[str, Any], query: str) -> Dict[str, Any]:
    shape = SHAPES.get(cfg.get("shape", ""))
    if shape is None:
        raise Refusal("shape-unknown", "no shape profile named %r" % cfg.get("shape"))
    arguments: Dict[str, Any] = {"query": query, "scopes": list(SCOPES), "limit": shape["limit"]}
    if cfg.get("project_key"):
        arguments["project"] = cfg["project_key"]
    if shape["supports_deadline"]:
        arguments["deadline_seconds"] = shape["deadline_seconds"]
    return {"tool": tool_id(cfg["server"], cfg["retrieve_tool"]), "arguments": arguments, "shape": cfg["shape"],
            "shape_provisional": shape["provisional"]}


def cmd_retrieve_request(args: argparse.Namespace) -> Tuple[int, Dict[str, Any]]:
    project = Path(args.project)
    cfg = read_config(project)
    require_enabled(cfg)
    text = _read_text(_resolve(project, args.brief))
    if text is None:
        raise Refusal("brief-not-found", str(args.brief))
    query = build_query(text)
    if not query.strip():
        raise Refusal("empty-query", "the brief holds no title, acceptance criteria or affected areas")
    return 0, render_retrieve_request(cfg, query)


# --- normalise -----------------------------------------------------------------------------------------------------
def new_rejections() -> Dict[str, int]:
    rejected: Dict[str, int] = {name: 0 for name in REJECTIONS}
    rejected["dropped-references"] = 0
    rejected["truncated-references"] = 0
    return rejected


def check_item(raw: Any, rejected: Dict[str, int]) -> Optional[Tuple[str, str]]:
    """The per-item admission rules: (id, version) when the item may stay, else None with the rejection counted."""
    if not isinstance(raw, dict):
        rejected["not-an-object"] += 1
        return None
    item_id, version = safe_token(raw.get("id")), safe_token(raw.get("version"))
    if item_id is None:
        rejected["invalid-id"] += 1
        return None
    if version is None:
        rejected["invalid-version"] += 1
        return None
    scope, status = raw.get("scope"), raw.get("status")
    if not isinstance(scope, str) or scope not in SCOPES:
        rejected["invalid-scope"] += 1
        return None
    if not isinstance(status, str) or status not in STATUSES:
        rejected["invalid-status"] += 1
        return None
    return item_id, version


def build_item(raw: Dict[str, Any], item_id: str, version: str, rejected: Dict[str, int]) -> Dict[str, Any]:
    """The per-item neutralised shape of an item that passed check_item."""
    superseded = split_reference(raw.get("superseded_by"))
    if superseded is None:
        rejected["dropped-references"] += 1
        superseded = "none"
    conflicts: List[str] = []
    raw_conflicts = raw.get("conflicts_with")
    if raw_conflicts is not None and not isinstance(raw_conflicts, list):
        rejected["dropped-references"] += 1
        raw_conflicts = []
    for ref in raw_conflicts or []:
        token = safe_token(ref)
        if token is None:
            rejected["dropped-references"] += 1
        elif len(conflicts) >= MAX_CONFLICTS:
            rejected["truncated-references"] += 1
        else:
            conflicts.append(token)
    provenance = raw.get("provenance")
    return {
        "id": item_id, "version": version, "scope": raw["scope"], "status": raw["status"],
        "title": clean_text(raw.get("title"), MAX_TITLE), "summary": clean_text(raw.get("summary"), MAX_SUMMARY),
        "superseded_by": superseded, "conflicts_with": conflicts,
        "provenance": provenance if isinstance(provenance, str) and provenance in PROVENANCES else "unknown",
    }


def normalise_item(raw: Any) -> Optional[Dict[str, Any]]:
    """One item through the same rules normalise applies (without the duplicate and over-limit rules)."""
    rejected = new_rejections()
    checked = check_item(raw, rejected)
    return build_item(raw, checked[0], checked[1], rejected) if checked else None


def normalise(response: Any) -> Dict[str, Any]:
    if not isinstance(response, dict) or not isinstance(response.get("items"), list):
        raise Refusal("malformed-response", "expected an object with an items list")
    rejected = new_rejections()
    accepted: List[Dict[str, Any]] = []
    seen = set()
    for raw in response["items"]:
        checked = check_item(raw, rejected)
        if checked is None:
            continue
        if checked in seen:
            rejected["duplicate"] += 1
            continue
        seen.add(checked)
        if len(accepted) >= MAX_ITEMS:
            rejected["over-limit"] += 1
            continue
        accepted.append(build_item(raw, checked[0], checked[1], rejected))
    rejected["total"] = sum(rejected[name] for name in REJECTIONS)
    versions: Dict[str, List[str]] = {}
    for item in accepted:
        versions.setdefault(item["id"], []).append(item["version"])
    conflicts_found = [{"id": i, "versions": v} for i, v in versions.items() if len(v) > 1]
    return {"items": accepted, "rejected": rejected, "conflicts": conflicts_found}


def cmd_normalise(args: argparse.Namespace) -> Tuple[int, Dict[str, Any]]:
    return 0, normalise(_read_json(Path(args.input)))


# --- capture-candidates ----------------------------------------------------------------------------------------
def stem_names(value: str, slug: str) -> bool:
    """The stem rule: the last path component, minus .md, equals the slug. Both separators."""
    stem = re.split(r"[\\/]", value.strip().strip("`'\" ").strip())[-1]
    stem = stem[:-3] if stem.lower().endswith(".md") else stem
    return bool(stem) and stem.casefold() == slug.casefold()


def text_names(text: str, slug: str) -> bool:
    """A bullet's own text names the contract by its concepts path, or by a 'Contract:' label."""
    escaped = re.escape(slug)
    path_form = r"(?<![\w-])concepts[\\/]" + escaped + r"\.md(?![\w-])"
    label_form = r"Contract:\W*(?:[^\s`]*[\\/])?" + escaped + r"(?:\.md)?(?![\w-])"
    return bool(re.search(path_form, text, re.I) or re.search(label_form, text, re.I))


def _flipped(report: Any, slug: str) -> bool:
    if not isinstance(report, dict):
        return False
    contract = report.get("contract")
    completion = report.get("completion")
    verdict = completion.get("verdict") if isinstance(completion, dict) else None
    return (isinstance(contract, str) and contract.casefold() == slug.casefold() and verdict == "flipped")


def _norm_path(value: Any) -> str:
    text = str(value).replace("\\", "/")
    return text[2:] if text.startswith("./") else text


def _carried(brief_rel: str, report: Any) -> bool:
    written = report.get("written_files") if isinstance(report, dict) else None
    if not isinstance(written, list):
        return False
    wanted = _norm_path(brief_rel)
    for entry in written:
        got = _norm_path(entry)
        if got == wanted or got.endswith("/" + wanted) or wanted.endswith("/" + got):
            return True
    return False


def linked_brief(project: Path, slug: str, default_branch: str) -> Optional[str]:
    """The project-relative path of the brief linked to the contract, through the shared selector."""
    select, parse = _PR["select_linked_brief"], _PR["parse_brief_frontmatter"]
    if select is None or parse is None:
        raise Refusal("reader-unavailable", "pr_merged.select_linked_brief is unavailable")
    folder = Path(project) / ".claude" / "work-items"
    briefs: List[Dict[str, Any]] = []
    if folder.is_dir():
        for candidate in sorted(folder.glob("*.md")):
            text = _read_text(candidate)
            fields = parse(text) if text is not None else {}
            if fields:
                entry = dict(fields)
                entry["_path"] = _rel(project, candidate)
                briefs.append(entry)
    contract_text = _read_text(Path(project) / ".claude" / "concepts" / (slug + ".md")) or ""
    chosen = select(contract_text, slug, briefs, default_branch)
    return chosen["_path"] if chosen else None


def token_list(project: Path) -> List[str]:
    """The project-name tokens from <project>/.claude/.project-tokens.json, the one location read."""
    data = _read_json(Path(project) / ".claude" / ".project-tokens.json")
    tokens = data.get("tokens") if isinstance(data, dict) else None
    if not isinstance(tokens, list):
        return []
    return [t for t in tokens if isinstance(t, str) and t.strip()]


def _sha(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def _registry_files(project: Path, name: str) -> List[Tuple[str, bool]]:
    """The registry's files in resolver order (root, general, the other domain files): (project-relative path,
    per_domain). A file under <NAME>/ is per_domain. Raises reader-unavailable when the layout module is missing."""
    lister = _RL["registry_files_in"]
    if lister is None:
        raise Refusal("reader-unavailable", "_registry_layout.registry_files_in is unavailable")
    shipped = _CVB["is_shipped"]
    registries = Path(project) / ".claude" / "registries"
    found: List[Tuple[str, bool]] = []
    try:
        listed = list(lister(registries, name + ".md"))
    except ImportError as exc:  # the bridge's stand-in beside a hooks folder older than the scripts
        raise Refusal("reader-unavailable", "_registry_layout.registry_files_in is unavailable: %s" % exc)
    for path in listed:
        rel = _rel(Path(project), path)
        per_domain = path.parent != registries
        if shipped is None or shipped(rel):
            found.append((rel, per_domain))
    return found


def _candidate(kind: str, key: str, rel: str, line: int, title: str, when: Optional[str], provenance: str,
               tier: str, text: str, slug: str) -> Dict[str, Any]:
    return {"source_kind": kind, "key": key,
            "source_ref": {"file": rel, "line": line, "title": title, "date": when},
            "provenance": provenance, "claimed_status": "proposed",
            "scope": "global" if tier == "Universal" else "project", "scope_lowered": None,
            "contract": slug, "text": text}


#: A journal entry's Trigger, matched only as a whole value, maps to a provenance or to a skip reason.
TRIGGER_PROVENANCE = {"pre-approval critic": "user-decision", "post-impl divergence": "source-code-fact"}
TRIGGER_AI_HYPOTHESIS = ("manual", "post-approval")


def trigger_mapping(trigger: Any) -> Tuple[Optional[str], Optional[str]]:
    """(provenance, None) for an offered trigger, or (None, skip reason).

    The whole value is compared, trimmed, case-folded and with surrounding backticks removed. A longer value that
    merely mentions a canonical one ("manual (follow-up to a pre-approval critic finding)") is an unknown trigger,
    never a guess.
    """
    value = trigger.strip().strip("`").strip().casefold() if isinstance(trigger, str) else ""
    if value in TRIGGER_PROVENANCE:
        return TRIGGER_PROVENANCE[value], None
    return None, "ai-hypothesis" if value in TRIGGER_AI_HYPOTHESIS else "unknown-trigger"


def select_candidates(project: Path, slug: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    entry_blocks, journal_entries, bullet = _GRD["entry_blocks"], _GRD["journal_entries"], _GRD["BULLET"]
    if entry_blocks is None or journal_entries is None or bullet is None:
        raise Refusal("reader-unavailable", "generate_registry_digest readers are unavailable")
    offered: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    for name, kind in (("MECHANISMS", "mechanism-entry"), ("VOCABULARY", "vocabulary-entry")):
        for rel, per_domain in _registry_files(project, name):
            text = _read_text(Path(project) / rel) or ""
            for block in entry_blocks(text, bullet, per_domain=per_domain):
                if text_names(block["text"], slug):
                    key = _sha("%s|%s|%s|%d" % (rel, block["tier"], block["title"], block["line"]))
                    offered.append(_candidate(kind, key, rel, block["line"], block["title"], None,
                                              "source-code-fact", block["tier"], block["text"], slug))
                for sub in block["subs"]:
                    if "**Correction" in sub["text"] and text_names(sub["text"], slug):
                        key = _sha("%s|%s|%s|%d" % (rel, block["tier"], block["title"], sub["line"]))
                        when = re.search(r"\((\d{4}-\d{2}-\d{2})", sub["text"])
                        offered.append(_candidate(
                            "correction-entry", key, rel, sub["line"], block["title"],
                            when.group(1) if when else None, "source-code-fact", block["tier"],
                            "%s\n(correction to the entry: %s)" % (sub["text"], block["title"]), slug))
    for rel, per_domain in _registry_files(project, "JOURNAL"):
        text = _read_text(Path(project) / rel) or ""
        for entry in journal_entries(text, per_domain=per_domain):
            if not entry["source"] or not stem_names(entry["source"], slug):
                continue
            provenance, reason = trigger_mapping(entry["trigger"])
            if provenance is None:
                skipped.append({"title": entry["title"], "key": entry["sig"], "reason": reason})
                continue
            offered.append(_candidate("journal-entry", entry["sig"], rel, entry["line"], entry["title"],
                                      entry["date"], provenance, entry["tier"], entry["text"], slug))
    return offered, skipped


def apply_scope_safety(candidates: List[Dict[str, Any]], tokens: List[str]) -> None:
    """Lower a global candidate to project on a token hit; with no token list, lower every one (fail closed)."""
    for cand in candidates:
        if cand["scope"] != "global":
            continue
        if not tokens:
            cand["scope"], cand["scope_lowered"] = "project", "no-token-list"
            continue
        lowered = cand["text"].casefold()
        for token in tokens:
            if token.casefold() in lowered:
                cand["scope"], cand["scope_lowered"] = "project", "token:" + token
                break


def cmd_capture_candidates(args: argparse.Namespace) -> Tuple[int, Dict[str, Any]]:
    project, slug = Path(args.project), args.contract
    cfg = read_config(project)
    require_capture(cfg)
    report = _read_json(_resolve(project, args.run_report))
    if not _flipped(report, slug):
        raise Refusal("not-flipped", "the live writing run did not return flipped for %s" % slug)
    default_branch = args.default_branch
    if default_branch is None:
        # The project's own origin/HEAD, read in the project folder and never the process's working directory.
        # pr_merged.default_branch() is never used: it falls back to "master" when origin/HEAD is unreadable.
        reader = _PR["default_branch_or_none"]
        default_branch = reader(cwd=str(project)) if reader else None
    if not default_branch:
        raise Refusal("default-branch-unknown",
                      "origin/HEAD is unreadable in the project: pass --default-branch <name>")
    brief_rel = linked_brief(project, slug, default_branch)
    if brief_rel is None or not _carried(brief_rel, report):
        raise Refusal("brief-not-carried", "no linked brief, or it is not in the run's written_files")
    offered, not_offered = select_candidates(project, slug)
    brief_text = _read_text(Path(project) / brief_rel) or ""
    recorded = set(RECEIPT_KEY_LINE.findall(brief_text))
    candidates = [c for c in offered if c["key"] not in recorded]
    already = [c["key"] for c in offered if c["key"] in recorded]
    apply_scope_safety(candidates, token_list(project))
    return 0, {"contract": slug, "brief": brief_rel, "candidates": candidates, "not_offered": not_offered,
               "already_recorded": already}


# --- capture-request ---------------------------------------------------------------------------------------------
def source_ref_text(value: Any) -> str:
    """'<file>:<line>' from the source_ref object capture-candidates emits, or a cleaned string as given."""
    if isinstance(value, dict):
        return "%s:%s" % (clean_text(value.get("file"), 200), safe_token(value.get("line")) or "")
    return clean_text(value, 200)


def cmd_capture_request(args: argparse.Namespace) -> Tuple[int, Dict[str, Any]]:
    project = Path(args.project)
    cfg = read_config(project)
    require_capture(cfg)
    cand = _read_json(_resolve(project, args.candidate))
    if not isinstance(cand, dict):
        raise Refusal("candidate-unreadable", str(args.candidate))
    provenance = cand.get("provenance")
    if provenance == "ai-hypothesis":
        raise Refusal("ai-hypothesis-refused", "an AI hypothesis is never captured")
    if provenance not in CAPTURABLE:
        raise Refusal("provenance-invalid", "provenance %r cannot be sent" % (provenance,))
    if cand.get("claimed_status") != "proposed":
        raise Refusal("status-not-proposed", "the plugin only ever claims proposed")
    ref = cand.get("source_ref") if isinstance(cand.get("source_ref"), dict) else {}
    arguments: Dict[str, Any] = {
        "title": clean_text(ref.get("title"), MAX_TITLE),
        "content": cand.get("text") if isinstance(cand.get("text"), str) else "",
        "scope": cand.get("scope") if cand.get("scope") in SCOPES else "project",
        "status": "proposed",
        "provenance": provenance,
        "source_ref": source_ref_text(cand.get("source_ref")),
        "client_key": cand.get("key") if isinstance(cand.get("key"), str) and KEY_RE.fullmatch(cand["key"]) else "",
    }
    if cfg["project_key"]:
        arguments["project"] = cfg["project_key"]
    return 0, {"tool": tool_id(cfg["server"], cfg["capture_tool"]), "arguments": arguments, "shape": cfg["shape"],
               "shape_provisional": SHAPES[cfg["shape"]]["provisional"]}


# --- record -----------------------------------------------------------------------------------------------------
def retrieved_line(item: Any) -> Optional[str]:
    if not isinstance(item, dict):
        return None
    item_id, version = safe_token(item.get("id")), safe_token(item.get("version"))
    scope, status, decision = item.get("scope"), item.get("status"), item.get("decision")
    if (item_id is None or version is None or scope not in SCOPES or status not in STATUSES
            or decision not in DECISIONS):
        return None
    parts = ["Retrieved: %s@%s" % (item_id, version), scope, status, decision]
    if decision == "applies" and item.get("cited") in ("cited", "not-cited"):
        parts.append(item["cited"])
    parts.append('"%s"' % clean_text(item.get("title"), MAX_TITLE).replace('"', "'"))
    return " | ".join(parts)


def reported_line(entry: Any) -> Optional[str]:
    if not isinstance(entry, dict):
        return None
    item_id, version = safe_token(entry.get("id")), safe_token(entry.get("version"))
    if item_id is None or version is None or entry.get("kind") not in REPORT_KINDS:
        return None
    return "Reported: %s | %s@%s | %s" % (entry["kind"], item_id, version, clean_text(entry.get("detail"), 200))


def receipt_line(entry: Any, already: set) -> Tuple[Optional[str], bool]:
    """(line, dropped). A key already on the brief is skipped silently: (None, False)."""
    if not isinstance(entry, dict):
        return None, True
    key = entry.get("key")
    if not isinstance(key, str) or not KEY_RE.fullmatch(key):
        return None, True
    if key in already:
        return None, False
    ref = source_ref_text(entry.get("source_ref"))
    when = safe_date(entry.get("date"))
    if entry.get("captured") is True:
        item_id, version = safe_token(entry.get("id")), safe_token(entry.get("version"))
        if item_id is None or version is None:
            return None, True
        return "Captured: %s | %s | %s@%s | %s" % (key, ref, item_id, version, when), False
    return "Not sent: %s | %s | (%s) | %s" % (key, ref, clean_text(entry.get("reason"), 120), when), False


def _section_bounds(lines: List[str]) -> Tuple[int, int]:
    for idx, line in enumerate(lines):
        if line.rstrip("\r") == SECTION:
            end = idx + 1
            while end < len(lines) and not lines[end].startswith("## "):
                end += 1
            return idx, end
    return len(lines), len(lines)


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp.%d" % os.getpid())
    tmp.write_bytes(text.encode("utf-8"))
    os.replace(tmp, path)


def cmd_record(args: argparse.Namespace) -> Tuple[int, Dict[str, Any]]:
    project = Path(args.project)
    cfg = read_config(project)
    # Only a disabled profile (I-M0) or a disabled outcome refuses. An unconfigured profile still records its one
    # line (Step 1.5 point 3); receipts need an enabled memory.
    if cfg["state"] == "disabled":
        raise Refusal("not-enabled", "memory state is disabled")
    if args.receipts:
        require_enabled(cfg)
    outcome = _read_json(_resolve(project, args.outcome))
    outcome = outcome if isinstance(outcome, dict) else {}
    if outcome.get("state") == "disabled":
        raise Refusal("not-enabled", "the outcome says memory was disabled")
    unconfigured = cfg["state"] == "unconfigured"
    brief_path = _resolve(project, args.brief)
    raw = _read_text(brief_path)
    if raw is None:
        raise Refusal("brief-not-found", str(args.brief))
    if args.receipts:
        report = _read_json(_resolve(project, args.run_report)) if args.run_report else None
        if not _carried(_rel(project, brief_path), report):
            raise Refusal("brief-not-carried", "the brief is not in the run's written_files")
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    front = FRONTMATTER.match(text)
    if not front:
        raise Refusal("would-add-frontmatter", "the brief has no frontmatter block to leave untouched")

    lines = text.split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    start, end = _section_bounds(lines)
    existing = lines[start + 1:end]
    existing_keys = set(RECEIPT_KEY_LINE.findall("\n".join(existing)))
    dropped = 0
    if args.receipts:
        new_lines = [l for l in existing if l.strip()] or [_memory_line(cfg, outcome)]
        receipts = outcome.get("receipts") if isinstance(outcome.get("receipts"), list) else []
        for entry in receipts:
            line, was_dropped = receipt_line(entry, existing_keys)
            dropped += was_dropped
            if line:
                new_lines.append(line)
                existing_keys.add(entry["key"])
    elif unconfigured:
        # One line, the reason from the profile; whatever the outcome carries is ignored. The keep rule: the
        # earlier Retrieved: and Reported: lines stay, in order, so a profile that went unconfigured loses nothing.
        new_lines = [_unconfigured_line(cfg, outcome)]
        new_lines += [l for l in existing if l.startswith(("Retrieved:", "Reported:"))]
        new_lines += [l for l in existing if l.startswith(("Captured:", "Not sent:"))]
    else:
        new_lines = [_memory_line(cfg, outcome)]
        retrieved = outcome.get("retrieved") if isinstance(outcome.get("retrieved"), list) else []
        reported = outcome.get("reported") if isinstance(outcome.get("reported"), list) else []
        carried: List[str] = []
        for item in retrieved:
            line = retrieved_line(item)
            dropped += line is None
            if line:
                carried.append(line)
        for entry in reported:
            line = reported_line(entry)
            dropped += line is None
            if line:
                carried.append(line)
        if not retrieved and not reported and outcome.get("state") != "unavailable":
            # The keep rule for an enabled empty retrieval: nothing new to say about items, so the earlier
            # Retrieved: and Reported: lines stay. An outcome that carries items replaces them; an unavailable
            # outcome says the call did not happen and is written as before.
            carried = [l for l in existing if l.startswith(("Retrieved:", "Reported:"))]
        new_lines += carried
        new_lines += [l for l in existing if l.startswith(("Captured:", "Not sent:"))]

    head = lines[:start]
    while head and head[-1] == "":
        head.pop()
    tail = lines[end:]
    while tail and tail[0] == "":
        tail.pop(0)
    parts = head + [""] + [SECTION] + new_lines + ([""] + tail if tail else [])
    result = "\n".join(parts) + "\n"
    after = FRONTMATTER.match(result)
    if not after or after.group(0) != front.group(0):
        raise Refusal("would-add-frontmatter", "the write would change the frontmatter")
    _atomic_write(brief_path, result.replace("\n", "\r\n") if crlf else result)
    return 0, {"written": True, "brief": _rel(project, brief_path), "lines": len(new_lines), "dropped": dropped}


def _unconfigured_line(cfg: Dict[str, Any], outcome: Dict[str, Any]) -> str:
    reason = cfg["reason"] if cfg["reason"] in REASONS else ""
    return "Memory: unconfigured%s | %s" % (" (%s)" % reason if reason else "", safe_date(outcome.get("date")))


def _memory_line(cfg: Dict[str, Any], outcome: Dict[str, Any]) -> str:
    state = "unavailable" if outcome.get("state") == "unavailable" else cfg["state"]
    reason = outcome.get("reason") if state == "unavailable" else cfg["reason"]
    reason = reason if isinstance(reason, str) and reason in REASONS else ""
    return "Memory: %s%s | %s" % (state, " (%s)" % reason if reason else "", safe_date(outcome.get("date")))


# --- check-contract ---------------------------------------------------------------------------------------------
def applies_items(text: str) -> List[Tuple[str, str]]:
    found: List[Tuple[str, str]] = []
    for item_id, version, decision in RETRIEVED_LINE.findall(text):
        if decision == "applies" and (item_id, version) not in found:
            found.append((item_id, version))
    return found


def cmd_check_contract(args: argparse.Namespace) -> Tuple[int, Dict[str, Any]]:
    project = Path(args.project)
    brief = _read_text(_resolve(project, args.brief)) or ""
    contract = _read_text(_resolve(project, args.contract)) or ""
    applies = applies_items(brief)
    cited = []
    for item_id, version in MEMORY_ITEM_LINE.findall(contract):
        if (item_id, version) not in cited:
            cited.append((item_id, version))
    items = [{"id": i, "version": v, "result": "cited" if (i, v) in cited else "not-cited"} for i, v in applies]
    uncleared = [{"id": i, "version": v, "result": "uncleared-item"} for i, v in cited if (i, v) not in applies]
    return 0, {"items": items, "uncleared": uncleared}


# --- changed-items ------------------------------------------------------------------------------------------------
def cmd_changed_items(args: argparse.Namespace) -> Tuple[int, Dict[str, Any]]:
    project = Path(args.project)
    data = _read_json(_resolve(project, args.input))
    returned: Dict[str, List[Dict[str, Any]]] = {}
    for raw in data.get("items", []) if isinstance(data, dict) and isinstance(data.get("items"), list) else []:
        # The same per-item rules normalise applies: an item normalise would reject cannot raise a notice, and
        # versions are compared as the normalised strings.
        item = normalise_item(raw)
        if item is not None:
            returned.setdefault(item["id"], []).append(item)
    recorded: Dict[Tuple[str, str], List[str]] = {}
    folder = project / ".claude" / "work-items"
    if folder.is_dir():
        for brief in sorted(folder.glob("*.md")):
            for pair in applies_items(_read_text(brief) or ""):
                recorded.setdefault(pair, []).append(_rel(project, brief))
    notices = []
    for (item_id, version), briefs in sorted(recorded.items()):
        current = returned.get(item_id)
        if not current:
            continue
        same = [i for i in current if i["version"] == version]
        chosen = same[0] if same else current[0]
        if same and chosen.get("status") not in ("superseded", "conflicting"):
            continue
        notices.append({"id": item_id, "recorded_version": version, "current_version": chosen["version"],
                        "current_status": chosen.get("status") if chosen.get("status") in STATUSES else "unknown",
                        "superseded_by": split_reference(chosen.get("superseded_by")) or "none",
                        "briefs": briefs})
    return 0, {"notices": notices}


# --- command line ------------------------------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="memory_boundary.py", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command")

    def add(name: str, handler, *flags: Tuple[str, bool]) -> None:
        p = sub.add_parser(name)
        p.add_argument("--project", required=True)
        for flag, required in flags:
            p.add_argument(flag, required=required)
        p.set_defaults(handler=handler)
        return p

    add("status", cmd_status)
    add("retrieve-request", cmd_retrieve_request, ("--brief", True))
    add("normalise", cmd_normalise, ("--input", True))
    cc = add("capture-candidates", cmd_capture_candidates, ("--contract", True), ("--run-report", True))
    cc.add_argument("--default-branch", default=None)
    add("capture-request", cmd_capture_request, ("--candidate", True))
    rec = add("record", cmd_record, ("--brief", True), ("--outcome", True), ("--run-report", False))
    rec.add_argument("--receipts", action="store_true")
    add("check-contract", cmd_check_contract, ("--brief", True), ("--contract", True))
    add("changed-items", cmd_changed_items, ("--input", True))
    return parser


def _emit(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload))


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if argv and argv[0] == "status":
        # status never fails: any problem at all reads as "memory off".
        try:
            args = parser.parse_args(argv)
            _emit(args.handler(args)[1])
        except Exception:
            _emit(public_status({"state": "disabled", "reason": "profile-absent", "server": "", "retrieve_tool": "",
                                 "capture_tool": "", "shape": "", "project_key": "", "capture": False,
                                 "date": today(), "line": ""}))
        return 0
    try:
        args = parser.parse_args(argv)
        if not getattr(args, "handler", None):
            raise UsageError("a subcommand is required")
        code, payload = args.handler(args)
    except UsageError as exc:
        _emit({"refused": "usage", "detail": str(exc)})
        return 2
    except Refusal as exc:
        _emit({"refused": exc.name, "detail": exc.detail})
        return 1
    except Exception as exc:  # a crash reads as "memory off" to every caller
        _emit({"refused": "error", "detail": type(exc).__name__})
        return 1
    _emit(payload)
    return code


if __name__ == "__main__":
    sys.exit(main())
