#!/usr/bin/env python3
"""
concept-gate.py -- PreToolUse hook for the Data-First Engineering Protocol.

Blocks Edit / Write / MultiEdit on non-trivial files unless an APPROVED
concept contract exists under ~/.claude/concepts/<project>/ whose
"Files to touch" section references the target file(s).

Hook contract (Claude Code):
    stdin:  JSON with { tool_name, tool_input: { file_path | path | edits[] } }
    exit 0: allow (optional stdout = informational)
    exit 2: block (stderr shown to Claude)
    other:  error (hook fails open -- logs to stderr, allows the call)

Contract status lifecycle:
    draft        -> not honored (blocks)
    approved     -> honored (allows matching files)
    implemented  -> honored (allows matching files; contract is kept as record)
    archived     -> NOT honored (skipped during lookup, like it doesn't exist)
    superseded-by: <path> -> NOT honored; pointer only

Bypass:
    CLAUDE_CONCEPT_GATE=off        -- disable the hook for a session
    CLAUDE_ACTIVE_CONTRACT=<path>  -- pin a specific approved contract
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable

# Passive error logging (fail-soft import).
sys.path.insert(0, str(Path(__file__).parent))
try:
    from _error_log import log_event
except Exception:
    def log_event(*args, **kwargs):  # type: ignore[no-redef]
        return

# Shared "Files to touch" parser (fail-soft import).
# Single source of truth lives in ~/.claude/scripts/_contract_files.py;
# falling back to the inline implementations below if the shared module
# is missing keeps the gate byte-for-byte compatible with its prior form.
_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if _SCRIPTS_DIR.exists():
    sys.path.insert(0, str(_SCRIPTS_DIR))
try:
    from _contract_files import (
        contract_covers_target as _shared_contract_covers_target,
        matches_path as _shared_matches_path,
    )
    _USE_SHARED_PARSER = True
except Exception:
    _USE_SHARED_PARSER = False

HOME = Path.home()
try:  # project-local .claude first, global second
    import _project_paths as _pp
except Exception:  # pragma: no cover - hooks must never crash a tool call
    _pp = None

CONCEPTS_ROOTS = (
    _pp.concepts_roots() if _pp else [HOME / ".claude" / "concepts"]
)
CONCEPTS_ROOT = next(
    (r for r in CONCEPTS_ROOTS if r.exists()), CONCEPTS_ROOTS[0]
)

# Statuses that honor the contract (allow matching edits).
HONORED_STATUSES = {"approved", "implemented"}
# Statuses that explicitly do NOT honor the contract (skip during lookup).
# `stub` is the lifecycle status of a follow-up stub at
# ~/.claude/concepts/<project>/followups/*.followup.md -- a deferred-improvement
# placeholder created by data-architect Step 4.5. It is NOT approved and must
# not authorize edits; promote via `/design-first` against the stub's
# `What was noticed` paragraph to produce a full contract.
IGNORED_STATUSES = {"archived", "superseded", "draft", "rejected", "stub"}

# File extensions that bypass the gate unconditionally (config-like files).
TRIVIAL_EXTENSIONS = {
    ".md", ".markdown", ".txt", ".rst",
    ".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".gitignore", ".gitattributes", ".editorconfig",
    ".env", ".env.example", ".env.local",
    ".lock",
}

# Path segments that bypass the gate unconditionally.
BYPASS_PATH_SEGMENTS = [
    "/.claude/",
    "\\.claude\\",
    "/.claude\\",
    "\\.claude/",
    "/memory.md",
    "\\memory.md",
    "/MECHANISMS.md",
    "\\MECHANISMS.md",
    "/VOCABULARY.md",
    "\\VOCABULARY.md",
    "/concepts/",
    "\\concepts\\",
    "/node_modules/",
    "\\node_modules\\",
    "/bin/",
    "\\bin\\",
    "/obj/",
    "\\obj\\",
    "/dist/",
    "\\dist\\",
]

# Filenames that bypass the gate.
BYPASS_FILENAMES = {
    "CLAUDE.md",
    "memory.md",
    "MECHANISMS.md",
    "VOCABULARY.md",
    "README.md",
    ".gitkeep",
}


def log(msg: str) -> None:
    """Log to stderr so it shows up in Claude's view without blocking."""
    print(f"[concept-gate] {msg}", file=sys.stderr)


def bypass_env() -> bool:
    """Hard bypass via environment variable."""
    return os.environ.get("CLAUDE_CONCEPT_GATE", "").lower() in {"off", "0", "false", "no"}


def pinned_contract() -> Path | None:
    """Operator-pinned contract path for the current session."""
    pinned = os.environ.get("CLAUDE_ACTIVE_CONTRACT", "").strip()
    if not pinned:
        return None
    p = Path(os.path.expanduser(pinned))
    return p if p.exists() else None


def extract_target_paths(payload: dict) -> list[str]:
    """
    Pull every target file path out of a PreToolUse payload.

    Edit / Write : single `file_path` (or `filePath` / `path`).
    MultiEdit    : single `file_path` shared across all edits (all edits are
                   for the SAME file per the MultiEdit contract, so one path
                   is enough). We still also scan a hypothetical `edits[]`
                   array in case a variant payload sends multiple targets.
    """
    tool_input = payload.get("tool_input") or {}
    paths: list[str] = []

    for key in ("file_path", "filePath", "path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value and value not in paths:
            paths.append(value)

    # Defensive: some payloads may carry an edits array with per-entry paths.
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for edit in edits:
            if not isinstance(edit, dict):
                continue
            for key in ("file_path", "filePath", "path"):
                value = edit.get(key)
                if isinstance(value, str) and value and value not in paths:
                    paths.append(value)

    return paths


def is_trivial_target(path: Path) -> bool:
    """Check whether the target falls under the trivial allowlist."""
    if path.name in BYPASS_FILENAMES:
        return True
    if path.suffix.lower() in TRIVIAL_EXTENSIONS:
        return True
    path_str = str(path)
    for segment in BYPASS_PATH_SEGMENTS:
        if segment in path_str:
            return True
    return False


def detect_project_name(target: Path) -> str | None:
    """
    Walk up from the target file looking for a project root marker.
    Returns the folder name of the first directory that contains one of:
    .git, CLAUDE.md, package.json, *.sln, pyproject.toml.
    """
    markers = {".git", "CLAUDE.md", "package.json", "pyproject.toml"}
    try:
        resolved = target.resolve(strict=False)
    except OSError:
        resolved = target
    for parent in [resolved] + list(resolved.parents):
        if not parent.is_dir():
            continue
        try:
            entries = {e.name for e in parent.iterdir()}
        except (PermissionError, OSError):
            continue
        if entries & markers:
            return parent.name
        if any(e.endswith(".sln") for e in entries):
            return parent.name
    return None


def iter_contracts(project_name: str | None) -> Iterable[Path]:
    """
    Yield every candidate concept contract file, newest first.
    Project-specific folder takes precedence over the global fallback.
    """
    roots: list[Path] = []
    for _base in CONCEPTS_ROOTS:
        if project_name:
            roots.append(_base / project_name)
        roots.append(_base)
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        try:
            candidates = sorted(
                root.rglob("*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            continue
        for path in candidates:
            if path in seen:
                continue
            seen.add(path)
            yield path


def contract_status(contract_path: Path) -> str:
    """
    Read the contract and return the normalized Status field.
    Returns one of: approved, implemented, draft, archived, superseded,
    rejected, or 'unknown' if no Status line is found.
    """
    try:
        text = contract_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "unknown"
    # Scan the first 60 lines for "Status: <value>"
    for line in text.splitlines()[:60]:
        m = re.search(r"\*?\*?Status:\*?\*?\s*([a-zA-Z_-]+)", line)
        if m:
            status = m.group(1).lower().strip()
            # Normalize "superseded-by" / "superseded_by" / "superseded"
            if status.startswith("superseded"):
                return "superseded"
            return status
    return "unknown"


def contract_is_honored(contract_path: Path) -> bool:
    """True if the contract's status is one that allows edits (approved/implemented)."""
    return contract_status(contract_path) in HONORED_STATUSES


if _USE_SHARED_PARSER:
    # Re-export from the shared module so behaviour stays byte-for-byte
    # identical to the inline implementation below (kept as fallback).
    contract_covers_target = _shared_contract_covers_target
    matches_path = _shared_matches_path
else:
    def contract_covers_target(contract_path: Path, target: Path) -> bool:
        """
        Check whether the contract's 'Files to touch' list references the target.
        Matching is done on suffix paths with forward-slash normalization and
        supports glob-style '...' and '*' wildcards in the contract entries.
        """
        try:
            text = contract_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return False

        target_norm = str(target).replace("\\", "/").lower()

        # Grab every line that starts with '-' or '*' under a "Files to touch" heading.
        sections = re.split(r"(?im)^\*?\*?files to touch:?\*?\*?\s*$", text)
        if len(sections) < 2:
            candidate_blocks = [text]
        else:
            candidate_blocks = sections[1:]

        for block_text in candidate_blocks:
            # Stop at the next markdown heading (##, ###, etc.) but NOT at blank lines.
            # Many contracts use blank lines to separate subsections within a single
            # "Files to touch" block (e.g. "*New files (6):*", "*Entities...*", etc.);
            # stopping at the first blank line would miss all subsections after the first.
            chunk = re.split(r"(?m)^#{1,6}\s", block_text, maxsplit=1)[0]
            for line in chunk.splitlines():
                stripped = line.strip()
                if not stripped.startswith(("-", "*", "+")):
                    continue
                raw = stripped.lstrip("-*+ ").strip()
                # Extract the path token: prefer the first backtick-quoted span,
                # otherwise take the first whitespace-delimited token.
                # This discards inline annotations like `*(already has UserId; mark only)*`.
                bt_match = re.match(r"`([^`]+)`", raw)
                if bt_match:
                    entry = bt_match.group(1)
                else:
                    entry = raw.split()[0] if raw.split() else raw
                entry = entry.strip("`")
                if not entry or entry.lower().startswith("pre-written task"):
                    continue
                entry_norm = entry.replace("\\", "/").lower()
                entry_norm = entry_norm.rstrip(",;.")
                if matches_path(entry_norm, target_norm):
                    return True
        return False


    def matches_path(pattern: str, target: str) -> bool:
        """
        Match a 'Files to touch' entry against a normalized target path.
        Supports '...' (multi-segment wildcard), '*' (single-segment wildcard),
        and substring matching so partial repo paths work.
        """
        if not pattern:
            return False
        if pattern in target:
            return True
        escaped = re.escape(pattern)
        escaped = escaped.replace(r"\.\.\.", ".*")
        escaped = escaped.replace(r"\*", "[^/]*")
        regex = re.compile(rf"(^|/){escaped}(/|$)")
        return bool(regex.search(target))


def resolve_target(
    target: Path,
    pinned: Path | None,
) -> tuple[bool, str | None, Path | None]:
    """
    Decide whether `target` is allowed.

    Returns (allowed, reason_if_blocked, matching_contract_path).
    """
    # 1. Trivial files bypass the gate.
    if is_trivial_target(target):
        return True, None, None

    # 2. Pinned contract via env var.
    if pinned is not None and contract_is_honored(pinned) and contract_covers_target(pinned, target):
        return True, None, pinned

    # 3. Scan the concepts folder for an honored contract that covers this file.
    project_name = detect_project_name(target)
    for contract in iter_contracts(project_name):
        status = contract_status(contract)
        if status in IGNORED_STATUSES:
            continue
        if status not in HONORED_STATUSES:
            continue
        if contract_covers_target(contract, target):
            return True, None, contract

    # 4. Determine an accurate reason.
    if not CONCEPTS_ROOT.exists():
        reason = "concepts folder does not exist -- no contracts have been created yet"
    else:
        reason = "no approved contract's 'Files to touch' list references this file"
    return False, reason, None


def block(
    reason: str,
    target: str,
    project: str | None,
    extras: list[str] | None = None,
) -> None:
    """Emit a block message and exit with code 2."""
    project_hint = project or "<unknown project>"
    bar = "=" * 62
    message = [
        "",
        bar,
        "[concept-gate] BLOCKED -- Data-First Engineering Protocol",
        bar,
        f"Target:  {target}",
        f"Project: {project_hint}",
        f"Reason:  {reason}",
    ]
    if extras:
        message.append("")
        message.extend(extras)
    message.extend([
        "",
        "No approved concept contract covers this file.",
        "",
        "Next steps:",
        "  1. Run /design-first <what you are trying to do>",
        "     -> data-architect produces a contract under",
        f"        ~/.claude/concepts/{project_hint}/",
        "     -> user resolves Open Questions",
        "     -> Status flips to 'approved'",
        "     -> implementer agents are invoked",
        "",
        "Useful commands:",
        "  /list-contracts       -- see all contracts and their statuses",
        "  /validate-registries  -- check MECHANISMS.md for dead links",
        "",
        "Escape hatches (use sparingly):",
        "  * Pin an existing contract: CLAUDE_ACTIVE_CONTRACT=<path>",
        "  * Disable the gate:         CLAUDE_CONCEPT_GATE=off",
        bar,
        "",
    ])
    try:
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    print("\n".join(message), file=sys.stderr)
    log_event(
        hook="concept-gate",
        event="block",
        file=str(target) if target else None,
        details={"reason": reason, "project": project_hint},
    )
    sys.exit(2)


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        log(f"failed to parse stdin payload: {e}")
        sys.exit(0)  # fail open

    if bypass_env():
        log("bypass via CLAUDE_CONCEPT_GATE=off")
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    if tool_name not in {"Edit", "Write", "MultiEdit"}:
        sys.exit(0)

    target_strs = extract_target_paths(payload)
    if not target_strs:
        log(f"no file_path in payload for {tool_name}, allowing")
        sys.exit(0)

    pinned = pinned_contract()

    blocked_targets: list[tuple[Path, str]] = []
    allowed_count = 0
    project_for_block: str | None = None

    for target_str in target_strs:
        target = Path(target_str)
        allowed, reason, _ = resolve_target(target, pinned)
        if allowed:
            allowed_count += 1
            continue
        blocked_targets.append((target, reason or "no matching contract"))
        if project_for_block is None:
            project_for_block = detect_project_name(target)

    if not blocked_targets:
        if allowed_count > 1:
            log(f"{tool_name}: all {allowed_count} targets allowed")
        sys.exit(0)

    # At least one target was blocked -- block the entire tool call.
    first_target, first_reason = blocked_targets[0]
    extras: list[str] = []
    if len(target_strs) > 1:
        extras.append(f"{tool_name} payload had {len(target_strs)} target(s):")
        for t, reason in blocked_targets:
            extras.append(f"  - BLOCKED: {t}")
            extras.append(f"    reason:  {reason}")
        if allowed_count:
            extras.append(f"  ({allowed_count} other target(s) would have been allowed)")

    block(first_reason, str(first_target), project_for_block, extras=extras if extras else None)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        log(f"internal error (failing open): {e}")
        sys.exit(0)
