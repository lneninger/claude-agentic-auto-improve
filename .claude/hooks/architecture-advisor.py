#!/usr/bin/env python3
"""
architecture-advisor.py -- UserPromptSubmit hook injecting CSS rules.

When the user prompt mentions UI/frontend keywords (component, template, style,
design, ui, layout, theme, scss, css, html), inject a short reminder block
pointing at DESIGN_PATTERNS.md and listing banned CSS patterns. This gives the
agent a just-in-time nudge BEFORE it starts writing, complementing the
architecture-guard.py PreToolUse blocker that runs AFTER.

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

# Per-app rules: when the user prompt mentions a path under
# ClientApp/projects/<app>/, the matching .app-rules.json is loaded and its
# `advisorRemindersAppendix` is appended to the reminder block.
APP_PATH_RX = re.compile(r"clientapp/projects/([a-z0-9-]+)/", re.IGNORECASE)


def find_app_rules(app_name: str, prompt_text: str) -> dict | None:
    """
    Resolve <app>/.app-rules.json by walking up from any path token in the
    prompt that references the project's clientapp tree. Falls back to None
    when the file is missing or unparseable -- the hook stays advisory.
    """
    # Try to locate the project root via any drive-letter path token in the prompt.
    candidates: list[Path] = []
    for token in re.findall(r"[a-zA-Z]:[\\/][^\s'\"<>]+", prompt_text):
        # Walk up to find ClientApp/projects/<app_name>/
        token_norm = Path(token.replace("\\", "/"))
        # Try every ancestor that ends in "<app_name>".
        for ancestor in [token_norm, *token_norm.parents]:
            if ancestor.name.lower() == app_name.lower():
                candidates.append(ancestor)
                break
    # Also try the conventional default at d:/Dev/HIPALANET/StockToolScalpingMachine/.
    candidates.append(
        Path(f"d:/Dev/HIPALANET/StockToolScalpingMachine/ClientApp/projects/{app_name}")
    )
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
The reference catalog is advisory, NOT authoritative -- when it disagrees with DESIGN_PATTERNS.md, the project file wins. Palette hexes there are chart-config-only colors, NEVER theme-token replacements.
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

Reference files (read before writing any UI code):
  ClientApp/projects/scalping-machine/DESIGN_PATTERNS.md (conversion table)
  ClientApp/projects/scalping-machine/ANGULAR_MATERIAL_RULES.md
  ClientApp/projects/scalping-machine/src/styles.scss (@theme bridge)

The PreToolUse architecture-guard.py hook WILL reject writes that violate
these rules. Get it right the first time -- don't trial-and-error against
the guard.
"""


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
    for match in APP_PATH_RX.finditer(prompt_text):
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
