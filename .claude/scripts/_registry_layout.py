#!/usr/bin/env python3
"""
_registry_layout.py -- the one reader of the registry layout.

Sole owner of: the layout marker, the entry grammars (mechanism / vocabulary bullets, journal
headings, legacy forms), entry keys, the non-entry sections (I-8b), path references, the layout
state (I-1) and the structure rules R1-R6 and A1. The digest generator, the lint, the writer and
the migration read registries only through this module, so the grammar exists once.

Imports the standard library and ``_claude_paths`` (the file-listing half of the resolver) only.
It imports neither ``plugin_doctor`` nor any CLI script. The normative text is
``.claude/references/registry-layout.md``.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

from _claude_paths import registry_files_in

LAYOUT_CURRENT = 2
MARKER = "<!-- registry-layout: 2 -->"
REGISTRIES = ("MECHANISMS", "VOCABULARY", "JOURNAL")
POINTER_HEADING = "## Project tier"
LEFTOVERS_HEADING = "## Migration 0001 leftovers (not parsed as entries)"
TRIGGERS = ("pre-approval critic", "post-approval", "post-impl divergence", "manual")
JOURNAL_REQUIRED_FIELDS = ("trigger", "source contract", "lesson", "tags")  # "apply when" is R1's job
ARCHIVED = "archived-title-only"

# Consumer-only or generated paths; a registry may cite them without them existing in a checkout.
R4_EXCLUDED_PREFIXES = (
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".claude/.sync-config.json",
    ".claude/.sync-state/",
    ".claude/hook-registration-profile.json",
    ".claude/.scout-cache/",
    ".claude/cache/",
    ".claude/logs/",
    ".codegraph/",
)

DIGEST_RELATIVE = Path(".scout-cache") / "registry-digest.md"
SOURCES_LINE = "<!-- registry-sources-sha256: {digest} -->"
_SOURCES_RE = re.compile(r"^<!--\s*registry-sources-sha256:\s*([0-9a-fA-F]+)\s*-->\s*$", re.MULTILINE)

REMEDY_MIGRATE = "registry_migrate.py --dry-run"
REMEDY_DOCTOR = "plugin_doctor.py --fix"
REMEDY_AGREE = "make the root markers agree, then re-run `--check`"

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_MARKER_RE = re.compile(r"^<!--\s*registry-layout:\s*(\S+?)\s*-->\s*$")
_HEADING = re.compile(r"^(#{1,6})[ \t]+(\S.*?)[ \t]*$")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
_DATE_SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2}")
_J_HEADER = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+(?:—|--|-)\s+(\S.*?)\s*$")
_DATED = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*(?:(?:—|–|--|-)(?:\s+|$)\s*)?(.*?)\s*$")
_BULLET = re.compile(r"^- \*\*(.+?)\*\*(.*)$")
_DATE_TAG = re.compile(r"^\s*\*\(([^)]*)\)\*")
_DATE_TAG_ANY = re.compile(r"\*\([^)]*\)\*")
_SEP = re.compile(r"^\s*(?:—|–|--(?=\s|$)|-(?=\s|$))\s*")
_FIELD = re.compile(r"^\s*-\s*\*\*([A-Za-z][^*:]*?):\*\*\s*(.*?)\s*$")
_STATUS = re.compile(r"^\s*-\s*\*\*Status:\*\*\s*(.*?)\s*$")
_J_BULLET = re.compile(r"^- (\d{4}-\d{2}-\d{2}\b.*)$")
_LEFTOVER_HEADING = re.compile(r"^## Migration \d+ leftovers")
_LEFTOVER_COMMENT = re.compile(r"^<!--\s*leftover from (.+?):(\d+)-(\d+),\s*([\w-]+)\s*-->\s*$")
_BACKTICK_SPAN = re.compile(r"`([^`\n]+)`")
_PATH_CHARS = re.compile(r"^[A-Za-z0-9_\-./\\]+$")
_PATH_EXT = re.compile(r"\.[A-Za-z0-9]{1,8}$")
_DIGEST_LINE = re.compile(r"^- (.*) \[[^\[\]]+:\d+\]\s*$")


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------
@dataclass
class Entry:
    registry: str
    tier: str                      # universal | project:<name> | domain:<slug> | below-pointer
    file: str
    line: int
    end_line: int
    title: str
    key: str
    text: str
    kind: str                      # entry | legacy
    status: str                    # active | archived-title-only | legacy
    date: str = ""
    tags: str = ""
    source_contract: str = ""
    fields: dict = field(default_factory=dict)
    has_body: bool = False
    malformed: list = field(default_factory=list)


@dataclass
class ParsedFile:
    file: str
    registry: str
    kind: str                      # root | domain
    slug: Optional[str]
    lines: list
    marker: str                    # the value after "registry-layout:" on line 1, or "none"
    entries: list
    project_headings: list         # (line, name)
    pointer_line: Optional[int]
    leftover_lines: list           # lines of leftover headings
    leftover_blocks: list          # (line, source, reason)
    leftover_range: Optional[tuple]
    fence: list                    # per line: inside a fence (delimiters included)

    @property
    def below_pointer(self) -> list:
        if self.pointer_line is None or self.kind != "root":
            return []
        return [e for e in self.entries if e.line > self.pointer_line]


@dataclass
class Finding:
    rule: str                      # R1..R6 or A1
    file: str
    line: int
    key: str
    message: str
    remedy: str
    severity: str                  # finding | advisory
    variant: str = ""              # R3 only: plugin-owned | unverified | universal-candidate


@dataclass
class LayoutState:
    state: str                     # current | pending | stale-sync | unknown | absent
    marker: str
    layout_current: int
    reasons: list
    remedy: str

    def as_dict(self) -> dict:
        return {"state": self.state, "marker": self.marker, "layout_current": self.layout_current,
                "reasons": list(self.reasons), "remedy": self.remedy}


# ---------------------------------------------------------------------------
# Text, keys, fences
# ---------------------------------------------------------------------------
def normalise_bytes(data: bytes) -> bytes:
    """Drop a byte order mark and fold line endings to LF."""
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def read_lines(path: Path) -> list:
    try:
        data = Path(path).read_bytes()
    except OSError:
        return []
    return normalise_bytes(data).decode("utf-8", errors="replace").split("\n")


def entry_key(title: str) -> str:
    """The normalised title: date tag removed, lowercased, whitespace collapsed."""
    return re.sub(r"\s+", " ", _DATE_TAG_ANY.sub(" ", title)).strip().lower()


def fence_mask(lines: Sequence[str]) -> list:
    """True for every line inside a fenced code block, delimiters included (I-8)."""
    mask: list = []
    open_char = ""
    open_len = 0
    for ln in lines:
        m = _FENCE.match(ln)
        if not open_char:
            if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
                open_char, open_len = m.group(1)[0], len(m.group(1))
                mask.append(True)
            else:
                mask.append(False)
        else:
            mask.append(True)
            if m and m.group(1)[0] == open_char and len(m.group(1)) >= open_len and not m.group(2).strip():
                open_char = ""
    return mask


def is_path_reference(span: str) -> bool:
    """One backticked span that names a repository file (see the spec, "Path reference")."""
    if not span or not _PATH_CHARS.match(span):
        return False
    if span.startswith(("/", "\\", "./", ".\\", "../", "..\\")):
        return False
    if "/" not in span and "\\" not in span:
        return False
    return bool(_PATH_EXT.search(span))


def path_references(text: str) -> list:
    return [m.group(1) for m in _BACKTICK_SPAN.finditer(text) if is_path_reference(m.group(1))]


def pointer_section(registry: str) -> str:
    """The fixed pointer that ends a layout-2 root (I-2). Generic, so the sync can deliver it."""
    stem = registry[:-3] if registry.endswith(".md") else registry
    return (
        f"{POINTER_HEADING}\n\n"
        "This file holds only the Universal tier. Project entries live in domain files beside it, "
        f"one file per domain, named `{stem}/<domain>.md`.\n\n"
        "The file `general.md` always exists in that folder, and every `.md` file in the folder is read.\n"
    )


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
def _valid_date(value: str) -> bool:
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _field_map(lines: Sequence[str]) -> dict:
    fields: dict = {}
    last = ""
    for ln in lines:
        m = _FIELD.match(ln)
        if m:
            name = re.sub(r"\s+", " ", m.group(1)).strip().lower()
            if name.startswith("correction"):
                last = ""
                continue
            fields[name] = m.group(2)
            last = name
        elif last and ln.strip() and ln.startswith(" "):
            fields[last] = (fields[last] + " " + ln.strip()).strip()
    return fields


def _status_of(lines: Sequence[str]) -> str:
    for ln in lines:
        m = _STATUS.match(ln)
        if m and ARCHIVED in m.group(1).lower():
            return ARCHIVED
    return "active"


def _split_sep(rest: str):
    """Split the text after a bullet title into (date tag content, separator found, body)."""
    tag = _DATE_TAG.match(rest)
    tag_text = ""
    if tag:
        tag_text = tag.group(1)
        rest = rest[tag.end():]
    sep = _SEP.match(rest)
    if sep:
        return tag_text, True, rest[sep.end():]
    return tag_text, False, rest.strip()


def _make_entry(op: dict, registry: str, file: str, tier: str) -> Entry:
    body = op["lines"]
    while body and not body[-1].strip():
        body = body[:-1]
    end_line = op["start"] + len(body)
    style = op["style"]
    status = _status_of(body)
    fields: dict = {}
    malformed: list = []
    date = ""
    tags = ""
    source = ""
    if style == "mv":
        tag_text, has_sep, first = _split_sep(op["rest"])
        m = re.search(r"\d{4}-\d{2}-\d{2}", tag_text)
        date = m.group(0) if m else ""
        if not has_sep:
            malformed.append("no separator after the title")
        parts = [first] + [ln for ln in body if not _STATUS.match(ln)]
        text = "\n".join(p.strip("\n") for p in parts).strip()
        title = op["title"].strip()
        has_body = bool(text)
        kind = "entry"
    elif style == "journal":
        header = op["title"]
        m = _J_HEADER.match(header)
        if m:
            date, title = m.group(1), m.group(2)
        else:
            dm = _DATED.match(header)
            date, title = (dm.group(1), dm.group(2)) if dm else ("", header)
            malformed.append("no separator after the date")
        if date and not _valid_date(date):
            malformed.append(f"invalid date {date}")
        fields = _field_map(body)
        text = "\n".join(body).strip()
        has_body = bool(fields.get("apply when", "").strip())
        tags = fields.get("tags", "").strip("` ")
        source = fields.get("source contract", "").strip("` ")
        kind = "entry"
        if status != ARCHIVED:
            for name in JOURNAL_REQUIRED_FIELDS:
                if name not in fields:
                    malformed.append(f"missing required field {name}")
            trig = fields.get("trigger")
            if trig is not None and trig.strip("` ").lower() not in TRIGGERS:
                malformed.append(f"trigger {trig!r} is not one of {', '.join(TRIGGERS)}")
    else:  # legacy heading or legacy bullet
        dm = _DATED.match(op["title"])
        date, title = (dm.group(1), dm.group(2)) if dm else ("", op["title"])
        text = "\n".join(body).strip()
        has_body = bool(text)
        kind = "legacy"
        status = "legacy"
    return Entry(registry=registry, tier=tier, file=file, line=op["start"], end_line=end_line, title=title,
                 key=entry_key(title), text=text, kind=kind, status=status, date=date, tags=tags,
                 source_contract=source, fields=fields, has_body=has_body, malformed=malformed)


def parse_text(text: str, registry: str, *, kind: str = "root", slug: Optional[str] = None,
               file: str = "") -> ParsedFile:
    """Parse one registry file into entries, legacy entries and structural landmarks."""
    registry = registry[:-3] if registry.endswith(".md") else registry
    lines = normalise_bytes(text.encode("utf-8")).decode("utf-8").split("\n")
    mask = fence_mask(lines)
    journal = registry == "JOURNAL"
    marker = "none"
    if lines:
        m = _MARKER_RE.match(lines[0])
        if m:
            marker = m.group(1)

    entries: list = []
    project_headings: list = []
    pointer_line: Optional[int] = None
    leftover_lines: list = []
    leftover_range: Optional[tuple] = None
    tier = "universal"
    prose_level: Optional[int] = None
    op: Optional[dict] = None

    def tier_now() -> str:
        return f"domain:{slug or ''}" if kind == "domain" else tier

    def close() -> None:
        nonlocal op
        if op is not None:
            entries.append(_make_entry(op, registry, file, op["tier"]))
            op = None

    def open_op(style: str, n: int, title: str, rest: str = "") -> None:
        nonlocal op
        close()
        op = {"style": style, "start": n, "title": title, "rest": rest, "lines": [], "tier": tier_now()}

    for idx, ln in enumerate(lines):
        n = idx + 1
        if mask[idx]:
            # A fence line belongs to the open entry when it continues it; a column-0 fence ends a bullet.
            if op is not None and (op["style"] in ("journal", "legacy-heading") or ln.startswith(" ") or not ln.strip()):
                op["lines"].append(ln)
            elif op is not None:
                close()
            continue
        hm = _HEADING.match(ln)
        if hm:
            level, htext = len(hm.group(1)), hm.group(2)
            close()
            if prose_level is not None and level <= prose_level:
                if leftover_range is not None and leftover_range[1] is None:
                    leftover_range = (leftover_range[0], n - 1)
                prose_level = None
            if prose_level is not None:
                continue
            if level == 2 and _LEFTOVER_HEADING.match(ln):
                leftover_lines.append(n)
                leftover_range = (n, None)
                prose_level = 2
            elif level == 2 and re.match(r"Project tier\s*$", htext, re.IGNORECASE):
                if pointer_line is None:
                    pointer_line = n
                tier = "below-pointer"
            elif level == 2 and re.match(r"Project:", htext):
                project_headings.append((n, htext[len("Project:"):].strip()))
                tier = f"project:{htext[len('Project:'):].strip()}"
            elif level == 2 and re.match(r"Universal", htext, re.IGNORECASE):
                tier = "universal"
            elif journal and level == 3 and _DATE_SHAPE.match(htext):
                open_op("journal", n, htext)
            elif level == 2 and _DATE_SHAPE.match(htext):
                open_op("legacy-heading", n, htext)
            elif level == 2 or (journal and level == 3):
                # I-8b: a non-entry heading opens a prose section. The level-1 file title does not:
                # it names the file, and entries of a domain file may follow it directly.
                prose_level = level
            continue
        if prose_level is not None:
            continue
        if op is not None and op["style"] in ("journal", "legacy-heading"):
            op["lines"].append(ln)
            continue
        if not journal:
            bm = _BULLET.match(ln)
            if bm:
                open_op("mv", n, bm.group(1), bm.group(2))
                continue
        else:
            jb = _J_BULLET.match(ln)
            if jb:
                open_op("legacy-bullet", n, jb.group(1))
                continue
        if op is not None:
            if ln.startswith("  ") or not ln.strip():
                op["lines"].append(ln)
            else:
                close()
    close()
    if leftover_range is not None and leftover_range[1] is None:
        leftover_range = (leftover_range[0], len(lines))

    leftover_blocks: list = []
    if leftover_range is not None:
        for i in range(leftover_range[0] - 1, leftover_range[1]):
            cm = _LEFTOVER_COMMENT.match(lines[i])
            if cm:
                leftover_blocks.append((i + 1, f"{cm.group(1)}:{cm.group(2)}-{cm.group(3)}", cm.group(4)))
    return ParsedFile(file=file, registry=registry, kind=kind, slug=slug, lines=lines, marker=marker,
                      entries=entries, project_headings=project_headings, pointer_line=pointer_line,
                      leftover_lines=leftover_lines, leftover_blocks=leftover_blocks,
                      leftover_range=leftover_range, fence=mask)


def parse_file(path: Path, registry: str, *, display: Optional[str] = None) -> ParsedFile:
    path = Path(path)
    registry = registry[:-3] if registry.endswith(".md") else registry
    is_root = path.name == f"{registry}.md"
    text = "\n".join(read_lines(path))
    return parse_text(text, registry, kind="root" if is_root else "domain",
                      slug=None if is_root else path.stem, file=display or str(path))


def parse_entries(path: Path, registry: str) -> list:
    return parse_file(path, registry).entries


# ---------------------------------------------------------------------------
# Reader adapters (Q21 (a)): the memory adapter and the journal tracker read through these
# ---------------------------------------------------------------------------
#: The top-level mechanism / vocabulary bullet. Re-exported by the digest generator for the memory adapter, which
#: passes it to ``entry_blocks`` for signature compatibility; the adapters use the one grammar, not this pattern.
BULLET = _BULLET
_SUB_BULLET = re.compile(r"^(\s+)[-*]\s")
_UNSET_SOURCES = ("", "none", "n/a", "na", "unknown", "tbd")


def source_value(raw: str) -> str:
    """A Source contract value: the rest of the line, backticks and padding trimmed; unset forms read empty."""
    value = (raw or "").strip().strip("`").strip()
    if value.lower() in _UNSET_SOURCES or value.startswith("<"):
        return ""
    return value


def _first_universal_heading(pf: ParsedFile) -> Optional[int]:
    """The 1-based line of the first ``## Universal...`` heading outside a fence, or None."""
    for idx, ln in enumerate(pf.lines):
        if pf.fence[idx]:
            continue
        hm = _HEADING.match(ln)
        if hm and len(hm.group(1)) == 2 and re.match(r"Universal", hm.group(2), re.IGNORECASE):
            return idx + 1
    return None


def _adapter_tier(pf: ParsedFile, entry: Entry, per_domain: bool) -> str:
    """``Universal`` only for a root entry that a ``## Universal`` heading precedes; otherwise ``Project``.

    The fail-closed rule for memory scope: an entry before any heading, below the pointer, under a project heading or
    in a domain file is Project.
    """
    if per_domain or entry.tier != "universal":
        return "Project"
    first = _first_universal_heading(pf)
    return "Universal" if first is not None and first < entry.line else "Project"


def entry_blocks(text: str, pattern: Any = None, per_domain: bool = False) -> list:
    """Every entry of a mechanism or vocabulary TEXT, with its full shape, read through ``parse_text``.

    One dict per entry (legacy entries included, I-8c): ``title``, ``line`` (1-based), ``tier`` (``Universal`` or
    ``Project``), ``text`` (the entry's own text, up to its first indented sub-bullet) and ``subs`` (each indented
    sub-bullet as ``line`` and ``text``, with deeper continuation lines folded in). A legacy entry keeps all its lines
    in ``text`` and has no subs. ``pattern`` is accepted for signature compatibility and not used: there is one
    grammar. Takes text, never a path.
    """
    pf = parse_text(text, "MECHANISMS", kind="domain" if per_domain else "root")
    blocks: list = []
    for entry in pf.entries:
        raw = pf.lines[entry.line - 1:entry.end_line]
        own, subs, sub_indent = [raw[0]], [], None
        if entry.kind == "legacy":
            own = list(raw)
        else:
            for offset, ln in enumerate(raw[1:], 1):
                sub = _SUB_BULLET.match(ln)
                if sub and (sub_indent is None or len(sub.group(1)) <= sub_indent):
                    sub_indent = len(sub.group(1))
                    subs.append({"line": entry.line + offset, "text": ln.strip()})
                elif subs:
                    subs[-1]["text"] += ("\n" + ln.strip()) if ln.strip() else ""
                else:
                    own.append(ln)
        blocks.append({"title": entry.title.strip(), "line": entry.line, "tier": _adapter_tier(pf, entry, per_domain),
                       "text": "\n".join(own).rstrip(), "subs": subs})
    return blocks


def journal_entries(text: str, per_domain: bool = False) -> list:
    """Every ``### YYYY-MM-DD`` entry of a journal TEXT, read through ``parse_text`` (entries only, never legacy).

    One dict per entry, malformed ones included: ``sig`` (sha1 of ``date|title``), ``date``, ``title``, ``line``,
    ``tier`` (see ``_adapter_tier``), ``trigger`` (trimmed, lower-cased), ``source`` (``source_value`` of the Source
    contract field, empty when unset) and ``text`` (the heading line plus every line of the entry).
    """
    pf = parse_text(text, "JOURNAL", kind="domain" if per_domain else "root")
    found: list = []
    for entry in pf.entries:
        if entry.kind != "entry":
            continue
        found.append({
            "sig": hashlib.sha1(f"{entry.date}|{entry.title}".encode("utf-8", errors="ignore")).hexdigest(),
            "date": entry.date, "title": entry.title, "line": entry.line,
            "tier": _adapter_tier(pf, entry, per_domain),
            "trigger": entry.fields.get("trigger", "").strip().lower(),
            "source": source_value(entry.fields.get("source contract", "")),
            "text": "\n".join(pf.lines[entry.line - 1:entry.end_line]),
        })
    return found


# ---------------------------------------------------------------------------
# Whole-registry reads
# ---------------------------------------------------------------------------
def display_for(registries_dir: Path, project_root: Optional[Path]):
    base = Path(project_root) if project_root is not None else Path(registries_dir).parent.parent

    def display(path: Path) -> str:
        try:
            return Path(path).resolve().relative_to(base.resolve()).as_posix()
        except (ValueError, OSError):
            return Path(path).as_posix()
    return display


def parsed_files(registries_dir: Path, *, project_root: Optional[Path] = None,
                 registries: Iterable[str] = REGISTRIES, domains: Optional[Iterable[str]] = None) -> list:
    """Every file of every registry, parsed, in resolver order (root, general, other domains)."""
    display = display_for(registries_dir, project_root)
    out: list = []
    for name in registries:
        for path in registry_files_in(Path(registries_dir), f"{name}.md", domains):
            out.append(parse_file(path, name, display=display(path)))
    return out


def collect_entries(registries_dir: Path, *, project_root: Optional[Path] = None,
                    registries: Iterable[str] = REGISTRIES, domains: Optional[Iterable[str]] = None) -> list:
    return [e for pf in parsed_files(registries_dir, project_root=project_root, registries=registries,
                                     domains=domains) for e in pf.entries]


def tier_label(entry: Entry) -> str:
    return "Universal" if entry.tier == "universal" else entry.tier


def clean_title(title: str, limit: int = 96) -> str:
    t = re.sub(r"\s+", " ", title).strip()
    return t if len(t) <= limit else t[:limit - 1] + "…"


def digest_title(entry: Entry) -> str:
    base = f"{entry.date} — {entry.title}" if entry.registry == "JOURNAL" and entry.date else entry.title
    return clean_title(base)


def sources_files(registries_dir: Path) -> list:
    files: list = []
    for name in REGISTRIES:
        files += registry_files_in(Path(registries_dir), f"{name}.md")
    integration = Path(registries_dir) / "INTEGRATION.md"
    if integration.is_file():
        files.append(integration)
    return sorted(files, key=lambda p: p.relative_to(registries_dir).as_posix())


def sources_sha256(registries_dir: Path) -> str:
    """The R6 hash: every file the digest reads, sorted by relative path, normalised bytes."""
    h = hashlib.sha256()
    for path in sources_files(registries_dir):
        h.update(path.relative_to(registries_dir).as_posix().encode("utf-8") + b"\0")
        h.update(normalise_bytes(path.read_bytes()) + b"\0")
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Layout state (I-1)
# ---------------------------------------------------------------------------
def layout_state(registries_dir: Path) -> LayoutState:
    d = Path(registries_dir)
    roots = {name: d / f"{name}.md" for name in REGISTRIES}
    present = {name: p for name, p in roots.items() if p.is_file()}
    if not present:
        return LayoutState("absent", "none", LAYOUT_CURRENT, [], REMEDY_DOCTOR)
    parsed = {name: parse_file(p, name) for name, p in present.items()}
    markers = {pf.marker for pf in parsed.values()}
    found = {m for m in markers if m != "none"}
    marker = "none" if not found else (next(iter(found)) if len(found) == 1 else "mixed")

    reasons: list = [f"registry-missing:{name}" for name in REGISTRIES if name not in present]
    if reasons:
        return LayoutState("unknown", marker, LAYOUT_CURRENT, reasons, REMEDY_DOCTOR)
    other = sorted(m for m in markers if m not in ("none", str(LAYOUT_CURRENT)))
    if other:
        return LayoutState("unknown", marker, LAYOUT_CURRENT, [f"marker-value:{m}" for m in other], REMEDY_AGREE)
    if len(markers) > 1:
        return LayoutState("unknown", marker, LAYOUT_CURRENT, ["mixed-markers"], REMEDY_AGREE)
    if markers == {"none"}:
        return LayoutState("pending", "none", LAYOUT_CURRENT, [], REMEDY_MIGRATE)

    for name, pf in parsed.items():
        for line, project in pf.project_headings:
            reasons.append(f"project-heading:{name}:{line}")
        for e in pf.below_pointer:
            reasons.append(f"below-pointer:{name}:{e.line}")
        for line in pf.leftover_lines:
            if pf.pointer_line is not None and line > pf.pointer_line:
                reasons.append(f"below-pointer:{name}:{line}")
        if not (d / name / "general.md").is_file():
            reasons.append(f"general-missing:{name}")
    if reasons:
        return LayoutState("stale-sync", marker, LAYOUT_CURRENT, reasons, REMEDY_MIGRATE)
    return LayoutState("current", marker, LAYOUT_CURRENT, [], "")


# ---------------------------------------------------------------------------
# Tokens and plugin keys
# ---------------------------------------------------------------------------
def load_project_tokens(project_root: Path) -> tuple:
    """(tokens, allowed) from ``<project>/.claude/.project-tokens.json``; both empty when absent."""
    try:
        data = json.loads((Path(project_root) / ".claude" / ".project-tokens.json").read_bytes().decode("utf-8-sig"))
    except (OSError, ValueError):
        return (), ()
    if not isinstance(data, dict):
        return (), ()
    tokens = tuple(t for t in data.get("tokens", []) if isinstance(t, str) and t.strip())
    allowed = tuple(t for t in data.get("allowed", []) if isinstance(t, str) and t)
    return tokens, allowed


def plugin_universal_keys(plugin_root: Path) -> dict:
    """The Universal-tier keys of the plugin's own root registries, per registry."""
    keys: dict = {}
    for name in REGISTRIES:
        path = Path(plugin_root) / ".claude" / "registries" / f"{name}.md"
        if path.is_file():
            keys[name] = frozenset(e.key for e in parse_file(path, name).entries
                                   if e.tier == "universal" and e.key)
    return keys


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------
def _loc(e: Entry) -> str:
    return f"{e.file}:{e.line}"


def rule_r1(entries: Sequence[Entry]) -> list:
    out = []
    for e in entries:
        if e.kind != "entry" or e.status == ARCHIVED or e.has_body:
            continue
        what = "an `Apply when:` field with text" if e.registry == "JOURNAL" else "a body after the separator"
        out.append(Finding("R1", e.file, e.line, e.key, f"entry {e.title!r} has no body: it needs {what}",
                           "restore the body, or append an indented `Status: archived-title-only` line "
                           "(registry_append.py --archive-title-only)", "finding"))
    return out


def rule_r2(entries: Sequence[Entry]) -> list:
    groups: dict = {}
    for e in entries:
        if e.key:
            groups.setdefault((e.registry, e.key), []).append(e)
    out = []
    for (_reg, key), group in groups.items():
        if len(group) > 1:
            where = ", ".join(_loc(e) for e in group)
            out.append(Finding("R2", group[0].file, group[0].line, key,
                               f"duplicate title {key!r} at {where}",
                               "keep one entry; rename the other or fold it into a Correction line", "finding"))
    return out


def rule_a1(entries: Sequence[Entry]) -> list:
    return [Finding("A1", e.file, e.line, e.key, f"malformed entry {e.title!r}: {'; '.join(e.malformed)}",
                    "fix the heading, separator or required field", "finding")
            for e in entries if e.kind == "entry" and e.malformed]


def _token_hit(text: str, tokens: Sequence[str], allowed: Sequence[str]) -> Optional[str]:
    for a in sorted(allowed, key=len, reverse=True):
        text = text.replace(a, " ")
    low = text.lower()
    for t in tokens:
        if t.lower() in low:
            return t
    return None


def rule_r3(files: Sequence[ParsedFile], tokens: Sequence[str], allowed: Sequence[str],
            plugin_keys: Any) -> list:
    out = []
    for pf in files:
        if pf.kind != "root":
            continue
        for line, name in pf.project_headings:
            out.append(Finding("R3", pf.file, line, "", f"project heading '## Project: {name}' in a root file",
                               "move the project entries into a domain file", "finding"))
        for e in pf.below_pointer:
            out.append(Finding("R3", e.file, e.line, e.key, f"entry {e.title!r} sits below the pointer section",
                               "move it into a domain file", "finding"))
        for line in pf.leftover_lines:
            if pf.pointer_line is not None and line > pf.pointer_line:
                out.append(Finding("R3", pf.file, line, "", "leftover section below the pointer section",
                                   "leftovers belong in general.md", "finding"))
        if isinstance(plugin_keys, Mapping):
            keys = plugin_keys.get(pf.registry)
        else:
            keys = plugin_keys
        for e in pf.entries:
            if e.tier != "universal" or not e.key:
                continue
            hit = _token_hit(f"{e.title}\n{e.text}", tokens, allowed) if tokens else None
            if hit is not None:
                if keys is None:
                    out.append(Finding("R3", e.file, e.line, e.key,
                                       f"entry {e.title!r} holds the project token {hit!r}; no plugin root resolved, "
                                       "so it cannot be told from a plugin-owned entry",
                                       "re-run with --plugin-root", "advisory", "unverified"))
                elif e.key in keys:
                    out.append(Finding("R3", e.file, e.line, e.key,
                                       f"plugin-owned entry {e.title!r} holds the project token {hit!r}",
                                       "fix it in the plugin, not here", "advisory", "plugin-owned"))
                else:
                    out.append(Finding("R3", e.file, e.line, e.key,
                                       f"client-authored Universal entry {e.title!r} holds the project token {hit!r}",
                                       "move it into a domain file", "finding"))
            elif keys is not None and e.key not in keys:
                out.append(Finding("R3", e.file, e.line, e.key,
                                   f"client-authored Universal entry {e.title!r} has no project token",
                                   "decide whether it is project content; if so, move it", "advisory",
                                   "universal-candidate"))
    return out


def _excluded(ref: str) -> bool:
    norm = ref.replace("\\", "/")
    return any(norm.startswith(p) for p in R4_EXCLUDED_PREFIXES)


def rule_r4(files: Sequence[ParsedFile], candidate_roots: Sequence[Path]) -> list:
    out = []
    for pf in files:
        skip = pf.leftover_range
        for idx, ln in enumerate(pf.lines):
            n = idx + 1
            if pf.fence[idx] or (skip is not None and skip[0] <= n <= skip[1]):
                continue
            seen: set = set()
            for ref in path_references(ln):
                if ref in seen or _excluded(ref):
                    continue
                seen.add(ref)
                rel = ref.replace("\\", "/")
                if not any((Path(r) / rel).exists() for r in candidate_roots):
                    out.append(Finding("R4", pf.file, n, "", ref,
                                       "update or remove the citation (registries are append-only: add a Correction)",
                                       "advisory"))
    return out


def rule_r5(registries_dir: Path, state: str, project_root: Optional[Path]) -> list:
    d = Path(registries_dir)
    display = display_for(d, project_root)
    out = []
    if (d / "INTEGRATION").is_dir():
        out.append(Finding("R5", display(d / "INTEGRATION"), 1, "",
                           "INTEGRATION.md is outside the layout; it has no domain folder",
                           "remove the folder", "finding"))
    for name in REGISTRIES:
        folder = d / name
        if not folder.is_dir() and state not in ("current", "stale-sync"):
            continue
        if not (folder / "general.md").is_file():
            out.append(Finding("R5", display(folder / "general.md"), 1, "", "general.md is missing",
                               "copy the general.md skeleton from the plugin templates", "finding"))
        if not folder.is_dir():
            continue
        for child in sorted(folder.iterdir(), key=lambda p: p.name):
            if child.is_dir():
                out.append(Finding("R5", display(child), 1, "", "nested folder inside a domain folder",
                                   "domain files sit directly in the folder", "finding"))
            elif child.suffix == ".md" and not _SLUG.match(child.stem):
                out.append(Finding("R5", display(child), 1, "",
                                   f"domain file name {child.name!r} is not a lowercase slug",
                                   "rename it, for example backend.md", "finding"))
    return out


def rule_r6(registries_dir: Path, entries: Sequence[Entry], digest_path: Path,
            project_root: Optional[Path]) -> tuple:
    """(findings, digest state) where the state is absent | fresh | stale."""
    if not Path(digest_path).is_file():
        return [], "absent"
    text = normalise_bytes(Path(digest_path).read_bytes()).decode("utf-8", errors="replace")
    display = display_for(Path(registries_dir), project_root)(Path(digest_path))
    reasons = []
    m = _SOURCES_RE.search(text)
    if m is None:
        reasons.append("the sources hash line is missing")
    elif m.group(1).lower() != sources_sha256(registries_dir):
        reasons.append("the sources hash differs from the registry files")
    present = set()
    for ln in text.split("\n"):
        dm = _DIGEST_LINE.match(ln)
        if dm:
            present.add(entry_key(dm.group(1)))
    missing = sorted({e.key for e in entries if e.key and entry_key(digest_title(e)) not in present})
    if missing:
        shown = ", ".join(repr(k) for k in missing[:5]) + (" ..." if len(missing) > 5 else "")
        reasons.append(f"{len(missing)} registry key(s) absent from the digest: {shown}")
    if not reasons:
        return [], "fresh"
    return ([Finding("R6", display, 1, "", "digest is stale: " + "; ".join(reasons),
                     "py -3 .claude/scripts/generate_registry_digest.py", "finding")], "stale")


def entry_findings(registries_dir: Path, *, project_root: Optional[Path] = None) -> list:
    """R1 and R2 only (what the digest generator refuses on)."""
    entries = collect_entries(registries_dir, project_root=project_root)
    return rule_r1(entries) + rule_r2(entries)


# ---------------------------------------------------------------------------
# Structure report
# ---------------------------------------------------------------------------
@dataclass
class StructureReport:
    state: LayoutState
    findings: list
    notices: list
    digest: str                    # absent | fresh | stale

    def exit_code(self, strict: bool = False) -> int:
        if self.state.state != "current":
            return 0
        for f in self.findings:
            if f.severity == "finding" or (strict and f.rule == "R4"):
                return 1
        return 0

    def lines(self, strict: bool = False) -> list:
        out = []
        current = self.state.state == "current"
        if not current:
            out.append(f"advisory: registry layout {self.state.state} — {self.state.remedy}")
        for f in self.findings:
            label = "finding" if (f.severity == "finding" or (strict and current and f.rule == "R4")) else "advisory"
            tag = f"{f.rule} {f.variant}".strip()
            if f.rule == "R4":
                out.append(f"{label}: {tag} {f.file}:{f.line} {f.message}")
            else:
                out.append(f"{label}: {tag} {f.file}:{f.line} {f.message} ({f.remedy})")
        out += self.notices
        if self.digest == "absent":
            out.append("digest: absent")
        return out


def structure_findings(registries_dir: Path, *, project_root: Optional[Path] = None,
                       plugin_root: Optional[Path] = None, plugin_keys: Any = None,
                       tokens: Sequence[str] = (), allowed: Sequence[str] = (),
                       digest_path: Optional[Path] = None) -> list:
    return check_structure(registries_dir, project_root=project_root, plugin_root=plugin_root,
                           plugin_keys=plugin_keys, tokens=tokens, allowed=allowed,
                           digest_path=digest_path).findings


def check_structure(registries_dir: Path, *, project_root: Optional[Path] = None,
                    plugin_root: Optional[Path] = None, plugin_keys: Any = None,
                    tokens: Sequence[str] = (), allowed: Sequence[str] = (),
                    digest_path: Optional[Path] = None) -> StructureReport:
    """Run R1-R6 and A1. ``plugin_keys`` is None when no plugin root resolved (R3 unverified)."""
    d = Path(registries_dir)
    base = Path(project_root) if project_root is not None else d.parent.parent
    state = layout_state(d)
    files = parsed_files(d, project_root=base)
    entries = [e for pf in files for e in pf.entries]
    roots = [base] + ([Path(plugin_root)] if plugin_root is not None else [])
    digest = Path(digest_path) if digest_path is not None else d.parent / DIGEST_RELATIVE
    r6, digest_state = rule_r6(d, entries, digest, base)

    findings = (rule_r1(entries) + rule_r2(entries) + rule_r3(files, tokens, allowed, plugin_keys)
                + rule_r4(files, roots) + rule_r5(d, state.state, base) + r6 + rule_a1(entries))
    if state.state != "current":
        for f in findings:
            f.severity = "advisory"

    notices = []
    for e in entries:
        if e.kind == "legacy":
            notices.append(f"advisory: legacy {e.file}:{e.line}")
    for pf in files:
        for line, _source, _reason in pf.leftover_blocks:
            notices.append(f"advisory: leftover {pf.file}:{line}")
    return StructureReport(state, findings, notices, digest_state)
