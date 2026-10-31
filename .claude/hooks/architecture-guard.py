#!/usr/bin/env python3
"""
architecture-guard.py -- PreToolUse hook blocking raw CSS in Angular files.

Scans Edit / Write / MultiEdit payloads for CSS anti-patterns and rejects
writes that would introduce:

    * static inline `style="..."` attributes in templates
      (dynamic `[style.prop]="expr"` bindings are allowed)
    * raw Tailwind `text-gray-*` / `bg-gray-*` / `border-gray-*` classes
      (must use the @theme bridge: text-on-surface-variant, etc.)
    * hardcoded hex colors in templates
    * inline `template:` / `styles:` in @Component({}) decorators
    * raw property rules in component SCSS files (warn, not block)

Hook contract (Claude Code):
    stdin:  JSON with { tool_name, tool_input: { file_path, content, new_string, edits[] } }
    exit 0: allow (optional stdout = informational)
    exit 2: block (stderr shown to Claude)
    other:  error (hook fails open -- logs to stderr, allows the call)

Bypass:
    CLAUDE_ARCH_GUARD=off -- disable the hook for a session

Exception list and rules file:
    architecture-guard.exceptions.json and architecture-guard.rules.json (both)
    hook_file finds each: project copy, template beside the hook, working folder's .claude/hooks, then ~/.claude/hooks

Post-edit view (G-4):
    For an Edit or MultiEdit the guard builds the file as it will be after the
    edit (disk text as UTF-8, CRLF folded to LF, old_string found exactly once
    unless replace_all). Line rules judge each edit's new text. The whole-file
    rules (height chain, inline template, inline styles) run once per file per
    call: the height chain on the view; the two inline rules when any edit's new
    text holds the pattern, or when the view holds it and the disk text did not.
    When the view cannot be built, every rule judges the new text alone.
    Each new step falls back to the stricter outcome when it raises (V-2).

Known limits (accepted; each is pinned by a test):
    W5   `relative` and `absolute` are never checked.
    W6b  Line rules judge each edit's new text, so two edits that together form
         `text-gray-500` pass.
    W8   Stylesheet rules only warn; the nesting check works one line at a time.
    W11  An edit that completes a violation started on disk passes.
    G-2  `*.component.html`, `*.component.ts`, `*.component.scss` are always scanned; any other
         `.html`, `.scss`, `.css` or `.ts` file only when its `.ts` sibling (for a `.ts`, its own
         post-edit text) already carries `@Component(`. A `.spec.ts` or `.d.ts` is never scanned.
         With no post-edit view the written text is used instead.
    G-5  A 3- or 6-character token with no digit that stands alone after
         whitespace (such as `  #fff`) is read as a template reference variable.
         Quotes are counted per kind, so an apostrophe inside a double-quoted value
         (`aria-label="Don't save" #add`) makes the count odd and that reference
         variable is still read as a colour (accepted, not fixed).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import NamedTuple

# Passive error logging (fail-soft import).
sys.path.insert(0, str(Path(__file__).parent))
try:
    from _error_log import log_event
except Exception:
    def log_event(*args, **kwargs):  # type: ignore[no-redef]
        return

HOOK_DIR = Path(__file__).resolve().parent
try:  # project-local .claude first, global second
    import _project_paths as _pp
except Exception:  # pragma: no cover - hooks must never crash a tool call
    _pp = None

# Without _project_paths the fallback is the hook's own folder (G-3).
EXCEPTIONS_FILE = (
    _pp.hook_file("architecture-guard.exceptions.json") if _pp
    else HOOK_DIR / "architecture-guard.exceptions.json"
)
EXTERNAL_RULES_FILE = (
    _pp.hook_file("architecture-guard.rules.json") if _pp
    else HOOK_DIR / "architecture-guard.rules.json"
)

# External rules loaded once per process; populated by /promote-ui-rule skill.
_EXTERNAL_RULES: list[dict] | None = None

# Project-shaped settings, read from the same rules file.
#
# Two facts in this hook name a project rather than a pattern: where the
# front-end applications live, and which documents the block message points a
# reader at. Both now come from architecture-guard.rules.json so the hook body
# is generic. The defaults below are generic too, and they only ever affect
# WHICH PATHS ARE SCANNED and WHAT THE MESSAGE CITES -- never whether a
# violation blocks. No verdict depends on them.
_PROJECT_SETTINGS: dict | None = None

_DEFAULT_FRONTEND_PROJECTS_ROOT = "projects"
_DEFAULT_REFERENCE_DOCUMENTS: list[str] = []


def load_project_settings() -> dict:
    global _PROJECT_SETTINGS
    if _PROJECT_SETTINGS is not None:
        return _PROJECT_SETTINGS
    data: dict = {}
    if EXTERNAL_RULES_FILE.exists():
        try:
            loaded = json.loads(EXTERNAL_RULES_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, json.JSONDecodeError) as e:
            log(f"failed to read project settings: {e}")
    root = data.get("frontend_projects_root")
    docs = data.get("reference_documents")
    # G-1: padding, backslashes, doubled and surrounding slashes do not change the root.
    root_segments = [
        s.strip() for s in (root.replace("\\", "/").lower().split("/") if isinstance(root, str) else [])
        if s.strip()
    ]
    _PROJECT_SETTINGS = {
        "frontend_projects_root": "/".join(root_segments) or _DEFAULT_FRONTEND_PROJECTS_ROOT,
        "reference_documents": (
            [str(d) for d in docs] if isinstance(docs, list) else list(_DEFAULT_REFERENCE_DOCUMENTS)
        ),
    }
    return _PROJECT_SETTINGS


def load_external_rules() -> list[dict]:
    global _EXTERNAL_RULES
    if _EXTERNAL_RULES is not None:
        return _EXTERNAL_RULES
    if not EXTERNAL_RULES_FILE.exists():
        _EXTERNAL_RULES = []
        return _EXTERNAL_RULES
    try:
        data = json.loads(EXTERNAL_RULES_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log(f"failed to read external rules: {e}")
        _EXTERNAL_RULES = []
        return _EXTERNAL_RULES
    rules = data.get("rules", []) if isinstance(data, dict) else []
    if not isinstance(rules, list):
        rules = []
    # Defensive validation: keep only well-formed entries.
    valid: list[dict] = []
    for r in rules:
        if not isinstance(r, dict):
            continue
        rid = r.get("id")
        regex = r.get("regex")
        applies_to = r.get("applies_to", "any")
        if not isinstance(rid, str) or not isinstance(regex, str):
            continue
        if applies_to not in ("html", "ts", "scss", "any"):
            continue
        try:
            re.compile(regex)
        except re.error:
            log(f"external rule '{rid}' has invalid regex; skipping")
            continue
        valid.append(r)
    _EXTERNAL_RULES = valid
    return _EXTERNAL_RULES


def scan_external_rules(
    content: str,
    file_path: Path,
    file_kind: str,  # 'html' | 'ts' | 'scss'
    exemptions: dict,
) -> list["Violation"]:
    """
    Apply external rules from architecture-guard.rules.json against content.
    Each rule fires when:
        - applies_to == file_kind or applies_to == 'any'
        - scope matches the file's app (or scope == 'all')
        - file_path is not in the rule's exception_seeds list
        - file is not exempted from the rule via architecture-guard.exceptions.json
    """
    rules = load_external_rules()
    if not rules:
        return []

    app = detect_app(file_path)
    norm_path = str(file_path).replace("\\", "/").lower()
    out: list[Violation] = []

    for rule in rules:
        applies_to = rule.get("applies_to", "any")
        if applies_to != "any" and applies_to != file_kind:
            continue
        scope = rule.get("scope", "all")
        if scope != "all" and scope != app:
            continue
        if file_rule_exempted(file_path, f"external:{rule['id']}", exemptions):
            continue
        # Per-rule exception seeds.
        seeds = rule.get("exception_seeds", []) or []
        if any(isinstance(s, str) and s.replace("\\", "/").lower() in norm_path for s in seeds):
            continue
        try:
            rx = re.compile(rule["regex"])
        except re.error:
            continue
        for i, line in enumerate(content.splitlines(), start=1):
            if not line.strip():
                continue
            if rx.search(line):
                out.append(Violation(
                    rule=f"external:{rule['id']}",
                    line_no=i,
                    line_text=line.strip(),
                    suggestion=rule.get("suggestion", f"External rule {rule['id']} fired.").strip(),
                ))

    return out

# Per-app rules: cached after first load. Key = app name (lowercase).
_APP_RULES_CACHE: dict[str, dict] = {}
_APP_RULES_LOADED: set[str] = set()


def detect_app(file_path: Path) -> str | None:
    """
    Detect the front-end application from a file path, or None when the path
    does not live under any application.

    The root that holds the applications is a project fact, so it is read from
    architecture-guard.rules.json (`frontend_projects_root`) rather than
    hard-coded here. A consuming project sets it to its own workspace root.
    """
    norm = str(file_path).replace("\\", "/").lower()
    root = load_project_settings()["frontend_projects_root"]
    m = re.search(re.escape(root) + r"/([a-z0-9-]+)/", norm)
    if m:
        return m.group(1)
    return None


def app_root_segments() -> list[str]:
    """G-1: the configured root of the front-end applications, one lower-case entry per path segment."""
    return load_project_settings()["frontend_projects_root"].split("/")


def load_app_rules(file_path: Path) -> dict | None:
    """
    Load the .app-rules.json that sits at the Angular project root above the
    given file. Cached per-app to avoid re-reading on every scan. Returns
    None if the file isn't reachable or doesn't exist.
    """
    app = detect_app(file_path)
    if not app:
        return None
    if app in _APP_RULES_LOADED:
        return _APP_RULES_CACHE.get(app)
    _APP_RULES_LOADED.add(app)

    # V-2: a raise in the root lookup or in the walk retries with the default root; a second raise means no rules.
    default_root = [_DEFAULT_FRONTEND_PROJECTS_ROOT]
    try:
        root_parts = app_root_segments()
    except Exception as e:  # noqa: BLE001
        log(f"app root lookup failed (using '{_DEFAULT_FRONTEND_PROJECTS_ROOT}'): {e}")
        root_parts = default_root
    try:
        return read_app_rules_file(file_path, app, root_parts)
    except Exception as e:  # noqa: BLE001
        log(f"app rules walk failed (retrying with '{_DEFAULT_FRONTEND_PROJECTS_ROOT}'): {e}")
    try:
        return read_app_rules_file(file_path, app, default_root)
    except Exception as e:  # noqa: BLE001
        log(f"app rules walk failed again (no app rules): {e}")
        return None


def read_app_rules_file(file_path: Path, app: str, root_parts: list[str]) -> dict | None:
    """Walk up to <frontend_projects_root>/<app>/.app-rules.json and read it; None when absent or unreadable."""
    depth = len(root_parts)
    parts = list(file_path.resolve().parts) if file_path.is_absolute() else list(Path.cwd().joinpath(file_path).resolve().parts)
    for i in range(len(parts) - 1, depth, -1):
        if parts[i].lower() == app and [p.lower() for p in parts[i - depth:i]] == root_parts:
            project_root = Path(*parts[: i + 1])
            rules_file = project_root / ".app-rules.json"
            if rules_file.exists():
                try:
                    data = json.loads(rules_file.read_text(encoding="utf-8"))
                    _APP_RULES_CACHE[app] = data  # shared with load_app_rules' per-app cache
                    return data
                except (OSError, json.JSONDecodeError) as e:
                    log(f"failed to read {rules_file}: {e}")
                    return None
            break
    return None


def scan_extra_banned_classes(
    line: str,
    file_path: Path,
    app_rules: dict | None,
    exemptions: dict,
    line_no: int,
) -> list["Violation"]:
    """
    Apply the per-app `extraBannedClasses` list against a single line.
    Each ban is treated as a substring match; suggestion is pulled from
    `extraTokenReplacements` when present, otherwise generic.
    """
    if not app_rules or file_rule_exempted(file_path, "app-banned-class", exemptions):
        return []
    banned = app_rules.get("extraBannedClasses", []) or []
    replacements = app_rules.get("extraTokenReplacements", {}) or {}
    out: list[Violation] = []
    for cls in banned:
        if not isinstance(cls, str) or not cls.strip():
            continue
        if re.search(rf"\b{re.escape(cls)}\b", line):
            replacement = replacements.get(cls)
            if replacement:
                suggestion = (
                    f"`{cls}` is banned in this app (theme mismatch). "
                    f"Use `{replacement}` from the @theme bridge instead."
                )
            else:
                suggestion = (
                    f"`{cls}` is banned in this app per .app-rules.json. "
                    f"Pick a Material token utility consistent with the app's theme."
                )
            out.append(Violation(
                rule=f"app-banned-class:{cls}",
                line_no=line_no,
                line_text=line.strip(),
                suggestion=suggestion,
            ))
    return out


class Violation(NamedTuple):
    rule: str
    line_no: int
    line_text: str
    suggestion: str
    rule_id: str = ""
    document: str | None = None


class PostEditView(NamedTuple):
    """The file as it will be after the edit. ``reason`` is set exactly when ``text`` is None."""
    path: str
    text: str | None
    disk: str | None  # the disk text before the edit; None for a Write or when unavailable
    source: str  # 'write-content' | 'disk-plus-edits'
    reason: str = ""


# Guard rule map (contract 2026-10-28-angular-tailwind-rule-documents, t6).
# Keys are matched exactly first, then by prefix. Each value is (Rule ID, document).
# `external:` rules carry their own id and no document (handled in resolve_rule_id).
RULE_MAP_EXACT: dict[str, tuple[str, str]] = {
    "inline-style": ("T-001", "TAILWINDCSS_RULES.md"),
    "hex-color": ("T-004", "TAILWINDCSS_RULES.md"),
    "scroll-edge": ("T-012", "TAILWINDCSS_RULES.md"),
    "inline-component-template": ("A-003", "ANGULAR_CODE_RULES.md"),
    "inline-component-styles": ("A-003", "ANGULAR_CODE_RULES.md"),
    "scss-warn:raw-property": ("T-010", "TAILWINDCSS_RULES.md"),
    "scss-warn:dead-host": ("T-011", "TAILWINDCSS_RULES.md"),
}
RULE_MAP_PREFIX: dict[str, tuple[str, str]] = {
    "gray-utility:": ("T-003", "TAILWINDCSS_RULES.md"),
    "app-banned-class:": ("T-022", "TAILWINDCSS_RULES.md"),
    "height-chain-warn:": ("T-014", "TAILWINDCSS_RULES.md"),
}
ADDON_DOCS_RELATIVE = (".claude", "references", "angular-tailwind")
DOCS_NOT_INSTALLED_LINE = (
    "Rule text not installed in this project: the angular-tailwind add-on installs it "
    "(/auto-improve-angular-tailwind-install)."
)


def resolve_rule_id(rule: str) -> tuple[str, str | None]:
    """Return (rule_id, document) for a guard rule name; ("", None) when unmapped."""
    if rule.startswith("external:"):
        return (rule[len("external:"):], None)
    if rule in RULE_MAP_EXACT:
        return RULE_MAP_EXACT[rule]
    for prefix, entry in RULE_MAP_PREFIX.items():
        if rule.startswith(prefix):
            return entry
    return ("", None)


def installed_document_path(document: str) -> Path | None:
    """The project's copy of an add-on document, or None when absent or the root is unknown."""
    try:
        root = _pp.project_dir() if _pp else None
    except Exception:  # noqa: BLE001
        root = None
    if root is None:
        return None
    candidate = root.joinpath(*ADDON_DOCS_RELATIVE, document)
    return candidate if candidate.is_file() else None


def format_rule_label(v: Violation) -> str:
    rule_id, _ = resolve_rule_id(v.rule)
    return f"[{v.rule}] {rule_id}" if rule_id else f"[{v.rule}]"


def document_footer(violations: list[Violation]) -> list[str]:
    """One 'Rule text:' line per installed document; one 'not installed' line if any is absent."""
    docs: list[str] = []
    for v in violations:
        _, doc = resolve_rule_id(v.rule)
        if doc and doc not in docs:
            docs.append(doc)
    out: list[str] = []
    missing = False
    for doc in docs:
        found = installed_document_path(doc)
        if found is None:
            missing = True
        else:
            out.append(f"Rule text: {found}")
    if missing:
        out.append(DOCS_NOT_INSTALLED_LINE)
    return out


def log(msg: str) -> None:
    print(f"[architecture-guard] {msg}", file=sys.stderr)


def bypass_env() -> bool:
    return os.environ.get("CLAUDE_ARCH_GUARD", "").lower() in {"off", "0", "false", "no"}


def load_exceptions() -> dict:
    if not EXCEPTIONS_FILE.exists():
        return {"ignored_files": [], "file_rule_exemptions": {}}
    try:
        return json.loads(EXCEPTIONS_FILE.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log(f"failed to read exceptions file: {e}")
        return {"ignored_files": [], "file_rule_exemptions": {}}


def path_in_ignored(path: Path, ignored_files: list[str]) -> bool:
    norm = str(path).replace("\\", "/").lower()
    for entry in ignored_files:
        e = entry.replace("\\", "/").lower().strip()
        if not e:
            continue
        if e in norm or norm.endswith(e):
            return True
    return False


def file_rule_exempted(path: Path, rule: str, exemptions: dict) -> bool:
    norm = str(path).replace("\\", "/").lower()
    for entry, rules in exemptions.items():
        e = entry.replace("\\", "/").lower().strip()
        if e in norm or norm.endswith(e):
            if rule in rules or "*" in rules:
                return True
    return False


# ---------------------------------------------------------------------------
# Regex rules
# ---------------------------------------------------------------------------

# Static inline style="..." in templates.
# Exclude: [style]="..."  (negative lookbehind on `[`)
# Exclude: [attr.style]="..."  (preceded by `.`)
RX_INLINE_STYLE = re.compile(r"(?<![\[\.\w])style\s*=\s*\"[^\"]*\"")

# C1(b): a static style on these elements is allowed when every property positions.
SVG_STYLE_ELEMENTS = frozenset({
    "svg", "g", "text", "tspan", "rect", "circle", "ellipse", "line", "polyline",
    "polygon", "path", "use", "image", "foreignobject", "canvas",
})
POSITIONING_PROPERTIES = frozenset({
    "position", "left", "top", "right", "bottom", "transform", "transform-origin", "translate",
})
RX_OPEN_TAG_BEFORE = re.compile(r"<([A-Za-z][\w:-]*)[^<>]*$")
RX_STYLE_VALUE = re.compile(r"\"([^\"]*)\"")


def style_is_positioning_exception(line: str, match: re.Match) -> bool:
    """True when the static style at ``match`` is C1(b): SVG/canvas tag on the same line, positioning only."""
    tag = RX_OPEN_TAG_BEFORE.search(line[: match.start()])
    if tag is None or tag.group(1).lower() not in SVG_STYLE_ELEMENTS:
        return False
    value = RX_STYLE_VALUE.search(match.group(0))
    names = []
    for decl in (value.group(1) if value else "").split(";"):
        if not decl.strip():
            continue
        if ":" not in decl:
            return False
        names.append(decl.split(":", 1)[0].strip().lower())
    return bool(names) and all(n in POSITIONING_PROPERTIES for n in names)


# Tailwind gray utilities that should be Material tokens.
RX_TEXT_GRAY = re.compile(r"\btext-gray-\d+\b")
RX_BG_GRAY = re.compile(r"\bbg-gray-\d+\b")
RX_BORDER_GRAY = re.compile(r"\bborder-gray-\d+\b")

# Hardcoded hex colors anywhere in a template line.
# Match 3 or 6 digit hex preceded by `#` and not part of an id selector.
RX_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b(?![0-9a-fA-F])")

# Inline template: or styles: in @Component({}) decorators.
RX_INLINE_TEMPLATE = re.compile(r"@Component\s*\(\s*\{[^}]*\btemplate\s*:", re.DOTALL)
RX_INLINE_STYLES = re.compile(r"@Component\s*\(\s*\{[^}]*\bstyles\s*:", re.DOTALL)

# Raw overflow-y-auto / sticky top-0 / position: relative patterns in templates.
RX_INLINE_OVERFLOW = re.compile(r"\boverflow-y-auto\b")
RX_INLINE_STICKY = re.compile(r"\bsticky\s+top-0\b")
RX_CLASS_ATTR = re.compile(r"""(?<![\w.\-])class\s*=\s*(?:"([^"]*)"|'([^']*)')""")
RX_STICKY_TOKEN = re.compile(r"(?:^|\s)(?:[\w-]+:)*sticky(?=\s|$)")


def class_attribute_has_sticky(line: str) -> bool:
    """True when a class="..." attribute holds a `sticky` token (variants allowed); prose does not count."""
    for m in RX_CLASS_ATTR.finditer(line):
        if RX_STICKY_TOKEN.search(m.group(1) if m.group(1) is not None else m.group(2)):
            return True
    return False

# Height-chain invariant for scroll-edge templates.
# scroll-edge + flex-1 min-h-0 inside a file whose first <div class="..."> lacks
# any of {h-full, flex-1, max-h-, min-h-screen} silently collapses to 0 px and
# renders empty content (recurring regression — observations 865 and 1292 in this project).
RX_HEIGHT_CHAIN_ANCHOR = re.compile(r"\bscroll-edge\b.*\bflex-1\b.*\bmin-h-0\b|\bflex-1\b.*\bmin-h-0\b.*\bscroll-edge\b")
RX_FIRST_DIV_CLASS = re.compile(r'<div\s+class="([^"]+)"')
RX_ROOT_HAS_HEIGHT = re.compile(r"\b(?:h-full|flex-1|max-h-|min-h-screen)\b")

# SCSS allow-contexts (wrap the raw property check):
# Raw properties are OK inside @keyframes, @media, @supports and @apply blocks,
# and inside ::ng-deep blocks EXCEPT in a ViewEncapsulation.None component
# (where ::ng-deep is not an allowing context; scoped selectors are instead).
# We approximate with a line-level scan that tracks nesting depth of allowed blocks.
RX_NG_DEEP = re.compile(r":host\s*::ng-deep|::ng-deep")
RX_KEYFRAMES = re.compile(r"@keyframes\b|@-webkit-keyframes\b")
RX_MEDIA = re.compile(r"@media\b|@supports\b")
RX_APPLY = re.compile(r"@apply\b")

# Raw CSS property rule: "name: value;" (not inside a selector or @rule).
RX_CSS_PROP = re.compile(r"^\s*[a-zA-Z-]+\s*:\s*[^;{}\n]+;\s*(?://.*)?$")


# ---------------------------------------------------------------------------
# Scanners
# ---------------------------------------------------------------------------

def scan_height_chain_invariant(content: str, path: Path, exemptions: dict) -> list[Violation]:
    """
    File-level WARN check for the scroll-edge height chain.

    Fires when ALL of the following hold:
      - file contains the substring `scroll-edge`
      - file contains `flex-1 min-h-0` (the parent-dependent height pattern)
      - the file's first `<div class="...">` does NOT carry any of:
        h-full, flex-1, max-h-, min-h-screen

    Why: `scroll-edge flex-1 min-h-0` depends on the parent providing a height
    via the flex chain. If the page's root wrapper does not claim height with
    h-full (or participate in a parent flex via flex-1), the table collapses
    to 0 px and the page renders empty. This has now regressed twice on the
    eval-runs pages (obs 865 May 19; obs 1292 May 20).

    Returns WARN-level violations (rule prefix `height-chain-warn:`). The main
    loop emits these via `emit_warnings` and does NOT exit 2 — the rule is in
    its trial window. After two regression-free weeks, promote to BLOCK by
    moving the call into the blocking path of `scan_template_html`.
    """
    if file_rule_exempted(path, "height-chain", exemptions):
        return []

    if "scroll-edge" not in content:
        return []
    if not RX_HEIGHT_CHAIN_ANCHOR.search(content):
        return []

    first_div = RX_FIRST_DIV_CLASS.search(content)
    if first_div is None:
        # No top-level <div class="..."> at all — the chain is hosted via @Component
        # host metadata (e.g. EvalRunsTableComponent itself). Skip — those files are
        # correct by construction and the WARN would be a false positive.
        return []

    root_classes = first_div.group(1)
    if RX_ROOT_HAS_HEIGHT.search(root_classes):
        return []

    line_no = content[: first_div.start()].count("\n") + 1
    return [Violation(
        rule="height-chain-warn:scroll-edge-no-root-height",
        line_no=line_no,
        line_text=first_div.group(0)[:120],
        suggestion=(
            "scroll-edge + flex-1 min-h-0 needs a parent height. Add `h-full min-h-0` "
            "to the root <div> of this template (or `flex-1 min-h-0` if it itself sits "
            "inside a flex parent). Without it, the table collapses to 0 px and the "
            "page renders empty even when data is loaded."
        ),
    )]


def is_template_reference_variable(line: str, match: re.Match) -> bool:
    """
    G-5: True when the `#` token at ``match`` is a template reference variable, not a colour.

    All four hold: whitespace or the line start comes before it; the quotes
    between the last `<` and the token are balanced (even `"` and even `'`);
    whitespace, `>`, `/`, `=` or the line end comes after it; the hex run has no digit.
    """
    start, end = match.start(), match.end()
    if start > 0 and not line[start - 1].isspace():
        return False
    segment = line[line.rfind("<", 0, start) + 1: start]
    if segment.count('"') % 2 or segment.count("'") % 2:
        return False
    if end < len(line) and not (line[end].isspace() or line[end] in ">/="):
        return False
    return not any(ch.isdigit() for ch in match.group(0))


def line_has_hex_color(line: str) -> bool:
    """True when the line holds a hex colour; a template reference variable does not count."""
    for m in RX_HEX_COLOR.finditer(line):
        try:
            if is_template_reference_variable(line, m):
                continue
        except Exception as e:  # noqa: BLE001 -- V-2: when the test fails, the token is a colour
            log(f"reference-variable test failed (treating as colour): {e}")
        return True
    return False


# (rule, decorator pattern, line pattern, suggestion) for the whole-file inline rules.
INLINE_COMPONENT_RULES = (
    ("inline-component-template", RX_INLINE_TEMPLATE, r"\btemplate\s*:",
     "Use templateUrl: './xxx.component.html' -- never inline template:."),
    ("inline-component-styles", RX_INLINE_STYLES, r"\bstyles\s*:",
     "Use styleUrl: './xxx.component.scss' -- never inline styles:."),
)


def inline_pattern_is_introduced(rx: re.Pattern, disk_text: str) -> bool:
    """True when the disk text did not already hold the inline pattern."""
    return not rx.search(disk_text)


def scan_inline_component_rules(
    content: str, path: Path, exemptions: dict, disk_text: str | None = None,
) -> list[Violation]:
    """
    Inline `template:` / `styles:` in @Component({}). With ``disk_text`` the pattern
    must be introduced by the edit (G-4); a failed comparison counts as introduced (V-2).
    """
    out: list[Violation] = []
    for rule, rx, line_pattern, suggestion in INLINE_COMPONENT_RULES:
        if file_rule_exempted(path, rule, exemptions) or not rx.search(content):
            continue
        if disk_text is not None:
            try:
                if not inline_pattern_is_introduced(rx, disk_text):
                    continue
            except Exception as e:  # noqa: BLE001
                log(f"view-against-disk comparison failed (counting as introduced): {e}")
        for i, line in enumerate(content.splitlines(), start=1):
            if re.search(line_pattern, line):
                out.append(Violation(rule=rule, line_no=i, line_text=line.strip(), suggestion=suggestion))
                break
    return out


def build_post_edit_view(payload: dict, file_path_str: str) -> PostEditView:
    """
    G-4: the file as it will be after this call's edits. A Write is its own content.
    Otherwise the disk text (strict UTF-8, CRLF folded to LF) with each edit applied in
    order; ``old_string`` must occur once unless ``replace_all``. The reason names why
    the view is unavailable: file-unreadable, not-utf8, old-string-missing, old-string-ambiguous.
    """
    tool_input = payload.get("tool_input") or {}
    if isinstance(tool_input.get("content"), str):
        return PostEditView(file_path_str, tool_input["content"], None, "write-content")

    def unavailable(reason: str) -> PostEditView:
        return PostEditView(file_path_str, None, None, "disk-plus-edits", reason)

    edits: list[dict] = []
    if isinstance(tool_input.get("new_string"), str):
        edits.append(tool_input)
    for edit in tool_input.get("edits") or []:
        if isinstance(edit, dict) and (edit.get("file_path") or file_path_str) == file_path_str:
            edits.append(edit)

    try:
        disk = Path(file_path_str).read_bytes().decode("utf-8").replace("\r\n", "\n")
    except UnicodeDecodeError:
        return unavailable("not-utf8")
    except OSError:
        return unavailable("file-unreadable")

    text = disk
    for edit in edits:
        old = str(edit.get("old_string", "")).replace("\r\n", "\n")
        new = str(edit.get("new_string", "")).replace("\r\n", "\n")
        found = text.count(old) if old else 0  # an empty old_string would match everywhere
        if found == 0:
            return unavailable("old-string-missing")
        if found > 1 and not edit.get("replace_all"):
            return unavailable("old-string-ambiguous")
        text = text.replace(old, new) if edit.get("replace_all") else text.replace(old, new, 1)
    return PostEditView(file_path_str, text, disk, "disk-plus-edits")


def scan_whole_file_rules(
    path: Path, fragments: list[str], view: PostEditView, exemptions: dict,
) -> tuple[list[Violation], list[Violation]]:
    """
    G-4: the whole-file rules, once per file per call. Returns (blocking, warnings).

    The height chain judges the view, or each fragment when there is no view. The two
    inline rules block on a view that holds the pattern when the disk text did not; the
    fragments were already judged by scan_component_ts. A Write has no disk text.
    """
    blocking: list[Violation] = []
    warnings: list[Violation] = []
    if is_template_html(path):
        for text in ([view.text] if view.text is not None else fragments):
            warnings.extend(scan_height_chain_invariant(text, path, exemptions))
    elif view.text is not None and view.disk is not None and is_component_ts(path, lambda: view.text):
        blocking.extend(scan_inline_component_rules(view.text, path, exemptions, view.disk))
    return blocking, warnings


def dedupe_violations(violations: list[Violation]) -> list[Violation]:
    """Drop a finding repeated with the same rule, line and text; first occurrence wins."""
    seen: set[tuple[str, int, str]] = set()
    unique: list[Violation] = []
    for v in violations:
        key = (v.rule, v.line_no, v.line_text)
        if key not in seen:
            seen.add(key)
            unique.append(v)
    return unique


def scan_template_html(content: str, path: Path, exemptions: dict) -> list[Violation]:
    violations: list[Violation] = []
    app_rules = load_app_rules(path)
    violations.extend(scan_external_rules(content, path, "html", exemptions))
    for i, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue

        # Rule: per-app banned classes from .app-rules.json
        violations.extend(scan_extra_banned_classes(line, path, app_rules, exemptions, i))

        # Rule: static inline style=
        if not file_rule_exempted(path, "inline-style", exemptions):
            for m in RX_INLINE_STYLE.finditer(line):
                if style_is_positioning_exception(line, m):
                    continue
                violations.append(Violation(
                    rule="inline-style",
                    line_no=i,
                    line_text=line.strip(),
                    suggestion=(
                        "Replace static style=\"...\" with Tailwind utilities from "
                        "the design-pattern document under Reference below "
                        "(e.g. text-primary, bg-surface-container, "
                        "border-outline-variant, w-48, p-4, gap-2). "
                        "Dynamic [style.prop]=\"expr\" bindings are allowed, and so is a "
                        "positioning-only style on an SVG element or canvas."
                    ),
                ))

        # Rule: text-gray / bg-gray / border-gray
        if not file_rule_exempted(path, "gray-utility", exemptions):
            for rx, label, replacement in (
                (RX_TEXT_GRAY, "text-gray", "text-on-surface-variant"),
                (RX_BG_GRAY, "bg-gray", "bg-surface-variant or bg-surface-container"),
                (RX_BORDER_GRAY, "border-gray", "border-outline-variant"),
            ):
                if rx.search(line):
                    violations.append(Violation(
                        rule=f"gray-utility:{label}",
                        line_no=i,
                        line_text=line.strip(),
                        suggestion=f"Replace {label}-* with {replacement} from the @theme bridge.",
                    ))

        # Rule: hex colors in templates (except SVG chart exception list).
        if not file_rule_exempted(path, "hex-color", exemptions):
            if line_has_hex_color(line):
                violations.append(Violation(
                    rule="hex-color",
                    line_no=i,
                    line_text=line.strip(),
                    suggestion=(
                        "Hardcoded hex colors are banned. Use Material token utilities "
                        "(text-primary, bg-surface-container-high, etc.) or, for SVG charts, "
                        "bind to a computed signal that reads var(--mat-sys-*) via getComputedStyle."
                    ),
                ))

        # Rule: inline overflow / sticky.
        if not file_rule_exempted(path, "scroll-edge", exemptions):
            if (RX_INLINE_OVERFLOW.search(line) or RX_INLINE_STICKY.search(line)
                    or class_attribute_has_sticky(line)):
                violations.append(Violation(
                    rule="scroll-edge",
                    line_no=i,
                    line_text=line.strip(),
                    suggestion=(
                        "Use the global scroll-edge / scroll-edge-content / scroll-edge-header "
                        "classes instead of inline overflow-y-auto or sticky positioning. "
                        "Set height via h-* utility on the scroll-edge element."
                    ),
                ))

    return violations


def scan_component_ts(content: str, path: Path, exemptions: dict) -> list[Violation]:
    violations: list[Violation] = []
    app_rules = load_app_rules(path)
    violations.extend(scan_external_rules(content, path, "ts", exemptions))

    # Rule: per-app banned classes from .app-rules.json (catches TS-side class strings).
    if app_rules:
        for i, line in enumerate(content.splitlines(), start=1):
            if not line.strip():
                continue
            violations.extend(scan_extra_banned_classes(line, path, app_rules, exemptions, i))

    # Rules: inline @Component({ template: ... }) and ({ styles: ... }).
    violations.extend(scan_inline_component_rules(content, path, exemptions))

    # Rule: gray-utility class strings inside TS string literals.
    # Catches STATE_BADGE-style maps and getStatusClass()-style helpers that
    # return Tailwind class strings — these slip past the .html-only scan
    # because the strings are interpolated into [class] / [ngClass] bindings.
    # The \b...-\d+\b pattern is safe here: TS identifiers can't contain
    # hyphens, so matches only fire inside string literals (or comments,
    # which are equally valid to flag).
    if not file_rule_exempted(path, "gray-utility", exemptions):
        for i, line in enumerate(content.splitlines(), start=1):
            if not line.strip():
                continue
            for rx, label, replacement in (
                (RX_TEXT_GRAY, "text-gray", "text-on-surface-variant"),
                (RX_BG_GRAY, "bg-gray", "bg-surface-variant or bg-surface-container"),
                (RX_BORDER_GRAY, "border-gray", "border-outline-variant"),
            ):
                if rx.search(line):
                    violations.append(Violation(
                        rule=f"gray-utility:{label}",
                        line_no=i,
                        line_text=line.strip(),
                        suggestion=(
                            f"Replace {label}-* with {replacement} from the @theme bridge. "
                            "TS-side class strings (STATE_BADGE maps, getStatusClass helpers) "
                            "must use the same Material tokens as templates."
                        ),
                    ))

    return violations


RX_ELEMENT_NAME = re.compile(r"^[a-zA-Z][\w-]*$")
RX_ENCAPSULATION_KEY = re.compile(r"\bencapsulation\s*:\s*([\w.]+)")
RX_COMPONENT_SELECTOR = re.compile(r"\bselector\s*:\s*(['\"])([^'\"]*)\1")
RX_DEAD_HOST = re.compile(r":host\b")

DEAD_HOST_SUGGESTION = (
    "`:host` matches nothing in a ViewEncapsulation.None component, so the "
    "browser discards this rule. Scope it under the component's element "
    "selector instead, for example `my-widget .vendor-class`."
)
RAW_PROPERTY_SUGGESTION = (
    "This property has a 1:1 Tailwind utility. Move it to the template as a "
    "class. In a ViewEncapsulation.None component, a rule scoped under the "
    "component's element selector may keep it here."
)


def strip_ts_comments(source: str) -> str:
    """Remove `//` comments (to the line end) and turn each `/* */` into one space; strings stay intact."""
    out: list[str] = []
    i, n = 0, len(source)
    quote = ""
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if quote:
            out.append(ch)
            if ch == "\\" and nxt:
                out.append(nxt)
                i += 2
                continue
            if ch == quote or (ch == "\n" and quote != "`"):
                # A '/" string also ends at a line break, so a regex literal
                # like /'/ cannot swallow the rest of the file.
                quote = ""
        elif ch in "'\"`":
            quote = ch
            out.append(ch)
        elif ch == "/" and nxt == "/":
            while i < n and source[i] != "\n":
                i += 1
            continue
        elif ch == "/" and nxt == "*":
            end = source.find("*/", i + 2)
            i = n if end == -1 else end + 2
            out.append(" ")
            continue
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def classify_sibling_component(scss_path: Path) -> tuple[str, str]:
    """
    Return (mode, element_scope) for the component that owns ``scss_path``.

    Reads ``<stem>.component.ts``, else ``<stem>.ts``, next to the stylesheet (the stem
    is the name without its ``.component``, ``.scss`` or ``.css``) as strict UTF-8. Mode is
    'none' only for a recognised ViewEncapsulation.None spelling (any identifier
    ending in .None, or the number 2); every other outcome -- missing or
    undecodable file, other encapsulation, no recognised value -- is
    'unclassified' or 'default', which keep today's warnings. Never raises.
    """
    try:
        stem = scss_path.name[: -len(scss_path.suffix)].removesuffix(".component")
        ts_path = scss_path.with_name(stem + ".component.ts")
        if not ts_path.is_file():
            ts_path = scss_path.with_name(stem + ".ts")
        source = strip_ts_comments(ts_path.read_text(encoding="utf-8"))
        key = RX_ENCAPSULATION_KEY.search(source)
        if key is None:
            return ("unclassified" if "ViewEncapsulation" in source else "default", "")
        value = key.group(1)
        if value == "2" or value.endswith(".None"):
            start = source.find("@Component(")
            sel = RX_COMPONENT_SELECTOR.search(source, start) if start >= 0 else None
            scope = sel.group(2).strip() if sel else ""
            return ("none", scope if RX_ELEMENT_NAME.match(scope) else "")
        return ("unclassified", "")
    except Exception:  # noqa: BLE001 -- any failure means today's behaviour
        return ("unclassified", "")


def _split_depth0_commas(selector: str) -> list[str]:
    """Split a selector list at commas that sit outside parentheses/brackets."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in selector:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def _member_is_scoped(member: str, scope: str) -> bool:
    """True when ``member`` begins with ``scope`` followed by a permitted continuation."""
    member = member.strip()
    if not scope or not member.startswith(scope):
        return False
    rest = member[len(scope):]
    if not rest:
        return True
    if rest[0] in ".[:#>":
        return True
    if rest[0].isspace():
        rest = rest.lstrip()
        return not rest or rest[0] not in "~+"
    return False


def selector_is_scoped(selector: str, scope: str) -> bool:
    """True when EVERY depth-0 comma member of ``selector`` is scoped under ``scope``."""
    return all(_member_is_scoped(m, scope) for m in _split_depth0_commas(selector))


def _strip_selector_comment(line: str) -> str:
    """Drop a `//` comment (rest of line) or an unclosed `/*`; a closed `/* */` becomes one space (quote aware)."""
    quote = ""
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif ch == "/" and i + 1 < n and line[i + 1] == "/":
            return line[:i].rstrip()
        elif ch == "/" and i + 1 < n and line[i + 1] == "*":
            end = line.find("*/", i + 2)
            if end == -1:
                return line[:i].rstrip()
            # A closed block comment becomes one space; scanning goes on.
            line = line[:i] + " " + line[end + 2:]
            n = len(line)
            continue
        i += 1
    return line.rstrip()  # a comment that ended the line leaves a space behind


def scan_component_scss(content: str, path: Path, exemptions: dict) -> list[Violation]:
    """
    SCSS scanner -- warns on raw property rules outside allowed contexts.
    Allowed contexts: ::ng-deep (encapsulated or unclassified components only),
    @keyframes, @media, @supports, @apply, and -- in a ViewEncapsulation.None
    component -- a block whose every selector is scoped under the component's
    element selector. In such a component `:host` matches nothing, so a `:host`
    line is reported as 'scss-warn:dead-host' and opens no context.

    Non-blocking by design: returns violations with rule prefix 'scss-warn:'
    which the caller treats as WARN not BLOCK. This lets cleanup work proceed
    gradually without tripping on partially-migrated files.
    """
    if file_rule_exempted(path, "scss-raw-property", exemptions):
        return []

    mode, scope = classify_sibling_component(path)
    unencapsulated = mode == "none"

    violations: list[Violation] = []
    violations.extend(scan_external_rules(content, path, "scss", exemptions))
    depth = 0
    allowed_depth = 0  # depth inside an allowed block
    pending_selector = ""  # preceding selector lines that end in a comma

    lines = content.splitlines()
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Track entering allowed contexts.
        enters_allowed = bool(
            (RX_NG_DEEP.search(stripped) and not unencapsulated)
            or RX_KEYFRAMES.search(stripped)
            or RX_MEDIA.search(stripped)
        )
        if unencapsulated:
            if RX_DEAD_HOST.search(stripped):
                violations.append(Violation(
                    rule="scss-warn:dead-host",
                    line_no=i,
                    line_text=stripped,
                    suggestion=DEAD_HOST_SUGGESTION,
                ))
            sel_line = _strip_selector_comment(stripped)
            if "{" in sel_line:
                selector = (pending_selector + " " + sel_line.split("{", 1)[0]).strip()
                pending_selector = ""
                if scope and not sel_line.startswith("@") and selector_is_scoped(selector, scope):
                    enters_allowed = True
            elif sel_line.endswith(","):
                pending_selector += " " + sel_line
            else:
                pending_selector = ""

        # Count braces on this line.
        open_braces = stripped.count("{")
        close_braces = stripped.count("}")

        # If we're outside any allowed block, check for raw properties.
        if allowed_depth == 0:
            if RX_CSS_PROP.match(stripped) and not RX_APPLY.search(stripped):
                # Ignore SCSS variable declarations ($var: value;).
                if not stripped.startswith("$"):
                    violations.append(Violation(
                        rule="scss-warn:raw-property",
                        line_no=i,
                        line_text=stripped,
                        suggestion=RAW_PROPERTY_SUGGESTION,
                    ))

        # Update depth trackers.
        if enters_allowed and open_braces:
            allowed_depth += open_braces
        depth += open_braces
        depth -= close_braces
        if depth < 0:
            depth = 0
        if allowed_depth > depth:
            allowed_depth = depth

    return violations


# ---------------------------------------------------------------------------
# Payload extraction
# ---------------------------------------------------------------------------

def extract_contents(payload: dict) -> list[tuple[str, str]]:
    """
    Return a list of (file_path, new_content) pairs from the tool_input.

    * Write: (file_path, content)
    * Edit:  (file_path, new_string)  -- only the new section, not full file
    * MultiEdit: multiple (file_path, new_string) per edit
    """
    tool_input = payload.get("tool_input") or {}
    pairs: list[tuple[str, str]] = []

    fp = (
        tool_input.get("file_path")
        or tool_input.get("filePath")
        or tool_input.get("path")
        or ""
    )

    # Write tool
    if "content" in tool_input and isinstance(tool_input["content"], str):
        pairs.append((fp, tool_input["content"]))

    # Edit tool
    if "new_string" in tool_input and isinstance(tool_input["new_string"], str):
        pairs.append((fp, tool_input["new_string"]))

    # MultiEdit tool
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for edit in edits:
            if not isinstance(edit, dict):
                continue
            new_str = edit.get("new_string", "")
            if isinstance(new_str, str):
                per_fp = edit.get("file_path", fp) or fp
                pairs.append((per_fp, new_str))

    return pairs


RX_COMPONENT_DECORATOR = re.compile(r"@Component\s*\(")


_SIBLING_DECORATOR: dict[Path, bool] = {}  # one read per sibling per call


def sibling_has_decorator(path: Path) -> bool:
    """G-2: True when the ``<stem>.ts`` beside ``path`` is on disk and carries ``@Component(``."""
    ts_path = path.with_name(path.name[: -len(path.suffix)] + ".ts")
    if ts_path not in _SIBLING_DECORATOR:
        _SIBLING_DECORATOR[ts_path] = (
            ts_path.is_file() and RX_COMPONENT_DECORATOR.search(ts_path.read_text(encoding="utf-8")) is not None)
    return _SIBLING_DECORATOR[ts_path]


def text_has_decorator(text: str) -> bool:
    """G-2: True when ``text`` carries ``@Component(``."""
    return RX_COMPONENT_DECORATOR.search(text) is not None


def counts_as_found(check, *args) -> bool:
    """V-2: a check that raises counts as found, so the file is scanned (the stricter outcome)."""
    try:
        return check(*args)
    except Exception as e:  # noqa: BLE001
        log(f"file check failed (scanning the file): {e}")
        return True


def is_template_html(path: Path) -> bool:
    if path.name.endswith(".component.html"):
        return True
    return path.suffix == ".html" and counts_as_found(sibling_has_decorator, path)


def is_component_ts(path: Path, get_text) -> bool:
    """
    The name decides first, so a ``.spec.ts`` or ``.d.ts`` is never read. Otherwise
    ``get_text()`` gives the file as it will be after the edit (the written text when no view exists).
    """
    if path.name.endswith(".component.ts"):
        return True
    if path.suffix != ".ts" or path.name.endswith((".spec.ts", ".d.ts")):
        return False
    return counts_as_found(lambda: text_has_decorator(get_text()))


def is_component_scss(path: Path) -> bool:
    if path.name.endswith(".component.scss"):
        return True
    return path.suffix in (".scss", ".css") and counts_as_found(sibling_has_decorator, path)


def post_edit_snapshot(payload: dict, file_path_str: str, snapshots: dict[str, PostEditView]) -> PostEditView:
    """The post-edit view of a file, built once per file per call; a builder fault makes it unavailable (V-2)."""
    if file_path_str not in snapshots:
        try:
            snapshots[file_path_str] = build_post_edit_view(payload, file_path_str)
        except Exception as e:  # noqa: BLE001
            log(f"post-edit view failed (judging fragments): {e}")
            snapshots[file_path_str] = PostEditView(file_path_str, None, None, "disk-plus-edits", "builder-error")
    return snapshots[file_path_str]


# ---------------------------------------------------------------------------
# Block / emit
# ---------------------------------------------------------------------------

def format_block_message(file_path: str, blocking: list[Violation]) -> str:
    bar = "=" * 62
    lines = [
        "",
        bar,
        "[architecture-guard] BLOCKED -- Raw CSS / anti-pattern in write",
        bar,
        f"File: {file_path}",
        f"Violations: {len(blocking)}",
        "",
    ]
    for v in blocking[:15]:  # cap at 15 to keep output readable
        lines.append(f"  {format_rule_label(v)} line {v.line_no}")
        excerpt = v.line_text if len(v.line_text) <= 120 else v.line_text[:117] + "..."
        lines.append(f"    | {excerpt}")
        lines.append(f"    -> {v.suggestion}")
        lines.append("")
    if len(blocking) > 15:
        lines.append(f"  ... and {len(blocking) - 15} more violation(s)")
        lines.append("")
    # The documents a reader is pointed at are a project fact, so they come from
    # architecture-guard.rules.json (`reference_documents`). An empty list simply
    # omits the section; no verdict depends on it.
    footer = document_footer(blocking)
    if footer:
        lines.extend(footer)
        lines.append("")
    reference_docs = load_project_settings()["reference_documents"]
    if reference_docs:
        lines.append("Reference:")
        lines.extend(f"  {doc}" for doc in reference_docs)
        lines.append("")
    lines.extend([
        "Escape hatch: CLAUDE_ARCH_GUARD=off (use sparingly)",
        bar,
        "",
    ])
    return "\n".join(lines)


def emit_warnings(file_path: str, warnings: list[Violation]) -> None:
    bar = "-" * 62
    out = [
        "",
        bar,
        f"[architecture-guard] WARN -- component SCSS has raw properties: {file_path}",
        bar,
    ]
    for v in warnings[:10]:
        out.append(f"  line {v.line_no}: {v.line_text[:100]}")
    if len(warnings) > 10:
        out.append(f"  ... and {len(warnings) - 10} more")
    out.append(
        "  -> Move these to the template as Tailwind utilities. See the design-pattern document."
    )
    out.append(bar)
    out.append("")
    print("\n".join(out), file=sys.stderr)


def emit_scss_warnings(file_path: str, warnings: list[Violation]) -> None:
    """
    Print stylesheet warnings grouped by rule, in first-occurrence order.

    Each group shows its heading, up to ten offending lines and that rule's
    suggestion once. Template warnings keep using emit_warnings unchanged.
    """
    bar = "-" * 62
    groups: dict[str, list[Violation]] = {}
    for v in warnings:
        groups.setdefault(v.rule, []).append(v)
    out = [
        "",
        bar,
        f"[architecture-guard] WARN -- component SCSS warnings: {file_path}",
        bar,
    ]
    for rule, items in groups.items():
        out.append(f"  {format_rule_label(items[0])}")
        for v in items[:10]:
            out.append(f"  line {v.line_no}: {v.line_text[:100]}")
        if len(items) > 10:
            out.append(f"  ... and {len(items) - 10} more")
        out.append(f"  -> {items[0].suggestion}")
    out.extend(f"  {line}" for line in document_footer(warnings))
    out.append(bar)
    out.append("")
    print("\n".join(out), file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        log(f"failed to parse stdin payload: {e}")
        sys.exit(0)

    if bypass_env():
        log("bypass via CLAUDE_ARCH_GUARD=off")
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    if tool_name not in {"Edit", "Write", "MultiEdit"}:
        sys.exit(0)

    exceptions = load_exceptions()
    ignored_files = exceptions.get("ignored_files", [])
    rule_exemptions = exceptions.get("file_rule_exemptions", {})

    pairs = extract_contents(payload)
    if not pairs:
        sys.exit(0)

    blocking: list[Violation] = []
    warnings: list[Violation] = []
    target_for_block = ""
    findings: dict[str, list[Violation]] = {}  # per file, in first-seen order
    fragments: dict[str, list[str]] = {}  # new text of each edit, for the whole-file pass
    snapshots: dict[str, PostEditView] = {}  # the post-edit view of each file, built once per call

    for file_path_str, new_content in pairs:
        if not file_path_str:
            continue
        path = Path(file_path_str)

        if path_in_ignored(path, ignored_files):
            continue

        if is_template_html(path):
            findings.setdefault(file_path_str, []).extend(
                scan_template_html(new_content, path, rule_exemptions))
            fragments.setdefault(file_path_str, []).append(new_content)
        elif path.suffix == ".ts" and is_component_ts(
                path, lambda: post_edit_snapshot(payload, file_path_str, snapshots).text or new_content):
            findings.setdefault(file_path_str, []).extend(
                scan_component_ts(new_content, path, rule_exemptions))
            fragments.setdefault(file_path_str, []).append(new_content)
        elif is_component_scss(path):
            vs = scan_component_scss(new_content, path, {
                **rule_exemptions,
            })
            # SCSS violations are WARN only.
            if vs:
                emit_scss_warnings(file_path_str, vs)

    # Whole-file rules: once per file per call, on the post-edit view (G-4). Each
    # step falls back to the stricter or the earlier outcome when it raises (V-2).
    for file_path_str, texts in fragments.items():
        path = Path(file_path_str)
        view = post_edit_snapshot(payload, file_path_str, snapshots)
        try:
            extra, hw = scan_whole_file_rules(path, texts, view, rule_exemptions)
        except Exception as e:  # noqa: BLE001
            log(f"whole-file pass failed (judging fragments): {e}")
            extra = []
            hw = []
            try:
                if is_template_html(path):
                    hw = [w for t in texts for w in scan_height_chain_invariant(t, path, rule_exemptions)]
            except Exception as e2:  # noqa: BLE001 -- a failed warning means no warning
                log(f"height-chain fallback failed (no warning): {e2}")
        # One finding per inline rule is enough: the fragments' finding wins over the view's.
        reported = {v.rule for v in findings.get(file_path_str, [])}
        findings.setdefault(file_path_str, []).extend(v for v in extra if v.rule not in reported)
        # WARN-level: scroll-edge height-chain invariant. Trial window —
        # not added to `blocking`, only emitted via stderr. Promote to BLOCK
        # by moving inside scan_template_html after two regression-free weeks.
        if hw:
            emit_warnings(file_path_str, hw)

    for file_path_str, vs in findings.items():
        try:
            vs = dedupe_violations(vs)
        except Exception as e:  # noqa: BLE001
            log(f"de-duplication failed (printing every finding): {e}")
        if vs:
            blocking.extend(vs)
            target_for_block = target_for_block or file_path_str

    if blocking:
        print(format_block_message(target_for_block, blocking), file=sys.stderr)
        log_event(
            hook="architecture-guard",
            event="block",
            file=target_for_block,
            details={
                "violation_count": len(blocking),
                "violations": [
                    {"rule": getattr(v, "rule", str(v)), "line": getattr(v, "line", None)}
                    for v in blocking[:10]
                ],
            },
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        log(f"internal error (failing open): {e}")
        sys.exit(0)
