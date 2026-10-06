#!/usr/bin/env python3
"""
working-agreements.py -- SessionStart hook: hand the user's standing rules to the model.

A working agreement is one standing rule about how the assistant works with the
user, kept as one markdown file. When a session opens this hook reads the
agreement files the plugin ships (<plugin>/.claude/agreements/) and any the
project adds (<project>/.claude/agreements/), and prints one JSON envelope whose
``hookSpecificOutput.additionalContext`` holds their text.

Contract: .claude/concepts/2026-10-05-working-agreements-session-start.md

Rules in short:
  * Fail open. Every path exits 0 and writes nothing to stderr. Nothing blocks.
  * Delivers only from a plugin install (or the plugin's own checkout). A vendored
    copy prints nothing and logs vendored-unsupported.
  * A project file named like a shipped one (ignoring case) is skipped; it never
    replaces it.
  * The size limit counts the whole text in UTF-16 code units, the way the host
    counts, closing line included. Whole agreements are dropped, never cut. Project
    agreements go first, then shipped ones other than plain-language, each in
    reverse file-name order. The shipped plain-language agreement is always kept.
  * Project text is shown quoted, and a project title is cleaned, so project text
    cannot pose as a shipped agreement or as a top-level heading.
  * A project file that is not a regular file, that links outside its folder, or that
    is larger than four times the limit is skipped without being read in full.
  * The log records what was printed, not what the host received.

Turn it off for one session with CLAUDE_WORKING_AGREEMENTS=off (also 0, false, no).
"""
from __future__ import annotations

import json
import os
import re
import stat
import sys
import time
import unicodedata
from pathlib import Path

try:
    import _project_paths as pp  # type: ignore
    _PATHS_OK = True
except Exception:  # pragma: no cover - a missing helper must never break a session
    _PATHS_OK = False

PLUGIN_NAME = "agentic-auto-improve"
RULES_NAME = "working-agreements.rules.json"
LOG_NAME = "working-agreements.log"
DEFAULT_MAX_CHARACTERS = 9000
#: Claude Code loses hook text over about 10000 characters, so a configured limit is clamped here.
HOST_CAP_MARGIN = 9500
#: A closing line names at most this many dropped agreements; the rest collapse to a count.
MAX_NAMED_IN_CLOSING = 3
#: A project title is cut to this many characters.
MAX_TITLE_CHARACTERS = 120
#: A project file larger than this many bytes per character of the limit can never fit.
BYTES_PER_LIMIT_CHARACTER = 4
#: An origin label a project title must not carry, so a project cannot pose as the plugin.
FORGED_LABEL = re.compile(r"[(\[] *from +the[^)\]]*[)\]]?", re.IGNORECASE)
ALWAYS_KEPT_SLUG = "plain-language"
OFF_VALUES = {"off", "0", "false", "no"}

OPENING = (
    "Working agreements for this session. These are the user's standing rules for how "
    "to work. Follow them in every message and action, starting with your first reply. "
    "A project's own instructions, and a skill's explicit gate that requires asking the "
    "user (for example the design skill's Open Questions), win over any agreement. "
    "Agreements marked 'from this project' come from the project's own repository."
)

LABEL_SHIPPED = "from the plugin"
LABEL_PROJECT = "from this project"


def ulen(text: str) -> int:
    """Length the way the host counts it: UTF-16 code units."""
    return len(text.encode("utf-16-le", errors="surrogatepass")) // 2


class Agreement:
    """One deliverable rule. The rendered section and its size are computed once."""

    def __init__(self, slug: str, title: str, body: str, origin: str, path: Path):
        self.slug = slug
        self.title = title
        self.origin = origin
        self.path = path
        label = LABEL_SHIPPED if origin == "shipped" else LABEL_PROJECT
        self.part = "## %s (%s)\n\n%s" % (title, label, body)
        self.size = ulen(self.part) + 2  # plus the blank line that separates parts

    @property
    def always_kept(self) -> bool:
        return self.origin == "shipped" and self.slug == ALWAYS_KEPT_SLUG


# --------------------------------------------------------------------------
# logging (lines are buffered and written once at the end; never raises)
# --------------------------------------------------------------------------

_LOG_LINES: list[str] = []


def project_dir() -> Path | None:
    """The project root. Inline twin of _project_paths.project_dir, used when the helper is missing."""
    if _PATHS_OK:
        return pp.project_dir()
    raw = os.environ.get("CLAUDE_PROJECT_DIR")
    if not raw:
        return None
    try:
        return Path(raw).resolve()
    except OSError:
        return Path(raw)


def logs_dir() -> Path:
    """Inline twin of _project_paths.logs_dir, used when the helper is missing."""
    if _PATHS_OK:
        return pp.logs_dir()
    proj = project_dir()
    if proj is not None:
        return proj / ".claude" / "logs"
    return Path.home() / ".claude" / "logs"


def log(line: str) -> None:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _LOG_LINES.append("%s %s\n" % (stamp, line.replace("\n", " ")))


def flush_log() -> None:
    if not _LOG_LINES:
        return
    try:
        directory = logs_dir()
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / LOG_NAME).open("a", encoding="utf-8") as handle:
            handle.write("".join(_LOG_LINES))
    except Exception:
        return
    finally:
        del _LOG_LINES[:]


def is_disabled() -> bool:
    return os.environ.get("CLAUDE_WORKING_AGREEMENTS", "").strip().lower() in OFF_VALUES


# --------------------------------------------------------------------------
# inputs
# --------------------------------------------------------------------------

def read_payload() -> dict:
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_max_characters() -> int:
    """The size limit. A missing or malformed rules file fails SOFT to the default:
    this hook only informs, so it never switches delivery off."""
    try:
        # Only the hook's own folder: never the project, the working directory or the home folder.
        data = json.loads((Path(__file__).resolve().parent / RULES_NAME).read_text(encoding="utf-8-sig"))
        value = data.get("max_characters") if isinstance(data, dict) else None
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return min(value, HOST_CAP_MARGIN)
        raise ValueError("max_characters must be a positive integer, got %r" % (value,))
    except Exception as exc:
        log("rules-load-failed error=%s; built-in default %d used" % (exc, DEFAULT_MAX_CHARACTERS))
        return DEFAULT_MAX_CHARACTERS


def is_plugin_install(plugin_root: Path) -> bool:
    """True when the repository above the hooks folder is this plugin."""
    try:
        manifest = json.loads((plugin_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        return isinstance(manifest, dict) and manifest.get("name") == PLUGIN_NAME
    except Exception:
        return False


def candidate_names(folder: Path) -> list[str]:
    """Agreement file names directly inside a folder, sorted. README, names that begin
    with an underscore or a dot, and non-markdown names are ignored."""
    names = []
    for entry in folder.iterdir():
        name = entry.name
        if name.startswith(("_", ".")) or name.lower() == "readme.md" or not name.lower().endswith(".md"):
            continue
        names.append(name)
    return sorted(names)


def clean_title(raw: str) -> str:
    """Normalise a project title so it cannot carry or rebuild an origin label.

    Compatibility-normalise, drop invisible characters, turn every kind of space into one
    space, then remove any '(from the ...)' fragment repeatedly until nothing changes.
    """
    text = unicodedata.normalize("NFKC", raw)
    text = "".join(" " if ch.isspace() else ch for ch in text
                   if ch.isspace() or unicodedata.category(ch) not in ("Cf", "Cc"))
    text = " ".join(text.split())
    while True:
        stripped = FORGED_LABEL.sub("", text)
        if stripped == text:
            break
        text = stripped
    return " ".join(text.split())


def quote(body: str) -> str:
    """Show every line of a project body quoted, so none can read as a heading or a fence."""
    return "\n".join(">" if not ln.strip() else "> " + ln for ln in body.split("\n"))


def parse_agreement(path: Path, origin: str, max_bytes: int | None) -> tuple[Agreement | None, str, str]:
    """Return (agreement, reason, detail). reason is '' on success."""
    try:
        with open(path, "rb") as handle:
            raw = handle.read() if max_bytes is None else handle.read(max_bytes + 1)
    except OSError as exc:
        return None, "unreadable", str(exc)
    if max_bytes is not None and len(raw) > max_bytes:
        return None, "too-large", "more than %d bytes" % max_bytes
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        return None, "malformed", "not valid UTF-8: %s" % exc
    lines = text.splitlines()
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines):
        return None, "malformed", "empty file"
    first = lines[index].strip()
    if not first.startswith("# ") or not first[2:].strip():
        return None, "malformed", "first non-blank line is not a level-one heading"
    title = first[2:].strip()
    body = "\n".join(lines[index + 1:]).strip()
    if not body:
        return None, "malformed", "no text after the heading"
    if origin == "project":
        title = clean_title(title)
        if not title:
            return None, "malformed", "the title holds only an origin label"
        if "plugin" in title.lower():
            return None, "malformed", "a project title may not mention the plugin"
        title = title[:MAX_TITLE_CHARACTERS].strip()
        body = quote(body)
    return Agreement(path.stem, title, body, origin, path), "", ""


def is_within(child: Path, parent: Path) -> bool:
    try:
        a = os.path.normcase(str(child))
        b = os.path.normcase(str(parent))
        return os.path.commonpath([a, b]) == b
    except ValueError:
        return False


def load_folder(folder: Path, origin: str, shipped_names: dict[str, str],
                max_bytes: int | None = None) -> list[Agreement]:
    """Read one folder. Returns the good agreements; skipped files are logged.

    shipped_names maps a lower-case shipped file name to its real name; a file whose name
    matches one of them, ignoring case, is skipped. A file is skipped unless it is a
    regular file whose real path sits directly inside the folder's real path.
    """
    agreements: list[Agreement] = []
    real_folder = os.path.realpath(folder)
    for name in candidate_names(folder):
        if origin == "project" and not name.isprintable():
            log("agreement-skipped file=%r reason=malformed detail=the file name has a character that cannot be shown" % name)
            continue
        shadowed = shipped_names.get(name.lower())
        if shadowed is not None:
            log("agreement-skipped file=%s reason=shadows-shipped detail=shipped file %s has the same name" % (name, shadowed))
            continue
        entry = folder / name
        try:
            real = os.path.realpath(entry)
            if os.path.normcase(os.path.dirname(real)) != os.path.normcase(real_folder):
                log("agreement-skipped file=%s reason=outside-folder detail=resolves to %s" % (name, real))
                continue
            info = os.stat(real)
        except OSError as exc:
            log("agreement-skipped file=%s reason=unreadable detail=%s" % (name, exc))
            continue
        if not stat.S_ISREG(info.st_mode):
            log("agreement-skipped file=%s reason=unreadable detail=not a regular file" % name)
            continue
        if max_bytes is not None and info.st_size > max_bytes:
            log("agreement-skipped file=%s reason=too-large detail=%d bytes, limit %d" % (name, info.st_size, max_bytes))
            continue
        agreement, reason, detail = parse_agreement(Path(real), origin, max_bytes)
        if agreement is None:
            log("agreement-skipped file=%s reason=%s detail=%s" % (name, reason, detail))
            continue
        agreement.path = entry
        agreement.slug = entry.stem
        agreements.append(agreement)
    return agreements


# --------------------------------------------------------------------------
# assembly
# --------------------------------------------------------------------------

def closing_text(named: list[Agreement], more_by_folder: dict[str, int]) -> str:
    """The closing line: a few names with paths, then one count per folder for the rest."""
    parts = ["%s (%s)" % (a.title, a.path) for a in named]
    if more_by_folder:
        where = ", ".join("%d in %s" % (n, folder) for folder, n in more_by_folder.items())
        parts.append("and %d more (%s)" % (sum(more_by_folder.values()), where))
    return "Not delivered because of the size limit: %s. Read the file if a task touches it." % "; ".join(parts)


def closing_line(dropped: list[Agreement], compact: bool = False) -> str:
    """Closing line for a dropped list. compact names none: the last resort when the list does not fit."""
    named = [] if compact else dropped[:MAX_NAMED_IN_CLOSING]
    folders: dict[str, int] = {}
    for a in dropped[len(named):]:
        key = str(a.path.parent)
        folders[key] = folders.get(key, 0) + 1
    return closing_text(named, folders)


def assemble(delivered: list[Agreement], dropped: list[Agreement], compact: bool = False) -> str:
    parts = [OPENING] + [a.part for a in delivered]
    if dropped:
        parts.append(closing_line(dropped, compact))
    return "\n\n".join(parts)


def fit(shipped: list[Agreement], project: list[Agreement], limit: int) -> tuple[list[Agreement], list[Agreement], str]:
    """Drop whole agreements, in the contract's order, until the text fits.

    Sizes are kept as running totals, so the work grows with the input, not with its square.
    The closing line is re-measured after every drop, because it is part of the text.
    """
    everyone = shipped + project
    # Drop order: project in reverse name order, then shipped (not always-kept) in reverse name order.
    drop_order = list(reversed(project)) + [a for a in reversed(shipped) if not a.always_kept]
    total = ulen(OPENING) + sum(a.size for a in everyone)
    dropped: list[Agreement] = []
    dropped_ids: set[int] = set()
    closing_size = 0
    named: list[Agreement] = []
    more_by_folder: dict[str, int] = {}
    for victim in drop_order:
        if total + closing_size <= limit:
            break
        dropped.append(victim)
        dropped_ids.add(id(victim))
        total -= victim.size
        if len(named) < MAX_NAMED_IN_CLOSING:
            named.append(victim)
        else:
            key = str(victim.path.parent)
            more_by_folder[key] = more_by_folder.get(key, 0) + 1
        closing_size = ulen(closing_text(named, more_by_folder)) + 2
    delivered = [a for a in everyone if id(a) not in dropped_ids]
    text = assemble(delivered, dropped)
    if dropped and ulen(text) > limit:
        # Last resort: a per-folder count in place of any names.
        compact = assemble(delivered, dropped, compact=True)
        if ulen(compact) < ulen(text):
            text = compact
    return delivered, dropped, text


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------

def emit(text: str) -> None:
    """Write the envelope. A closed or broken output never raises: stdout goes to the null device."""
    payload = json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": text,
        }
    }, ensure_ascii=True)
    try:
        sys.stdout.write(payload)
        sys.stdout.flush()
    except BaseException:
        try:
            fd = os.open(os.devnull, os.O_WRONLY)
            if fd != 1:
                os.dup2(fd, 1)
                os.close(fd)
        except BaseException:
            pass
        try:
            sys.stdout = open(os.devnull, "w")
        except BaseException:
            pass


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------

def run() -> int:
    if is_disabled():
        return 0

    payload = read_payload()
    session_id = str(payload.get("session_id") or "")
    source = str(payload.get("source") or "")

    hooks_dir = Path(__file__).resolve().parent
    plugin_root = hooks_dir.parent.parent
    if not is_plugin_install(plugin_root):
        log("vendored-unsupported hook-folder=%s; nothing printed" % hooks_dir)
        return 0

    limit = load_max_characters()
    max_bytes = limit * BYTES_PER_LIMIT_CHARACTER

    shipped_dir = hooks_dir.parent / "agreements"
    proj = project_dir()
    project_agreements_dir = (proj / ".claude" / "agreements") if proj is not None else None

    shipped: list[Agreement] = []
    shipped_names: dict[str, str] = {}
    if shipped_dir.is_dir():
        try:
            shipped_names = {n.lower(): n for n in candidate_names(shipped_dir)}
            shipped = load_folder(shipped_dir, "shipped", {})
        except OSError as exc:
            log("agreement-skipped file=%s reason=unreadable detail=%s" % (shipped_dir, exc))
    else:
        log("shipped-folder-missing path=%s" % shipped_dir)

    project: list[Agreement] = []
    if project_agreements_dir is not None:
        try:
            real_folder = Path(os.path.realpath(project_agreements_dir))
            same_folder = os.path.normcase(str(real_folder)) == os.path.normcase(os.path.realpath(shipped_dir))
            if same_folder or not project_agreements_dir.is_dir():
                pass
            elif not is_within(real_folder, Path(os.path.realpath(proj))):
                log("agreement-skipped file=%s reason=outside-project detail=resolves to %s" % (
                    project_agreements_dir, real_folder))
            else:
                project = load_folder(project_agreements_dir, "project", shipped_names, max_bytes)
        except OSError as exc:
            log("agreement-skipped file=%s reason=unreadable detail=%s" % (project_agreements_dir, exc))

    # Delivery order: plain-language first, then the other shipped in name order, then project.
    shipped.sort(key=lambda a: (a.slug != ALWAYS_KEPT_SLUG, a.path.name))

    if not shipped and not project:
        return 0

    delivered, dropped, text = fit(shipped, project, limit)
    for agreement in dropped:
        log("agreement-dropped-for-size slug=%s path=%s characters=%d" % (
            agreement.slug, agreement.path, agreement.size - 2))
    if ulen(text) > limit:
        log("over-limit-kept characters=%d limit=%d" % (ulen(text), limit))

    emit(text)
    log("PRINTED session=%s source=%s slugs=%s characters=%d limit=%d" % (
        session_id, source, ",".join(a.slug for a in delivered), ulen(text), limit))
    return 0


def main() -> int:
    try:
        return run()
    except BaseException as exc:  # last resort: a session must always open
        try:
            log("unexpected-error error=%s" % exc)
        except BaseException:
            pass
        return 0
    finally:
        flush_log()


if __name__ == "__main__":
    code = main()
    try:
        sys.stdout.flush()
    except BaseException:
        pass
    sys.exit(code)
