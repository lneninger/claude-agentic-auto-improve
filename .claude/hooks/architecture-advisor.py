#!/usr/bin/env python3
"""
architecture-advisor.py -- UserPromptSubmit hook injecting CSS rules.

When the user prompt mentions UI/frontend keywords (component, template, style,
design, ui, layout, theme, scss, css, html), inject a short reminder block
pointing at the project's design documents and listing banned CSS patterns. This
gives the agent a just-in-time nudge BEFORE it starts writing, complementing the
architecture-guard.py PreToolUse blocker that runs AFTER.

Project-shaped facts -- where the front-end applications live, and which
documents the reminder cites -- are NOT hard-coded here. They come from
architecture-guard.rules.json (`frontend_projects_root`, `reference_documents`),
the same file the guard reads, so the two never disagree. With both absent the
hook still emits every rule it emits today; it simply detects no application
name and prints no reference section.

Hook contract (Claude Code):
    stdin:  JSON with { prompt: <user text>, ... }
    stdout: JSON with { hookSpecificOutput: { hookEventName: 'UserPromptSubmit',
                        additionalContext: <string injected into the prompt> } }
    exit 0: succeed (additionalContext is injected if present)
    other:  non-fatal -- fails open

Bypass:
    CLAUDE_ARCH_ADVISOR=off -- disable for a session
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HOME = Path.home()
sys.path.insert(0, str(Path(__file__).parent))
try:  # project-local .claude first, global second
    import _project_paths as _pp
except Exception:  # pragma: no cover -- hooks must never crash a prompt
    _pp = None

RULES_FILE = (
    _pp.hook_file("architecture-guard.rules.json") if _pp
    else HOME / ".claude" / "hooks" / "architecture-guard.rules.json"
)

_DEFAULT_FRONTEND_PROJECTS_ROOT = "projects"
_DEFAULT_REFERENCE_DOCUMENTS: list[str] = []
_PROJECT_SETTINGS: dict | None = None


def load_project_settings() -> dict:
    """
    Read the two project-shaped facts from architecture-guard.rules.json.

    Shared with architecture-guard.py on purpose: the advisor names the same
    application root and the same reference documents the guard names, so one
    file owns both. Neither key changes which rules are emitted.
    """
    global _PROJECT_SETTINGS
    if _PROJECT_SETTINGS is not None:
        return _PROJECT_SETTINGS
    data: dict = {}
    try:
        if RULES_FILE.exists():
            loaded = json.loads(RULES_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
    except (OSError, json.JSONDecodeError) as e:
        log(f"failed to read project settings: {e}")
    root = data.get("frontend_projects_root")
    docs = data.get("reference_documents")
    _PROJECT_SETTINGS = {
        "frontend_projects_root": (
            str(root).strip("/") if isinstance(root, str) and root.strip()
            else _DEFAULT_FRONTEND_PROJECTS_ROOT
        ),
        "reference_documents": (
            [str(d) for d in docs] if isinstance(docs, list)
            else list(_DEFAULT_REFERENCE_DOCUMENTS)
        ),
    }
    return _PROJECT_SETTINGS


def app_path_rx() -> re.Pattern[str]:
    """
    Per-app rules: when the user prompt mentions a path under
    <frontend_projects_root>/<app>/, the matching .app-rules.json is loaded and
    its `advisorRemindersAppendix` is appended to the reminder block.
    """
    root = load_project_settings()["frontend_projects_root"]
    return re.compile(re.escape(root) + r"/([a-z0-9-]+)/", re.IGNORECASE)


def find_app_rules(app_name: str, prompt_text: str) -> dict | None:
    """
    Resolve <app>/.app-rules.json by walking up from any path token in the
    prompt that references the project's front-end tree. Falls back to None
    when the file is missing or unparseable -- the hook stays advisory.
    """
    # Try to locate the project root via any drive-letter path token in the prompt.
    candidates: list[Path] = []
    for token in re.findall(r"[a-zA-Z]:[\\/][^\s'\"<>]+", prompt_text):
        # Walk up to find <frontend_projects_root>/<app_name>/
        token_norm = Path(token.replace("\\", "/"))
        # Try every ancestor that ends in "<app_name>".
        for ancestor in [token_norm, *token_norm.parents]:
            if ancestor.name.lower() == app_name.lower():
                candidates.append(ancestor)
                break
    # Also try the current project root, which the editor exports, then the CWD.
    root = load_project_settings()["frontend_projects_root"]
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        candidates.append(Path(project_dir) / root / app_name)
    candidates.append(Path.cwd() / root / app_name)
    for c in candidates:
        rules_file = c / ".app-rules.json"
        if rules_file.exists():
            try:
                return json.loads(rules_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
    return None


TRIGGER_KEYWORDS = {
    "component", "template", "style", "styles", "design", "ui", "layout",
    "theme", "scss", "css", "html", "material", "tailwind", "angular",
    "dashboard", "dialog", "card", "panel", "sidebar", "button", "widget",
}

# Narrower keyword set for the ui-ux-pro-max reference nudge. Triggers ONLY
# when the prompt looks like a layout-design request, not every UI mention.
PRO_MAX_LAYOUT_KEYWORDS = {
    "dashboard", "layout", "page", "list-view", "listview",
    "form-layout", "card-layout", "table-layout",
    "blade", "panel-layout",
}

PRO_MAX_REFERENCE_FILES = (
    "product-patterns.md",
    "ux-guidelines.md",
    "chart-decisions.md",
    "finance-palettes.md",
)

PRO_MAX_NUDGE = """\
[architecture-advisor] Layout/UX hint: this looks like a layout-design request.
Before writing, glance at:
  ~/.claude/references/ui-ux-pro-max/product-patterns.md (Blade + dense-metrics-grid + 6 product patterns)
  ~/.claude/references/ui-ux-pro-max/ux-guidelines.md   (~60 severity-flagged UX rules)
The reference catalog is advisory, NOT authoritative -- when it disagrees with a document in the "Reference files" list above, the project file wins. Palette hexes there are chart-config-only colors, NEVER theme-token replacements.
"""

REMINDER = """\
[architecture-advisor] CSS/Tailwind reminder for this session:

* Templates (.component.html): ZERO static style="..." attributes allowed.
  Every static property must be a Tailwind utility from the @theme bridge.
  Dynamic [style.prop]="expr()" bindings ARE allowed for runtime-computed values.

* Component SCSS (.component.scss): near-empty. Only allowed content is
  ::ng-deep / @keyframes / @media / @supports / @apply blocks. Raw property
  rules belong in the template as Tailwind classes.

* Banned: text-gray-*, bg-gray-*, border-gray-* -> use text-on-surface-variant,
  bg-surface-variant, border-outline-variant (from the Material @theme bridge).

* Banned: hardcoded hex colors in templates -> use Material token utilities
  (text-primary, bg-surface-container, border-outline-variant, etc.).

* Banned: inline template: / styles: in @Component() decorators -> always use
  templateUrl + styleUrl pointing at .component.html / .component.scss.

* Banned: inline overflow-y-auto / sticky top-0 for scroll containers -> use
  the global scroll-edge / scroll-edge-content / scroll-edge-header classes.

The PreToolUse architecture-guard.py hook WILL reject writes that violate
these rules. Get it right the first time -- don't trial-and-error against
the guard.
"""


def reference_section() -> str:
    """
    Render the "Reference files" block from `reference_documents` in
    architecture-guard.rules.json. An empty list omits the block entirely --
    the reminder above stands on its own, and no rule depends on it.
    """
    docs = load_project_settings()["reference_documents"]
    if not docs:
        return ""
    lines = ["Reference files (read before writing any UI code):"]
    lines.extend(f"  {d}" for d in docs)
    return "\n".join(lines) + "\n"


def log(msg: str) -> None:
    print(f"[architecture-advisor] {msg}", file=sys.stderr)


def main() -> None:
    if os.environ.get("CLAUDE_ARCH_ADVISOR", "").lower() in {"off", "0", "false", "no"}:
        sys.exit(0)

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        log(f"failed to parse stdin: {e}")
        sys.exit(0)

    prompt_text = payload.get("prompt", "") or payload.get("user_prompt", "")
    if not isinstance(prompt_text, str) or not prompt_text.strip():
        sys.exit(0)

    tokens = set(re.findall(r"[a-zA-Z][a-zA-Z-]{2,}", prompt_text.lower()))
    if not (tokens & TRIGGER_KEYWORDS):
        sys.exit(0)

    # Per-app appendix: detect referenced apps and append each app's reminders.
    extra_blocks: list[str] = []
    seen_apps: set[str] = set()
    for match in app_path_rx().finditer(prompt_text):
        app = match.group(1).lower()
        if app in seen_apps:
            continue
        seen_apps.add(app)
        rules = find_app_rules(app, prompt_text)
        if not rules:
            continue
        appendix = rules.get("advisorRemindersAppendix", "").strip()
        if appendix:
            extra_blocks.append(appendix)

    additional_context = REMINDER
    refs = reference_section()
    if refs:
        additional_context += "\n" + refs
    if extra_blocks:
        additional_context += "\n\n" + "\n\n".join(extra_blocks)

    # Narrow ui-ux-pro-max layout nudge. Fires only when:
    #   - prompt contains a layout-specific keyword (not just "ui" / "component")
    #   - prompt does NOT already mention any of the reference filenames
    prompt_lower = prompt_text.lower()
    if any(k in tokens for k in PRO_MAX_LAYOUT_KEYWORDS):
        if not any(ref in prompt_lower for ref in PRO_MAX_REFERENCE_FILES):
            additional_context += "\n\n" + PRO_MAX_NUDGE

    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": additional_context,
        }
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        log(f"internal error (failing open): {e}")
        sys.exit(0)
