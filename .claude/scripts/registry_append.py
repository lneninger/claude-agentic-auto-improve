#!/usr/bin/env python3
"""
registry_append.py -- the single write path of the registries (Command "Append registry entry").

    registry_append.py --project <root> --registry mechanisms|vocabulary|journal --from-file <entry.md|->
                       [--universal | --domain <slug> [--create-domain]]
    registry_append.py --project <root> --registry <r> --from-file <text|-> --correction-of "<title>"
                       [--date YYYY-MM-DD] [--source <text>]
    registry_append.py --project <root> --registry <r> --archive-title-only "<title>"

A plain append adds one entry. The domain choice (anything but ``--universal``) is: ``--domain`` when that file
exists (or ``--create-domain``), else the area of the entry's source contract (``derive_area``) when that domain
file exists, else ``general``; the choice is printed.

Placement:
    current          ``--universal`` -> the end of the Universal tier, before the pointer; otherwise the end of the
                     chosen domain file's entries, above the leftovers heading when there is one.
    pending / stale-sync
                     a non-Universal entry goes to a domain file (``general.md`` is created from the skeleton when
                     missing; an unknown ``--domain`` falls back to ``general`` and is named) and is NEVER written
                     into a root file. ``--universal`` goes to the end of the root's Universal tier (before a synced
                     pointer, else before the first ``## Project:``, else the end of the file). Both print
                     ``advisory: registry layout <state> -- appended to <file>:<line>; run registry_migrate.py
                     --dry-run`` and exit 0.

Rejections (stderr ``registry_append: <code>: <message>``):
    exit 2  bodiless-input, duplicate-entry, malformed-input, unknown-domain (current only), no-universal-tier,
            correction-target-missing, archive-target-missing, archive-target-has-body
    exit 3  layout-unknown, registries-absent, project-undetermined, write-failed

Every write goes through ``_preview_apply._atomic_write``. A new journal entry is passed to
``accuracy_update.process_journal_change`` with its signature as ``fresh``, so a post-approval entry written by this
script fires the accuracy signal once even in a journal file the tracker never saw.

``--project`` is required: the script never guesses which project's registries to write (a plugin install would
otherwise write into the plugin's own).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import sys
from pathlib import Path
from typing import Optional

SCRIPTS_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = SCRIPTS_DIR.parent / "templates" / "registries"

STEMS = {"mechanisms": "MECHANISMS", "vocabulary": "VOCABULARY", "journal": "JOURNAL"}
TITLES = {"MECHANISMS": "Mechanisms", "VOCABULARY": "Vocabulary", "JOURNAL": "Journal"}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
BOM = b"\xef\xbb\xbf"
ARCHIVE_LINE = "  - **Status:** archived-title-only"

EXIT_REJECTED = 2
EXIT_FAILED = 3


class Rejection(Exception):
    """A closed-set refusal: the code names it, the exit code says which kind."""

    def __init__(self, code: str, message: str, exit_code: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code


def reject(code: str, message: str) -> Rejection:
    return Rejection(code, message, EXIT_REJECTED)


def fail(code: str, message: str) -> Rejection:
    return Rejection(code, message, EXIT_FAILED)


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------
class TextFile:
    """One registry file as normalised lines plus the bytes-level facts needed to write it back unchanged."""

    def __init__(self, path: Path, lines: list, eol: str, bom: bool):
        self.path = path
        self.lines = lines
        self.eol = eol
        self.bom = bom

    @classmethod
    def read(cls, path: Path) -> "TextFile":
        raw = Path(path).read_bytes()
        bom = raw.startswith(BOM)
        if bom:
            raw = raw[len(BOM):]
        eol = "\r\n" if b"\r\n" in raw else "\n"
        text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
        return cls(Path(path), text.split("\n"), eol, bom)

    @classmethod
    def new(cls, path: Path, text: str) -> "TextFile":
        return cls(Path(path), text.replace("\r\n", "\n").split("\n"), "\n", False)

    def text(self) -> str:
        return "\n".join(self.lines)

    def data(self) -> bytes:
        body = "\n".join(self.lines)
        if not body.endswith("\n"):
            body += "\n"
        body = body.replace("\n", self.eol)
        return (BOM if self.bom else b"") + body.encode("utf-8")


def insert_block(lines: list, boundary: int, block: list) -> tuple:
    """Insert ``block`` after the last non-blank line before ``boundary`` (a 0-based line index, or ``len(lines)``).

    One blank line separates the block from what precedes it and from the section that follows it.
    Returns (new lines, 1-based line number of the block's first line).
    """
    boundary = min(boundary, len(lines))
    at_end = boundary >= len(lines)
    head = list(lines[:boundary])
    while head and not head[-1].strip():
        head.pop()
    start = len(head) + (1 if head else 0)
    new = head + ([""] if head else []) + list(block) + [""]
    if not at_end:
        new += list(lines[boundary:])
    return new, start + 1


def skeleton(stem: str, slug: str) -> str:
    """The text of a new domain file: the shipped skeleton when it can be found, else a minimal header."""
    path = TEMPLATES_DIR / stem / "general.md"
    try:
        text = path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n")
    except OSError:
        text = ""
    if text.strip():
        if slug != "general":
            text = re.sub(r"^(# .*? - )general\b", lambda m: m.group(1) + slug, text, count=1)
        return text if text.endswith("\n") else text + "\n"
    return (f"# {TITLES[stem]} - {slug}\n\n> Project-tier entries of the {slug} domain. This file is owned by the "
            "project: the plugin sync never writes it.\n")


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
def read_input(source: str) -> str:
    try:
        raw = sys.stdin.buffer.read() if source == "-" else Path(source).read_bytes()
    except OSError as exc:
        raise reject("malformed-input", "cannot read the entry file %s: %s" % (source, exc))
    if raw.startswith(BOM):
        raw = raw[len(BOM):]
    return raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def parse_input(text: str, stem: str, rl):
    """The one entry the input holds, with its verbatim lines. Raises malformed-input or bodiless-input."""
    pf = rl.parse_text(text.rstrip() + "\n" if text.strip() else "", stem, kind="domain", slug="input", file="<input>")
    lines = pf.lines
    if not text.strip():
        raise reject("malformed-input", "the entry file is empty")
    if len(pf.entries) != 1:
        raise reject("malformed-input", "the input must hold exactly one entry, found %d" % len(pf.entries))
    entry = pf.entries[0]
    first = next(i for i, ln in enumerate(lines) if ln.strip())
    if entry.line != first + 1:
        raise reject("malformed-input", "text before the entry (line %d): only the entry may be in the input" % (first + 1))
    if any(ln.strip() for ln in lines[entry.end_line:]):
        raise reject("malformed-input", "text after the entry: only one entry may be in the input")
    if entry.kind != "entry":
        raise reject("malformed-input", "a legacy-form entry cannot be appended; use the entry grammar")
    if entry.malformed:
        raise reject("malformed-input", "; ".join(entry.malformed))
    if not entry.title.strip():
        raise reject("malformed-input", "the entry has no title")
    if not entry.has_body and entry.status != rl.ARCHIVED:
        raise reject("bodiless-input", "the entry %r has no body%s" % (
            entry.title, " (an `Apply when:` field with text)" if stem == "JOURNAL" else ""))
    return entry, [ln for ln in lines[first:entry.end_line]]


# ---------------------------------------------------------------------------
# Choices
# ---------------------------------------------------------------------------
def existing_domains(registries_dir: Path, stem: str) -> set:
    folder = registries_dir / stem
    try:
        return {p.stem for p in folder.iterdir() if p.is_file() and p.suffix == ".md"}
    except OSError:
        return set()


def area_domain(entry, project: Path, existing: set) -> Optional[str]:
    """The source contract's area when that domain file exists."""
    raw = (entry.source_contract or "").strip()
    if not raw or raw.upper() == "N/A":
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = project / path
    if not path.is_file():
        return None
    try:
        from derive_area import derive_areas
        areas = derive_areas(path)
    except Exception:
        return None
    for area in areas:
        if area in existing:
            return area
    return None


def choose_domain(args, state: str, registries_dir: Path, stem: str, entry, project: Path) -> tuple:
    """(slug, reason). The caller creates the file when it does not exist."""
    existing = existing_domains(registries_dir, stem)
    if args.domain:
        slug = args.domain
        if slug in existing:
            return slug, "--domain"
        if args.create_domain:
            if not SLUG.match(slug):
                raise reject("unknown-domain", "%r is not a lowercase slug, so no domain file can be created" % slug)
            return slug, "--domain --create-domain (new file)"
        if state == "current":
            raise reject("unknown-domain", "there is no domain file %s/%s.md; use --create-domain to make it"
                         % (stem, slug))
        return "general", "unknown --domain %s fell back to general (no file %s/%s.md; --create-domain makes it)" % (
            slug, stem, slug)
    area = area_domain(entry, project, existing)
    if area:
        return area, "area of the source contract"
    return "general", "default"


def universal_boundary(parsed) -> int:
    """0-based index of the line a Universal entry goes in front of: the pointer, else the first project heading."""
    marks = []
    if parsed.pointer_line is not None:
        marks.append(parsed.pointer_line - 1)
    if parsed.project_headings:
        marks.append(parsed.project_headings[0][0] - 1)
    return min(marks) if marks else len(parsed.lines)


def check_universal_tier(parsed, rl) -> None:
    """A root with no title heading and no entry above its first tier heading has no Universal tier to extend."""
    top = universal_boundary(parsed)
    for idx in range(min(top, len(parsed.lines))):
        if not parsed.fence[idx] and re.match(r"^#[ \t]+\S", parsed.lines[idx]):
            return
    if any(e.tier == "universal" and e.line - 1 < top for e in parsed.entries):
        return
    raise reject("no-universal-tier", "%s holds no title heading and no entry above its first tier heading, so it has "
                 "no Universal tier to extend" % Path(parsed.file).name)


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------
def rel(project: Path, path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(project.resolve()).as_posix()
    except (ValueError, OSError):
        return Path(path).as_posix()


def write_file(tf: TextFile) -> None:
    from _preview_apply import _atomic_write
    error = _atomic_write(tf.path, tf.data())
    if error is not None:
        raise fail("write-failed", "cannot write %s: %s" % (tf.path, error))


def verify_parses(tf: TextFile, rl, stem: str, key: str, *, root: bool, slug: Optional[str]) -> bool:
    parsed = rl.parse_text(tf.text(), stem, kind="root" if root else "domain", slug=slug)
    return any(e.key == key and (not root or e.tier == "universal") for e in parsed.entries)


def duplicate_check(registries_dir: Path, stem: str, entry, rl, project: Path) -> None:
    for existing in rl.collect_entries(registries_dir, project_root=project, registries=[stem]):
        if existing.key == entry.key:
            raise reject("duplicate-entry", "%r already exists at %s:%d" % (entry.title, existing.file, existing.line))


def append_entry(args, state, registries_dir: Path, project: Path, stem: str, rl) -> tuple:
    text = read_input(args.from_file)
    entry, block = parse_input(text, stem, rl)
    duplicate_check(registries_dir, stem, entry, rl, project)

    reason = ""
    if args.universal:
        target = registries_dir / (stem + ".md")
        tf = TextFile.read(target)
        parsed = rl.parse_text(tf.text(), stem, kind="root", file=target.name)
        check_universal_tier(parsed, rl)
        new_lines, line = insert_block(tf.lines, universal_boundary(parsed), block)
        candidate = TextFile(tf.path, new_lines, tf.eol, tf.bom)
        if not verify_parses(candidate, rl, stem, entry.key, root=True, slug=None):
            # A prose section closes the Universal tier: put the entry after its last Universal entry instead.
            universal = [e for e in parsed.entries if e.tier == "universal"]
            if not universal:
                raise fail("write-failed", "the entry would not parse at the end of %s; nothing was written" % target.name)
            new_lines, line = insert_block(tf.lines, universal[-1].end_line, block)
            candidate = TextFile(tf.path, new_lines, tf.eol, tf.bom)
            if not verify_parses(candidate, rl, stem, entry.key, root=True, slug=None):
                raise fail("write-failed", "the entry would not parse in %s; nothing was written" % target.name)
        tf = candidate
        reason = "universal"
    else:
        slug, reason = choose_domain(args, state, registries_dir, stem, entry, project)
        target = registries_dir / stem / (slug + ".md")
        tf = TextFile.read(target) if target.is_file() else TextFile.new(target, skeleton(stem, slug))
        parsed = rl.parse_text(tf.text(), stem, kind="domain", slug=slug, file=target.name)
        boundary = parsed.leftover_lines[0] - 1 if parsed.leftover_lines else len(tf.lines)
        new_lines, line = insert_block(tf.lines, boundary, block)
        candidate = TextFile(tf.path, new_lines, tf.eol, tf.bom)
        if not verify_parses(candidate, rl, stem, entry.key, root=False, slug=slug):
            raise fail("write-failed", "the entry would not parse at the end of %s (a prose section is last); "
                       "nothing was written" % rel(project, target))
        tf = candidate
        print("domain: %s (%s)" % (slug, reason))
    write_file(tf)
    return entry, tf.path, line


def locate(registries_dir: Path, project: Path, stem: str, title: str, rl):
    key = rl.entry_key(title)
    for e in rl.collect_entries(registries_dir, project_root=project, registries=[stem]):
        if e.key == key:
            return e
    return None


def insert_under_entry(project: Path, entry, new_lines: list) -> tuple:
    """Add lines directly under an entry (allowed appends of I-7). Returns (path, first new line number)."""
    path = project / entry.file
    tf = TextFile.read(path)
    at = entry.end_line  # 0-based index of the line after the entry's last non-blank line
    tf.lines[at:at] = new_lines
    write_file(tf)
    return tf.path, at + 1


def correct_entry(args, registries_dir: Path, project: Path, stem: str, rl) -> tuple:
    target = locate(registries_dir, project, stem, args.correction_of, rl)
    if target is None:
        raise reject("correction-target-missing", "no %s entry is titled %r" % (stem, args.correction_of))
    body = [ln.strip() for ln in read_input(args.from_file).strip().split("\n") if ln.strip()]
    if not body:
        raise reject("malformed-input", "the correction text is empty")
    date = args.date or _dt.date.today().isoformat()
    lines = ["  - **Correction (%s, %s):** %s" % (date, args.source or "registry_append", body[0])]
    lines += ["    " + ln for ln in body[1:]]
    return insert_under_entry(project, target, lines)


def archive_entry(args, registries_dir: Path, project: Path, stem: str, rl) -> Optional[tuple]:
    target = locate(registries_dir, project, stem, args.archive_title_only, rl)
    if target is None:
        raise reject("archive-target-missing", "no %s entry is titled %r" % (stem, args.archive_title_only))
    if target.has_body:
        raise reject("archive-target-has-body", "%r at %s:%d has a body; only a bodiless entry can be archived"
                     % (target.title, target.file, target.line))
    if target.status == rl.ARCHIVED:
        print("already archived: %s:%d" % (target.file, target.line))
        return None
    return insert_under_entry(project, target, [ARCHIVE_LINE])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="registry_append.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project", help="the project root (the folder holding .claude/); required")
    p.add_argument("--registry", required=True, choices=sorted(STEMS))
    p.add_argument("--from-file", help="the entry (or correction text) file, or - for standard input")
    p.add_argument("--universal", action="store_true", help="append to the Universal tier of the root file")
    p.add_argument("--domain", help="the domain file (slug) to append to")
    p.add_argument("--create-domain", action="store_true", help="create the --domain file when it does not exist")
    p.add_argument("--correction-of", metavar="TITLE", help="add a Correction line under the entry with this title")
    p.add_argument("--archive-title-only", metavar="TITLE", help="mark the bodiless entry with this title archived")
    p.add_argument("--date", help="the date of a --correction-of line (default: today)")
    p.add_argument("--source", help="the source of a --correction-of line (default: registry_append)")
    return p


def run(args) -> int:
    parser = build_parser()
    if args.universal and args.domain:
        parser.error("--universal and --domain exclude each other")
    if args.create_domain and not args.domain:
        parser.error("--create-domain needs --domain")
    modes = [bool(args.correction_of), bool(args.archive_title_only)]
    if all(modes):
        parser.error("--correction-of and --archive-title-only exclude each other")
    if args.archive_title_only:
        if args.from_file or args.universal or args.domain:
            parser.error("--archive-title-only takes only --project, --registry and the title")
    elif not args.from_file:
        parser.error("--from-file is required")
    if args.correction_of and (args.universal or args.domain):
        parser.error("--correction-of edits the entry where it is; it takes no --universal or --domain")

    if not args.project or not Path(args.project).is_dir():
        raise fail("project-undetermined", "--project must name an existing project folder (got %r); the script never "
                   "guesses the project" % (args.project or ""))
    project = Path(args.project).resolve()
    os.environ["CLAUDE_PROJECT_DIR"] = str(project)

    try:
        import _registry_layout as rl
        import _preview_apply  # noqa: F401  (named here so a missing module is reported by name)
    except ImportError as exc:
        raise fail("write-failed", "a module registry_append.py needs is missing: %s" % exc)

    registries_dir = project / ".claude" / "registries"
    layout = rl.layout_state(registries_dir)
    if layout.state == "absent":
        raise fail("registries-absent", "no registry file exists under %s; run plugin_doctor.py --fix" % registries_dir)
    if layout.state == "unknown":
        raise fail("layout-unknown", "the registry layout is unknown (%s); %s" % (", ".join(layout.reasons), layout.remedy))
    stem = STEMS[args.registry]

    if args.correction_of:
        path, line = correct_entry(args, registries_dir, project, stem, rl)
        print("%s:%d" % (rel(project, path), line))
        return 0
    if args.archive_title_only:
        done = archive_entry(args, registries_dir, project, stem, rl)
        if done:
            print("%s:%d" % (rel(project, done[0]), done[1]))
        return 0

    entry, path, line = append_entry(args, layout.state, registries_dir, project, stem, rl)
    where = "%s:%d" % (rel(project, path), line)
    print(where)
    if layout.state in ("pending", "stale-sync"):
        print("advisory: registry layout %s — appended to %s; run registry_migrate.py --dry-run"
              % (layout.state, where))
    if stem == "JOURNAL":
        notify_tracker(path, entry)
    return 0


def notify_tracker(path: Path, entry) -> None:
    """Tell the accuracy tracker about the new entry (its signature is ``fresh``). Never fails the append."""
    try:
        import accuracy_update
        accuracy_update.process_journal_change([path], fresh=[accuracy_update.journal_signature(entry.date, entry.title)])
    except Exception as exc:
        sys.stderr.write("registry_append: the entry was written; the accuracy tracker did not run: %s\n" % (exc,))


def main(argv: Optional[list] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except Rejection as rej:
        sys.stderr.write("registry_append: %s: %s\n" % (rej.code, rej.message))
        return rej.exit_code


if __name__ == "__main__":
    sys.exit(main())
