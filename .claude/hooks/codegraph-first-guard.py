#!/usr/bin/env python3
"""
codegraph-first-guard.py -- PreToolUse hook for the CodeGraph-First Protocol.

Blocks Read / Grep / Glob on source-code paths until at least one CodeGraph
tool has been called in the current investigation turn.

The "turn" is bounded by UserPromptSubmit:
    UserPromptSubmit -> codegraph-turn-reset.py deletes the sentinel
    PostToolUse on mcp__codegraph__* -> codegraph-turn-tracker.py creates it
    PreToolUse on Read|Grep|Glob -> this hook checks for the sentinel

Hook contract (Claude Code):
    stdin:  JSON with { tool_name, tool_input: {...} }
    exit 0: allow
    exit 2: block (stderr shown to Claude)
    other:  error (hook fails open -- logs to stderr, allows the call)

Bypass:
    CLAUDE_SKIP_CG=1   -- user-set escape hatch for one session
    CLAUDE_SKIP_CG=off -- same as above (matches concept-gate convention)

Sentinel:
    <cwd>/.claude/.codegraph-used-this-turn
    Created by codegraph-turn-tracker.py after any mcp__codegraph__* call.
    Removed by codegraph-turn-reset.py on UserPromptSubmit.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Passive error logging (fail-soft import).
sys.path.insert(0, str(Path(__file__).parent))
try:
    from _error_log import log_event
except Exception:
    def log_event(*args, **kwargs):  # type: ignore[no-redef]
        return

SENTINEL_NAME = ".codegraph-used-this-turn"

# File extensions that bypass the gate unconditionally (non-code).
TRIVIAL_EXTENSIONS = {
    ".md", ".markdown", ".txt", ".rst",
    ".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".gitignore", ".gitattributes", ".editorconfig",
    ".env", ".lock",
    ".log", ".csv", ".tsv",
    ".sql", ".http",
}

# File extensions considered source code (gated without prior CodeGraph call).
SOURCE_EXTENSIONS = {
    ".cs", ".fs", ".vb", ".fsx", ".csx",
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".html", ".scss", ".sass", ".css", ".less",
    ".py", ".pyx", ".pyi",
    ".java", ".kt", ".scala",
    ".go", ".rs", ".cpp", ".c", ".h", ".hpp",
    ".rb", ".php", ".swift",
}

# Path substrings that bypass the gate unconditionally (generated, deps, etc.).
BYPASS_PATH_SEGMENTS = [
    "/.claude/",
    "\\.claude\\",
    "/.claude\\",
    "\\.claude/",
    "/.git/",
    "\\.git\\",
    "/node_modules/",
    "\\node_modules\\",
    "/bin/",
    "\\bin\\",
    "/obj/",
    "\\obj\\",
    "/dist/",
    "\\dist\\",
    "/build/",
    "\\build\\",
    "/migrations/",
    "\\migrations\\",
    "/generated/",
    "\\generated\\",
    "/assets/wiki/",
    "\\assets\\wiki\\",
    "/__pycache__/",
    "\\__pycache__\\",
    "/.venv/",
    "\\.venv\\",
    "/venv/",
    "\\venv\\",
    "/concepts/",
    "\\concepts\\",
    "/.codegraph/",
    "\\.codegraph\\",
]

# Filenames that bypass the gate.
BYPASS_FILENAMES = {
    "CLAUDE.md",
    "memory.md",
    "MECHANISMS.md",
    "VOCABULARY.md",
    "JOURNAL.md",
    "INTEGRATION.md",
    "README.md",
    ".gitkeep",
}


def log(msg: str) -> None:
    """Log to stderr so Claude sees the diagnostic line."""
    print(f"[codegraph-first-guard] {msg}", file=sys.stderr)


def bypass_env() -> bool:
    """Hard bypass via environment variable."""
    val = os.environ.get("CLAUDE_SKIP_CG", "").lower()
    return val in {"1", "on", "true", "yes", "off"}


def sentinel_path() -> Path:
    """Project-local sentinel path under <cwd>/.claude/."""
    return Path.cwd() / ".claude" / SENTINEL_NAME


def sentinel_exists() -> bool:
    return sentinel_path().exists()


def normalize(s: str) -> str:
    return s.replace("\\", "/").lower()


def has_bypass_segment(path_str: str) -> bool:
    norm = normalize(path_str)
    return any(normalize(seg) in norm for seg in BYPASS_PATH_SEGMENTS)


def classify_path(path_str: str) -> str:
    """
    Classify a file-path-like string.

    Returns:
        'allowed' -- always allow (markdown, config, generated, deps, etc.)
        'source'  -- gated; requires prior CodeGraph call
        'unknown' -- ambiguous; gated under strict policy
    """
    if not path_str:
        return "allowed"

    if has_bypass_segment(path_str):
        return "allowed"

    name = Path(path_str).name
    if name in BYPASS_FILENAMES:
        return "allowed"

    suffix = Path(path_str).suffix.lower()
    if suffix in TRIVIAL_EXTENSIONS:
        return "allowed"
    if suffix in SOURCE_EXTENSIONS:
        return "source"

    return "unknown"


def classify_pattern(pattern: str) -> str:
    """
    Classify a Grep regex pattern or Glob filename pattern.

    Returns:
        'allowed' -- pattern explicitly targets allowed file types
        'source'  -- pattern targets source files
        'unknown' -- ambiguous
    """
    if not pattern:
        return "unknown"

    lower = pattern.lower()

    # Glob-style file-extension targets.
    for ext in TRIVIAL_EXTENSIONS:
        if lower.endswith(ext) or f"*{ext}" in lower or f"{{{ext[1:]}" in lower:
            return "allowed"
    for ext in SOURCE_EXTENSIONS:
        if lower.endswith(ext) or f"*{ext}" in lower:
            return "source"

    # Generic patterns like `**/*` with no extension token -> ambiguous.
    return "unknown"


def extract_targets(tool_name: str, tool_input: dict) -> tuple[list[str], list[str]]:
    """
    Return (path_targets, pattern_targets) for the given tool payload.

    path_targets    -- file/dir paths that classify_path() handles.
    pattern_targets -- glob/regex patterns that classify_pattern() handles.
    """
    paths: list[str] = []
    patterns: list[str] = []

    if tool_name == "Read":
        for key in ("file_path", "filePath", "path"):
            v = tool_input.get(key)
            if isinstance(v, str) and v:
                paths.append(v)
                break

    elif tool_name == "Glob":
        v = tool_input.get("pattern")
        if isinstance(v, str) and v:
            patterns.append(v)
        v = tool_input.get("path")
        if isinstance(v, str) and v:
            paths.append(v)

    elif tool_name == "Grep":
        v = tool_input.get("path")
        if isinstance(v, str) and v:
            paths.append(v)
        v = tool_input.get("glob")
        if isinstance(v, str) and v:
            patterns.append(v)
        v = tool_input.get("type")
        # `type: "cs"` / `type: "ts"` etc. -> source-ish; convert to pattern.
        if isinstance(v, str) and v:
            patterns.append(f"*.{v.lstrip('.')}")

    return paths, patterns


def decide(tool_name: str, tool_input: dict) -> tuple[str, str]:
    """
    Return (decision, reason).

    decision: 'allow' | 'block'
    reason:   human-readable explanation
    """
    paths, patterns = extract_targets(tool_name, tool_input)

    # If we couldn't extract anything, fail open.
    if not paths and not patterns:
        return "allow", "no path or pattern in payload"

    path_classes = [classify_path(p) for p in paths]
    pattern_classes = [classify_pattern(p) for p in patterns]

    all_classes = path_classes + pattern_classes

    # If everything is explicitly allowed (markdown, config, deps), allow.
    if all_classes and all(c == "allowed" for c in all_classes):
        return "allow", "all targets in non-source allowlist"

    # If any target is source OR ambiguous (Grep/Glob with no extension hint),
    # we require a prior CodeGraph call this turn.
    if sentinel_exists():
        return "allow", "CodeGraph already called this turn (sentinel present)"

    # No sentinel -> block.
    if any(c == "source" for c in all_classes):
        return "block", "source-code target without prior CodeGraph call"

    # Only "unknown" left (Grep regex, generic Glob like `**/*`).
    # Under hard-block policy, treat ambiguous code investigation as gated.
    return "block", "ambiguous codebase investigation without prior CodeGraph call"


def cg_suggestion(tool_name: str, tool_input: dict) -> str:
    """Return a tailored suggestion naming the right CodeGraph tool."""
    if tool_name == "Read":
        path = (
            tool_input.get("file_path")
            or tool_input.get("filePath")
            or tool_input.get("path")
            or ""
        )
        name = Path(path).stem if path else "Symbol"
        # Strip common C# suffixes for a cleaner search term.
        for suf in ("Service", "Controller", "Repository", "Configuration", "Entity"):
            if name.endswith(suf) and name != suf:
                name = name[: -len(suf)] or name
                break
        return (
            f"Before reading source files, ask CodeGraph:\n"
            f"  - mcp__codegraph__codegraph_search query=\"{name}\"\n"
            f"  - mcp__codegraph__codegraph_node id=<hit-id>\n"
            f"  - mcp__codegraph__codegraph_callers id=<hit-id>   (impact)\n"
            f"  - mcp__codegraph__codegraph_callees id=<hit-id>   (dependencies)\n"
            f"For broad area exploration, delegate to the Explore subagent\n"
            f"(it has codegraph_explore / codegraph_context for heavy reads)."
        )

    if tool_name == "Grep":
        pattern = tool_input.get("pattern", "") or ""
        return (
            f"Before grepping source code, ask CodeGraph:\n"
            f"  - mcp__codegraph__codegraph_search query=\"{pattern[:80]}\"\n"
            f"    (returns symbol hits with file:line; usually replaces Grep entirely)\n"
            f"  - mcp__codegraph__codegraph_callers / codegraph_callees for relationships\n"
            f"Only fall back to Grep when CodeGraph returns no results."
        )

    if tool_name == "Glob":
        pattern = tool_input.get("pattern", "") or ""
        return (
            f"Before globbing for source files, ask CodeGraph:\n"
            f"  - mcp__codegraph__codegraph_files pattern=\"{pattern[:80]}\"\n"
            f"  - mcp__codegraph__codegraph_search query=\"<symbol-name>\"\n"
            f"Glob is appropriate only for non-indexed files (markdown, config)."
        )

    return "Call any mcp__codegraph__codegraph_* tool first."


def block(reason: str, tool_name: str, tool_input: dict) -> None:
    """Emit block message and exit 2."""
    bar = "=" * 62
    suggestion = cg_suggestion(tool_name, tool_input)
    cwd_sentinel = sentinel_path()
    message = [
        "",
        bar,
        "[codegraph-first-guard] BLOCKED -- CodeGraph-First Protocol",
        bar,
        f"Tool:     {tool_name}",
        f"Reason:   {reason}",
        f"Sentinel: {cwd_sentinel} (not present)",
        "",
        "CodeGraph is the primary investigation tool. Every codebase",
        "question starts with a CodeGraph call -- only after that does",
        "the gate open for Read / Grep / Glob in the same turn.",
        "",
        suggestion,
        "",
        "Decision table: ~/.claude/references/codegraph-decision-table.md",
        "",
        "Escape hatches (use sparingly):",
        "  * One-shot:  set CLAUDE_SKIP_CG=1 in the environment",
        "  * Index dead/stale: run `codegraph sync` or `codegraph init -i`",
        bar,
        "",
    ]
    try:
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    print("\n".join(message), file=sys.stderr)
    log_event(
        hook="codegraph-first-guard",
        event="block",
        file=None,
        details={"tool": tool_name, "reason": reason},
    )
    sys.exit(2)


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        log(f"failed to parse stdin payload: {e}")
        sys.exit(0)

    if bypass_env():
        log("bypass via CLAUDE_SKIP_CG")
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    if tool_name not in {"Read", "Grep", "Glob"}:
        sys.exit(0)

    tool_input = payload.get("tool_input") or {}

    decision, reason = decide(tool_name, tool_input)
    if decision == "allow":
        sys.exit(0)

    block(reason, tool_name, tool_input)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        log(f"internal error (failing open): {e}")
        sys.exit(0)
