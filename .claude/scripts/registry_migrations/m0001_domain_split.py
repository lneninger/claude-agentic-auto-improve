"""
m0001_domain_split -- registry migration 0001: layout 1 (or a stale sync) -> layout 2.

Contract 2026-11-04-domain-split-registries, "Migration 0001" steps 1-6, I-12, "Migration leftover block".

The module PLANS; it never writes. ``build_plan`` returns the files to write, the per-registry report data and, when
the tree cannot be migrated, a refusal. ``verify_plan`` is the I-12 no-loss check on the plan. The runner
(``registry_migrate.py``) owns the order of checks, the hash and the write.

Per registry:
  1. parse the root and the domain files (``_registry_layout`` owns the grammar);
  2. the Universal tier keeps header prose, I-8b sections, fences and plugin-owned entries; a client-authored entry
     that holds a project token moves; a token-free client-authored entry stays and is listed as a candidate;
  3. project content moves verbatim (entries and legacy entries) in the order: the domain file already holding the
     key, a ``Tags:`` value equal to a domain file, the source contract's area, ``general``; prose, non-entry
     sections and tables go verbatim into leftover blocks in ``general.md``; ``## Project:`` lines are removed;
  4. one key in several places is merged field by field, or refused as ``conflicting-entry``;
  5. bodiless keys are listed as orphans with a ready-to-run ``--archive-title-only`` command, never marked;
  6. the root gets the marker and exactly one pointer section; ``general.md`` is created from the skeleton.

Lines are compared after folding line endings, dropping the byte order mark and trimming trailing spaces. The
only lines the migration adds are the marker, the pointer section, the skeleton header, the leftover heading and the
provenance and fence lines of leftover blocks; the only lines it removes are ``project-heading``,
``replaced-sync-section`` and ``merged-duplicate`` lines.
"""

from __future__ import annotations

import collections
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import _registry_layout as rl
from _claude_paths import registry_files_in

NUMBER = "0001"
FROM_LAYOUT = 1
TO_LAYOUT = 2
STATES = ("pending", "stale-sync")

BOM = b"\xef\xbb\xbf"
REASON_PROJECT_HEADING = "project-heading"
REASON_SYNC = "replaced-sync-section"
REASON_MERGED = "merged-duplicate"
ORPHAN_HINT = "recover the body from your own backups, or mark it"
UNRESOLVED_HINT = "re-run with --plugin-root"

_UNIVERSAL_HEADING = re.compile(r"^##[ \t]+Universal", re.IGNORECASE)
_SOURCE_PATH = re.compile(r"[^\s`'\"(),;]+\.md")
_TITLES = {"MECHANISMS": "Mechanisms", "VOCABULARY": "Vocabulary", "JOURNAL": "Journal"}


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@dataclass
class Context:
    project: Path
    registries_dir: Path
    templates_dir: Path
    plugin_keys: Optional[Dict[str, frozenset]]      # None: no separate plugin root resolved
    tokens: Sequence[str] = ()
    allowed: Sequence[str] = ()

    def rel(self, path: Path) -> str:
        try:
            return Path(path).resolve().relative_to(self.project.resolve()).as_posix()
        except (ValueError, OSError):
            return Path(path).as_posix()


@dataclass
class SrcFile:
    path: Path
    rel: str
    kind: str                       # root | domain
    slug: Optional[str]
    raw: bytes
    bom: bool
    eol: str
    pf: Any                         # rl.ParsedFile

    @property
    def lines(self) -> list:
        return self.pf.lines


@dataclass
class Occ:
    entry: Any                      # rl.Entry
    sf: SrcFile
    origin: str                     # domain | universal | move
    order: int
    lines: list
    token_move: bool = False
    dest: str = ""
    reason: str = ""

    @property
    def where(self) -> str:
        return "%s:%d" % (self.sf.rel, self.entry.line)


@dataclass
class PlannedFile:
    rel: str
    path: Path
    before: Optional[bytes]
    after: bytes


@dataclass
class Plan:
    files: List[PlannedFile] = field(default_factory=list)
    registries: Dict[str, dict] = field(default_factory=dict)
    conflicts: List[dict] = field(default_factory=list)
    refusal: Optional[Tuple[str, str]] = None
    accounting: Dict[str, dict] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _nonblank(lines: Sequence[str]) -> collections.Counter:
    return collections.Counter(ln.rstrip() for ln in lines if ln.strip())


def _contains(big: collections.Counter, small: collections.Counter) -> bool:
    return all(big[key] >= count for key, count in small.items())


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _load(path: Path, rel: str, name: str, kind: str, slug: Optional[str]) -> SrcFile:
    raw = Path(path).read_bytes()
    text = rl.normalise_bytes(raw).decode("utf-8")           # UnicodeDecodeError -> the caller refuses
    pf = rl.parse_text(text, name, kind=kind, slug=slug, file=rel)
    return SrcFile(Path(path), rel, kind, slug, raw, raw.startswith(BOM), "\r\n" if b"\r\n" in raw else "\n", pf)


def render_leftover_block(source: str, first: int, last: int, reason: str, lines: Sequence[str]) -> Tuple[list, list]:
    """One migration leftover block (Value Object "Migration leftover block").

    Returns (the block's lines, the lines the migration ADDS: the provenance comment and the two fences). The
    verbatim lines are not in the second list: they are the source's own text.
    """
    longest = max([len(run) for ln in lines for run in re.findall(r"`+", ln)] or [0])
    fence = "`" * max(3, longest + 1)
    comment = "<!-- leftover from %s:%d-%d, %s -->" % (source, first, last, reason)
    return [comment, fence, *lines, fence], [comment, fence, fence]


def area_of(project: Path, raw: str) -> Optional[str]:
    """The first area of the contract a ``Source contract`` field names, or None (seam for tests)."""
    raw = (raw or "").strip()
    if not raw or raw.upper() == "N/A":
        return None
    found = _SOURCE_PATH.search(raw)
    if not found:
        return None
    path = Path(found.group(0)).expanduser()
    if not path.is_absolute():
        path = Path(project) / path
    try:
        if not path.is_file():
            return None
        from derive_area import derive_areas
        areas = derive_areas(path)
    except Exception:
        return None
    return areas[0] if areas else None


def _skeleton_lines(ctx: Context, name: str) -> List[str]:
    path = ctx.templates_dir / name / "general.md"
    try:
        text = path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    except OSError:
        text = ""
    if not text.strip():
        text = ("# %s - general\n\n> Project-tier entries that fit no other domain file. This file is owned by the "
                "project: the plugin sync never writes it.\n" % _TITLES.get(name, name))
    lines = text.rstrip("\n").split("\n")
    return lines + [""]


def _insert_block(lines: list, boundary: int, block: list) -> list:
    """Insert ``block`` after the last non-blank line before ``boundary`` (0-based), one blank line around it."""
    boundary = min(boundary, len(lines))
    at_end = boundary >= len(lines)
    head = list(lines[:boundary])
    while head and not head[-1].strip():
        head.pop()
    new = head + ([""] if head else []) + list(block) + [""]
    if not at_end:
        new += list(lines[boundary:])
    return new


def _place_block(lines: list, name: str, slug: str, block: list, style: str) -> list:
    """Add one moved entry to a domain file's lines: above the leftovers heading, and (for a bullet) above the first
    heading-style entry, because a heading entry swallows every following line."""
    pf = rl.parse_text("\n".join(lines), name, kind="domain", slug=slug)
    boundary = pf.leftover_lines[0] - 1 if pf.leftover_lines else len(lines)
    if style == "bullet":
        headings = [e.line for e in pf.entries if lines[e.line - 1].lstrip().startswith("#")]
        if headings:
            boundary = min(boundary, min(headings) - 1)
    return _insert_block(lines, boundary, block)


def _apply_edits(lines: Sequence[str], edits: Dict[int, Tuple[int, list]]) -> list:
    """Replace line ranges (1-based, inclusive) by new lines; an empty list deletes the range."""
    out: list = []
    n = 1
    total = len(lines)
    while n <= total:
        if n in edits:
            end, new = edits[n]
            out += list(new)
            n = end + 1
        else:
            out.append(lines[n - 1])
            n += 1
    return out


def _to_bytes(lines: Sequence[str], sf: Optional[SrcFile]) -> bytes:
    body = "\n".join(lines)
    if not body.endswith("\n"):
        body += "\n"
    eol = sf.eol if sf is not None else "\n"
    body = body.replace("\n", eol)
    return (BOM if (sf is not None and sf.bom) else b"") + body.encode("utf-8")


def _style_of(occ: Occ) -> str:
    first = occ.lines[0].lstrip() if occ.lines else ""
    return "heading" if first.startswith("#") else "bullet"


# ---------------------------------------------------------------------------
# Root analysis (steps 1-3)
# ---------------------------------------------------------------------------
def _analyse_root(sf: SrcFile) -> Tuple[list, list]:
    """Per-line roles of the root (index = line number) and the removed lines found by role.

    A role is ``keep`` (Universal text), ``free`` (project content), ``drop`` (a blank line that goes with a removed
    section) or a ``(removed, reason)`` pair.
    """
    pf = sf.pf
    lines = pf.lines
    total = len(lines)
    events: Dict[int, str] = {}
    for n, _name in pf.project_headings:
        events[n] = "project"
    if pf.pointer_line is not None:
        events[pf.pointer_line] = "pointer"
    for n in range(1, total + 1):
        if not pf.fence[n - 1] and _UNIVERSAL_HEADING.match(lines[n - 1]):
            events.setdefault(n, "universal")
    entry_starts = {e.line for e in pf.entries}
    roles: list = [None] * (total + 2)
    current = "universal"
    pointer_open = False
    for n in range(1, total + 1):
        text = lines[n - 1]
        kind = events.get(n)
        if kind:
            current = kind
            if kind == "project":
                roles[n] = ("removed", REASON_PROJECT_HEADING)
                pointer_open = False
            elif kind == "pointer":
                roles[n] = ("removed", REASON_SYNC)
                pointer_open = True
            else:
                roles[n] = "keep"
                pointer_open = False
            continue
        if n == 1 and pf.marker != "none":
            roles[n] = ("removed", REASON_SYNC)
            continue
        if current == "universal":
            roles[n] = "keep"
        elif current == "project":
            roles[n] = "free"
        else:
            if pointer_open:
                heading = (not pf.fence[n - 1]) and rl._HEADING.match(text)
                if n in entry_starts or heading or pf.fence[n - 1]:
                    pointer_open = False
                else:
                    roles[n] = ("removed", REASON_SYNC) if text.strip() else "drop"
                    continue
            roles[n] = "free"
    return roles, list(events.items())


def _token_hit(ctx: Context, text: str) -> Optional[str]:
    if not ctx.tokens:
        return None
    return rl._token_hit(text, ctx.tokens, ctx.allowed)


# ---------------------------------------------------------------------------
# Group merge (step 4)
# ---------------------------------------------------------------------------
@dataclass
class Merged:
    position: Occ
    base: Occ
    lines: list
    removed: List[Tuple[str, int, str, str]]          # (file, line, reason, text)
    appended: List[str]
    members: List[Occ]


def _fields_of(occ: Occ) -> Dict[str, str]:
    e = occ.entry
    if e.kind == "entry" and e.registry == "JOURNAL":
        return {k: _squash(v) for k, v in e.fields.items()}
    return {"body": _squash(e.text)} if (e.has_body or e.kind == "legacy") and e.text.strip() else {}


def _bullet_head(line: str) -> Optional[Tuple[str, str]]:
    """(title, date tag) of a mechanism / vocabulary bullet line, or None when it is not one."""
    m = rl._BULLET.match(line)
    if not m:
        return None
    tag_text, _has_sep, _body = rl._split_sep(m.group(2))
    return m.group(1).strip(), tag_text.strip()


def _merge_group(group: List[Occ]) -> Tuple[Optional[Merged], Optional[dict]]:
    """Fold the copies of one key into one. Returns (merged, None), or (None, conflict)."""
    rank = {"domain": 0, "universal": 1, "move": 2}
    ordered = sorted(group, key=lambda o: (rank[o.origin], o.order))
    counters = {id(o): _nonblank(o.lines) for o in ordered}

    # Rule 1: one copy holds every line of the others -> it is the kept copy.
    candidates = [o for o in ordered if o.entry.has_body] + [o for o in ordered if not o.entry.has_body]
    base = next((c for c in candidates
                 if all(_contains(counters[id(c)], counters[id(o)]) for o in ordered if o is not c)), None)
    if base is None:
        base = candidates[0]
    others = [o for o in ordered if o is not base]
    resident = [o for o in ordered if o.origin != "move"]
    position = resident[0] if resident else base

    merged_lines = list(base.lines)
    present = collections.Counter(counters[id(base)])
    merged_fields = _fields_of(base)
    removed: list = []
    appended: list = []
    mv = base.entry.registry != "JOURNAL" and base.entry.kind == "entry"
    for other in others:
        head_covered = False
        if not _contains(present, counters[id(other)]):
            hb, ho = merged_lines[0].rstrip(), other.lines[0].rstrip()
            if ho == hb:
                head_covered = False
            elif mv and other.entry.kind == "entry" and _bullet_head(hb) == _bullet_head(ho):
                # The same bold title and date tag; the lines differ only in the body text after the separator,
                # which is compared as the entry's one field below.
                head_covered = True
            else:
                return None, {"key": base.entry.key, "locations": [o.where for o in ordered], "field": "heading",
                              "versions": [hb, ho]}
            theirs = _fields_of(other)
            for fname, value in theirs.items():
                if fname in merged_fields and merged_fields[fname] != value:
                    # M/V: the body is one field, shown by each copy's first line; journal: "<field>: <text>".
                    versions = [hb, ho] if fname == "body" else [
                        "%s: %s" % (fname, merged_fields[fname]), "%s: %s" % (fname, value)]
                    return None, {"key": base.entry.key, "locations": [o.where for o in ordered], "field": fname,
                                  "versions": versions}
            for fname, value in theirs.items():
                merged_fields.setdefault(fname, value)
        mine = collections.Counter()
        for idx, text in enumerate(other.lines):
            if not text.strip():
                continue
            key = text.rstrip()
            if (idx == 0 and head_covered) or present[key] > 0:
                if not (idx == 0 and head_covered):
                    present[key] -= 1
                removed.append((other.sf.rel, other.entry.line + idx, REASON_MERGED, text))
            else:
                if idx == 0:
                    # The heading line is a field (step 4): a heading that is not already in the kept copy is a
                    # difference to refuse, never a line to append.
                    return None, {"key": base.entry.key, "locations": [o.where for o in ordered], "field": "heading",
                                  "versions": [merged_lines[0].rstrip(), text.rstrip()]}
                merged_lines.append(text)
                appended.append(text)
                mine[key] += 1
        present.update(mine)
    return Merged(position, base, merged_lines, removed, appended, ordered), None


# ---------------------------------------------------------------------------
# One registry
# ---------------------------------------------------------------------------
def _display_command(ctx: Context, name: str, title: str) -> str:
    quoted = title.replace("'", "''")
    return ("py -3 .claude/scripts/registry_append.py --project '%s' --registry %s --archive-title-only '%s'"
            % (str(ctx.project).replace("'", "''"), name.lower(), quoted))


def _new_report() -> dict:
    return {"kept": [], "moved": [], "merged_duplicates": [], "appended_merge_lines": [], "bodiless_orphans": [],
            "unclassified": [], "token_entries_moved": [], "plugin_owned_token_entries": [],
            "unverified_token_entries": [], "universal_candidates": [], "unmovable_token_lines": [],
            "legacy_entries": [], "leftovers": [], "removed_lines": [], "conflicts": [],
            "counts": {"in": 0, "kept": 0, "moved": 0, "merged_away": 0, "out": 0}}


def _plan_registry(ctx: Context, name: str, plan: Plan) -> None:
    report = _new_report()
    plan.registries[name] = report
    paths = registry_files_in(ctx.registries_dir, name + ".md")
    files: List[SrcFile] = []
    for path in paths:
        is_root = path.name == name + ".md" and path.parent == ctx.registries_dir
        try:
            files.append(_load(path, ctx.rel(path), name, "root" if is_root else "domain", None if is_root else path.stem))
        except UnicodeDecodeError:
            plan.refusal = ("unknown-layout", "%s is not valid UTF-8, so it cannot be migrated safely" % ctx.rel(path))
            return
    root = next(f for f in files if f.kind == "root")
    domains = [f for f in files if f.kind == "domain"]
    domain_slugs = {f.slug for f in domains} | {"general"}

    roles, _events = _analyse_root(root)
    root_lines = root.lines
    plugin_keys = ctx.plugin_keys.get(name, frozenset()) if ctx.plugin_keys is not None else None

    # --- occurrences ---------------------------------------------------------------------------
    occs: List[Occ] = []
    order = 0
    for sf in domains:
        for e in sf.pf.entries:
            occs.append(Occ(e, sf, "domain", order, sf.lines[e.line - 1:e.end_line]))
            order += 1
    for e in root.pf.entries:
        lines = root_lines[e.line - 1:e.end_line]
        occ = Occ(e, root, "universal", order, lines)
        order += 1
        if e.tier == "universal":
            hit = _token_hit(ctx, "%s\n%s" % (e.title, e.text))
            if hit is not None:
                if plugin_keys is None:
                    report["unverified_token_entries"].append(e.key)
                elif e.key in plugin_keys:
                    report["plugin_owned_token_entries"].append(e.key)
                else:
                    occ.origin, occ.token_move = "move", True
                    report["token_entries_moved"].append(e.key)
            elif plugin_keys is not None and e.key not in plugin_keys and e.key:
                report["universal_candidates"].append(e.key)
        else:
            occ.origin = "move"
        occs.append(occ)

    for occ in occs:
        if occ.origin == "move":
            for n in range(occ.entry.line, occ.entry.end_line + 1):
                roles[n] = "moved"

    # --- token lines outside any entry (stay) ----------------------------------------------------
    if ctx.tokens:
        for n in range(1, len(root_lines) + 1):
            if roles[n] == "keep" and root_lines[n - 1].strip() and not root.pf.fence[n - 1] \
                    and not any(o.entry.line <= n <= o.entry.end_line for o in occs if o.sf is root):
                if _token_hit(ctx, root_lines[n - 1]) is not None:
                    report["unmovable_token_lines"].append({"file": root.rel, "line": n, "text": root_lines[n - 1]})

    # --- leftover runs ---------------------------------------------------------------------------
    runs: List[dict] = []
    current: Optional[dict] = None

    def close_run() -> None:
        nonlocal current
        if current is not None:
            ns = current["lines"]
            while ns and not root_lines[ns[-1] - 1].strip():
                ns.pop()
            while ns and not root_lines[ns[0] - 1].strip():
                ns.pop(0)
            if ns:
                runs.append(current)
            current = None

    for n in range(1, len(root_lines) + 1):
        if roles[n] != "free":
            if roles[n] != "drop":
                close_run()
            continue
        text = root_lines[n - 1]
        heading = None if root.pf.fence[n - 1] else rl._HEADING.match(text)
        if current is None:
            current = {"reason": "non-entry-heading" if heading else "project-prose",
                       "level": len(heading.group(1)) if heading else None, "lines": [n]}
        elif heading and (current["level"] is None or len(heading.group(1)) <= current["level"]):
            close_run()
            current = {"reason": "non-entry-heading", "level": len(heading.group(1)), "lines": [n]}
        else:
            current["lines"].append(n)
    close_run()

    # --- groups (step 4) and destinations (step 3) ---------------------------------------------
    by_key: Dict[str, List[Occ]] = collections.OrderedDict()
    singles: List[Occ] = []
    for occ in occs:
        if occ.entry.key:
            by_key.setdefault(occ.entry.key, []).append(occ)
        else:
            singles.append(occ)

    edits: Dict[str, Dict[int, Tuple[int, list]]] = collections.defaultdict(dict)
    # I-12 (entries): per key, every input line of every copy, minus the lines a merge removed as duplicates
    key_lines: Dict[str, collections.Counter] = {}
    placements: List[dict] = []              # moved survivors, in source order
    survivors: List[Tuple[Occ, str]] = []    # (occ, final file rel or dest rel)
    merged_away = 0

    def classify(occ: Occ) -> Tuple[str, str]:
        e = occ.entry
        for tag in [t.strip("`") for t in re.split(r"[,\s;]+", (e.tags or "").lower()) if t.strip("`")]:
            if tag in domain_slugs:
                return tag, "tags"
        area = area_of(ctx.project, e.source_contract)
        if area and area in domain_slugs:
            return area, "source-contract-area"
        return "general", "general-default"

    groups = list(by_key.values()) + [[o] for o in singles]
    for group in groups:
        if len(group) == 1:
            occ = group[0]
            if occ.entry.key:
                key_lines[occ.entry.key] = _nonblank(occ.lines)
            if occ.origin == "move":
                slug, reason = classify(occ)
                occ.dest, occ.reason = slug, reason
                placements.append({"occ": occ, "lines": occ.lines, "slug": slug, "reason": reason, "key": occ.entry.key})
            else:
                survivors.append((occ, occ.sf.rel))
            continue
        merged, conflict = _merge_group(group)
        if conflict is not None:
            report["conflicts"].append(conflict)
            plan.conflicts.append(dict(conflict, registry=name))
            continue
        merged_away += len(group) - 1
        merged_key = group[0].entry.key
        if merged_key:
            total: collections.Counter = collections.Counter()
            for member in group:
                total.update(_nonblank(member.lines))
            dropped = _nonblank([r[3] for r in merged.removed])
            total.subtract(dropped)
            key_lines[merged_key] = +total
        pos = merged.position
        for other in group:
            if other is pos or other.origin == "move":
                continue
            edits[other.sf.rel][other.entry.line] = (other.entry.end_line, [])
        where: str
        if pos.origin == "move":
            slug, reason = classify(merged.base)
            pos.dest, pos.reason = slug, reason
            placements.append({"occ": pos, "lines": merged.lines, "slug": slug, "reason": reason,
                               "key": pos.entry.key, "origin_where": merged.base.where})
            where = "%s/%s.md" % (name, slug)
        else:
            if merged.lines != pos.lines:
                edits[pos.sf.rel][pos.entry.line] = (pos.entry.end_line, merged.lines)
            survivors.append((pos, pos.sf.rel))
            where = pos.where
        report["merged_duplicates"].append({"key": pos.entry.key, "kept_at": where,
                                            "from": [o.where for o in merged.members if o is not merged.base],
                                            "lines": [r[3] for r in merged.removed]})
        if merged.appended:
            report["appended_merge_lines"].append({"key": pos.entry.key, "kept_at": where, "lines": merged.appended})
        for file_, line_no, reason, text in merged.removed:
            report["removed_lines"].append({"file": file_, "line": line_no, "reason": reason, "text": text})

    if plan.conflicts and any(c["registry"] == name for c in plan.conflicts):
        return

    # --- root output ---------------------------------------------------------------------------
    added = collections.Counter()
    removed = collections.Counter()
    for item in report["removed_lines"]:
        removed[item["text"].rstrip()] += 1
    kept_root: list = []
    root_edits = edits.get(root.rel, {})
    n = 1
    while n <= len(root_lines):
        if n in root_edits:
            end, new = root_edits[n]
            kept_root += list(new)
            n = end + 1
            continue
        role = roles[n]
        if role == "keep":
            kept_root.append(root_lines[n - 1])
        elif isinstance(role, tuple) and root_lines[n - 1].strip():
            report["removed_lines"].append({"file": root.rel, "line": n, "reason": role[1], "text": root_lines[n - 1]})
            removed[root_lines[n - 1].rstrip()] += 1
        n += 1
    while kept_root and not kept_root[-1].strip():
        kept_root.pop()
    pointer = rl.pointer_section(name).rstrip("\n").split("\n")
    root_out = [rl.MARKER, ""] + kept_root + [""] + pointer + [""]
    added.update(_nonblank([rl.MARKER] + pointer))

    # --- domain outputs --------------------------------------------------------------------------
    outputs: Dict[str, dict] = {}
    outputs[root.rel] = {"sf": root, "path": root.path, "lines": root_out}
    leftover_blocks: List[list] = []
    for run in runs:
        ns = run["lines"]
        block, add = render_leftover_block(root.rel, ns[0], ns[-1], run["reason"], [root_lines[i - 1] for i in ns])
        leftover_blocks.append(block)
        added.update(_nonblank(add))
        report["leftovers"].append({"source": "%s:%d-%d" % (root.rel, ns[0], ns[-1]), "reason": run["reason"],
                                    "lines": [root_lines[i - 1] for i in ns]})

    by_slug: Dict[str, list] = collections.defaultdict(list)
    for placement in placements:
        by_slug[placement["slug"]].append(placement)
    slugs = {f.slug for f in domains} | {"general"}
    existing = {f.slug: f for f in domains}
    for slug in sorted(slugs):
        sf = existing.get(slug)
        if sf is not None:
            lines = _apply_edits(sf.lines, edits.get(sf.rel, {}))
            rel_path, path = sf.rel, sf.path
        else:
            lines = _skeleton_lines(ctx, name)
            added.update(_nonblank(lines))
            path = ctx.registries_dir / name / (slug + ".md")
            rel_path = ctx.rel(path)
        for placement in by_slug.get(slug, []):
            style = "heading" if placement["lines"][0].lstrip().startswith("#") else "bullet"
            lines = _place_block(lines, name, slug, placement["lines"], style)
        if slug == "general" and leftover_blocks:
            pf = rl.parse_text("\n".join(lines), name, kind="domain", slug=slug)
            body = list(lines)
            while body and not body[-1].strip():
                body.pop()
            if not pf.leftover_lines:
                body += ["", rl.LEFTOVERS_HEADING]
                added.update(_nonblank([rl.LEFTOVERS_HEADING]))
            for block in leftover_blocks:
                body += [""] + block
            lines = body + [""]
        outputs[rel_path] = {"sf": sf, "path": path, "lines": lines}

    # --- report data ---------------------------------------------------------------------------
    moved_count = 0
    for placement in placements:
        occ: Occ = placement["occ"]
        e = occ.entry
        to = "%s/%s.md" % (name, placement["slug"])
        report["moved"].append({"key": e.key, "from": occ.where, "to": to, "reason": placement["reason"]})
        if placement["reason"] == "general-default":
            report["unclassified"].append(e.key)
        if e.kind == "legacy":
            report["legacy_entries"].append({"key": e.key, "from": occ.where, "to": to})
        moved_count += 1
    for occ, location in survivors:
        report["kept"].append({"key": occ.entry.key, "file": location})
        if occ.entry.kind == "legacy":
            report["legacy_entries"].append({"key": occ.entry.key, "from": occ.where, "to": location})

    # --- files, orphans, accounting -------------------------------------------------------------
    dst = collections.Counter()
    out_keys: List[str] = []
    out_entries: List[dict] = []
    for rel_path, out in sorted(outputs.items()):
        sf, path, lines = out["sf"], out["path"], out["lines"]
        dst.update(_nonblank(lines))
        data = _to_bytes(lines, sf)
        if sf is None or data != sf.raw:
            plan.files.append(PlannedFile(rel_path, path, sf.raw if sf is not None else None, data))
        pf = rl.parse_text("\n".join(lines), name, kind="root" if out["sf"] is root else "domain",
                           slug=None if out["sf"] is root else path.stem, file=rel_path)
        out_keys += [e.key for e in pf.entries]
        for e in pf.entries:
            span = pf.lines[e.line - 1:e.end_line]
            out_entries.append({"key": e.key, "location": "%s:%d" % (rel_path, e.line),
                                "first_line": span[0].rstrip() if span else "", "lines": _nonblank(span)})
        if out["sf"] is not root:
            for e in pf.entries:
                if e.kind == "entry" and e.status != rl.ARCHIVED and not e.has_body:
                    report["bodiless_orphans"].append({"key": e.key, "location": "%s:%d" % (rel_path, e.line),
                                                       "hint": ORPHAN_HINT,
                                                       "command": _display_command(ctx, name, e.title)})
    src = collections.Counter()
    for sf in files:
        src.update(_nonblank(sf.lines))
    in_count = len(occs)
    report["counts"] = {"in": in_count, "kept": in_count - merged_away - moved_count, "moved": moved_count,
                        "merged_away": merged_away, "out": in_count - merged_away}
    plan.accounting[name] = {"src": src, "dst": dst, "added": added, "removed": removed,
                             "in_keys": sorted({o.entry.key for o in occs}), "out_keys": out_keys,
                             "expected_out": in_count - merged_away,
                             "key_lines": key_lines, "out_entries": out_entries}


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def build_plan(ctx: Context) -> Plan:
    plan = Plan()
    for name in rl.REGISTRIES:
        _plan_registry(ctx, name, plan)
        if plan.refusal is not None:
            return plan
    if plan.conflicts:
        plan.refusal = ("conflicting-entry", _conflict_message(plan.conflicts))
        plan.files = []
        return plan
    plan.files.sort(key=lambda f: f.rel)
    return plan


def _conflict_message(conflicts: Sequence[dict]) -> str:
    parts = []
    for c in conflicts:
        parts.append("%s %r at %s differs in field %r (%s)" % (
            c["registry"], c["key"], ", ".join(c["locations"]), c["field"], " | ".join(v for v in c["versions"])))
    return ("; ".join(parts) + ". Way out: on layout 1 keep one version, rename one title, or fold one version into a "
            "`Correction` line; commit; re-run the dry-run.")


class PlanProblem(str):
    """The message of a failed plan check; ``code`` is the refusal code the runner reports it under."""
    code = "content-loss-detected"


class ConflictingEntryProblem(PlanProblem):
    code = "conflicting-entry"


def _duplicate_output_keys(acc: dict) -> List[str]:
    """One message per key held by two or more output entries, naming each location and its first line."""
    seen: Dict[str, List[dict]] = collections.OrderedDict()
    for entry in acc.get("out_entries", []):
        if entry["key"]:
            seen.setdefault(entry["key"], []).append(entry)
    return ["%r is held by %s" % (key, " and ".join("%s (%s)" % (e["location"], e["first_line"]) for e in entries))
            for key, entries in seen.items() if len(entries) > 1]


def verify_plan(plan: Plan) -> Optional[str]:
    """The I-12 check on the plan: None when nothing is lost, otherwise the message of the refusal.

    The message is a ``PlanProblem``: its ``code`` is ``content-loss-detected``, or ``conflicting-entry`` when the plan
    still holds two output entries with one key. Per registry the check is the multiset of lines (per result), the key
    set and count, and, per key, that the output entry holds every input line of every copy except the lines a merge
    removed as duplicates.
    """
    duplicates: List[str] = []
    for name, acc in plan.accounting.items():
        duplicates += ["%s: %s" % (name, msg) for msg in _duplicate_output_keys(acc)]
    if duplicates:
        return ConflictingEntryProblem("; ".join(duplicates) + ". Two output entries with one key would be a copy "
                                       "the migration did not merge; nothing was written.")
    problems: List[str] = []
    for name, acc in plan.accounting.items():
        expected = collections.Counter(acc["src"])
        expected.update(acc["added"])
        for line, count in acc["removed"].items():
            if expected[line] < count:
                problems.append("%s: a removed line is not in the source or the added lines: %r" % (name, line))
        expected.subtract(acc["removed"])
        expected = +expected
        dst = +acc["dst"]
        if expected != dst:
            missing = sorted((expected - dst).elements())[:5]
            extra = sorted((dst - expected).elements())[:5]
            problems.append("%s: lines missing from the result: %s; unexpected lines in the result: %s" % (
                name, missing or "none", extra or "none"))
        if set(acc["out_keys"]) != set(acc["in_keys"]):
            problems.append("%s: the entry keys of the result differ from the source (%d in, %d out)" % (
                name, len(acc["in_keys"]), len(acc["out_keys"])))
        if len(acc["out_keys"]) != acc["expected_out"]:
            problems.append("%s: %d entries in the result, %d expected (in = out + merged away)" % (
                name, len(acc["out_keys"]), acc["expected_out"]))
        by_key = {e["key"]: e for e in acc.get("out_entries", []) if e["key"]}
        for key, needed in acc.get("key_lines", {}).items():
            held = by_key.get(key)
            if held is None:
                continue                                   # a missing key is reported by the key-set check above
            if not _contains(held["lines"], needed):
                absent = sorted((needed - held["lines"]).elements())[:3]
                problems.append("%s: the output entry %r at %s lacks input lines: %s" % (
                    name, key, held["location"], absent))
    return PlanProblem("; ".join(problems)) if problems else None
