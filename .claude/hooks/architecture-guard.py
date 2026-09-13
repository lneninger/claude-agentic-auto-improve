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

Exception list:
    ~/.claude/hooks/architecture-guard.exceptions.json
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

HOME = Path.home()
try:  # project-local .claude first, global second
    import _project_paths as _pp
except Exception:  # pragma: no cover - hooks must never crash a tool call
    _pp = None

EXCEPTIONS_FILE = (
    _pp.hook_file("architecture-guard.exceptions.json") if _pp
    else HOME / ".claude" / "hooks" / "architecture-guard.exceptions.json"
)
EXTERNAL_RULES_FILE = (
    _pp.hook_file("architecture-guard.rules.json") if _pp
    else HOME / ".claude" / "hooks" / "architecture-guard.rules.json"
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
    _PROJECT_SETTINGS = {
        "frontend_projects_root": (
            str(root).strip("/").lower() if isinstance(root, str) and root.strip()
            else _DEFAULT_FRONTEND_PROJECTS_ROOT
        ),
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

    # Walk up to find <frontend_projects_root>/<app>/.app-rules.json.
    parts = list(file_path.resolve().parts) if file_path.is_absolute() else list(Path.cwd().joinpath(file_path).resolve().parts)
    for i in range(len(parts) - 1, 0, -1):
        if parts[i].lower() == app and i >= 2 and parts[i - 1].lower() == "projects":
            project_root = Path(*parts[: i + 1])
            rules_file = project_root / ".app-rules.json"
            if rules_file.exists():
                try:
                    data = json.loads(rules_file.read_text(encoding="utf-8"))
                    _APP_RULES_CACHE[app] = data
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

# Height-chain invariant for scroll-edge templates.
# scroll-edge + flex-1 min-h-0 inside a file whose first <div class="..."> lacks
# any of {h-full, flex-1, max-h-, min-h-screen} silently collapses to 0 px and
# renders empty content (recurring regression — observations 865 and 1292 in this project).
RX_HEIGHT_CHAIN_ANCHOR = re.compile(r"\bscroll-edge\b.*\bflex-1\b.*\bmin-h-0\b|\bflex-1\b.*\bmin-h-0\b.*\bscroll-edge\b")
RX_FIRST_DIV_CLASS = re.compile(r'<div\s+class="([^"]+)"')
RX_ROOT_HAS_HEIGHT = re.compile(r"\b(?:h-full|flex-1|max-h-|min-h-screen)\b")

# SCSS allow-contexts (wrap the raw property check):
# If a line is inside a ::ng-deep, @keyframes, @media, @supports, @apply block,
# raw properties are OK. We approximate with a line-level scan that tracks
# nesting depth of allowed blocks.
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
                violations.append(Violation(
                    rule="inline-style",
                    line_no=i,
                    line_text=line.strip(),
                    suggestion=(
                        "Replace static style=\"...\" with Tailwind utilities from "
                        "the design-pattern document under Reference below "
                        "(e.g. text-primary, bg-surface-container, "
                        "border-outline-variant, w-[200px], p-4, gap-2). "
                        "Dynamic [style.prop]=\"expr\" bindings are allowed."
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
            if RX_HEX_COLOR.search(line):
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
            if RX_INLINE_OVERFLOW.search(line) or RX_INLINE_STICKY.search(line):
                violations.append(Violation(
                    rule="scroll-edge",
                    line_no=i,
                    line_text=line.strip(),
                    suggestion=(
                        "Use the global scroll-edge / scroll-edge-content / scroll-edge-header "
                        "classes instead of inline overflow-y-auto or sticky top-0. "
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

    # Rule: inline @Component({ template: ... }) — separate exemption.
    if not file_rule_exempted(path, "inline-component-template", exemptions):
        if RX_INLINE_TEMPLATE.search(content):
            for i, line in enumerate(content.splitlines(), start=1):
                if re.search(r"\btemplate\s*:", line):
                    violations.append(Violation(
                        rule="inline-component-template",
                        line_no=i,
                        line_text=line.strip(),
                        suggestion="Use templateUrl: './xxx.component.html' — never inline template:.",
                    ))
                    break

    # Rule: inline @Component({ styles: ... }) — separate exemption.
    if not file_rule_exempted(path, "inline-component-styles", exemptions):
        if RX_INLINE_STYLES.search(content):
            for i, line in enumerate(content.splitlines(), start=1):
                if re.search(r"\bstyles\s*:", line):
                    violations.append(Violation(
                        rule="inline-component-styles",
                        line_no=i,
                        line_text=line.strip(),
                        suggestion="Use styleUrl: './xxx.component.scss' — never inline styles:.",
                    ))
                    break

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


def scan_component_scss(content: str, path: Path, exemptions: dict) -> list[Violation]:
    """
    SCSS scanner -- warns on raw property rules outside allowed contexts.
    Allowed contexts: ::ng-deep, @keyframes, @media, @supports, @apply.

    Non-blocking by design: returns violations with rule prefix 'scss-warn:'
    which the caller treats as WARN not BLOCK. This lets cleanup work proceed
    gradually without tripping on partially-migrated files.
    """
    if file_rule_exempted(path, "scss-raw-property", exemptions):
        return []

    violations: list[Violation] = []
    violations.extend(scan_external_rules(content, path, "scss", exemptions))
    depth = 0
    allowed_depth = 0  # depth inside an allowed block

    lines = content.splitlines()
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Track entering allowed contexts.
        enters_allowed = bool(
            RX_NG_DEEP.search(stripped)
            or RX_KEYFRAMES.search(stripped)
            or RX_MEDIA.search(stripped)
        )

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
                        suggestion=(
                            "This property has a 1:1 Tailwind utility. Move it to the "
                            "template as a class. Component SCSS should only hold "
                            "::ng-deep, @keyframes, @media, and @apply blocks."
                        ),
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


def is_template_html(path: Path) -> bool:
    return path.name.endswith(".component.html")


def is_component_ts(path: Path) -> bool:
    return path.name.endswith(".component.ts")


def is_component_scss(path: Path) -> bool:
    return path.name.endswith(".component.scss")


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
        lines.append(f"  [{v.rule}] line {v.line_no}")
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

    for file_path_str, new_content in pairs:
        if not file_path_str:
            continue
        path = Path(file_path_str)

        if path_in_ignored(path, ignored_files):
            continue

        if is_template_html(path):
            vs = scan_template_html(new_content, path, rule_exemptions)
            if vs:
                blocking.extend(vs)
                target_for_block = target_for_block or file_path_str
            # WARN-level: scroll-edge height-chain invariant. Trial window —
            # not added to `blocking`, only emitted via stderr. Promote to BLOCK
            # by moving inside scan_template_html after two regression-free weeks.
            hw = scan_height_chain_invariant(new_content, path, rule_exemptions)
            if hw:
                emit_warnings(file_path_str, hw)
        elif is_component_ts(path):
            vs = scan_component_ts(new_content, path, rule_exemptions)
            if vs:
                blocking.extend(vs)
                target_for_block = target_for_block or file_path_str
        elif is_component_scss(path):
            vs = scan_component_scss(new_content, path, {
                **rule_exemptions,
            })
            # SCSS violations are WARN only.
            if vs:
                emit_warnings(file_path_str, vs)

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
