#!/usr/bin/env python3
"""
bash-gate.py -- PreToolUse hook for the Data-First Engineering Protocol.

Blocks Bash commands that write to source files via shell redirection,
sed -i, tee, awk -i inplace, or cp/mv overwriting a tracked file, unless
the destination is covered by an approved concept contract.

This closes the "bash bypass" loophole in concept-gate.py: agents can no
longer `echo 'code' > file.cs` or `sed -i 's/x/y/' file.ts` to dodge the
contract requirement.

Allowed bash (unconditionally):
    * reads (cat, grep, ls, git, find, etc.)
    * commands that write only to trivial/bypassed files (.md, .json, .yaml,
      anything under .claude/, node_modules/, bin/, obj/, dist/)
    * package managers (npm, pip, dotnet) writing to their own lockfiles
    * mkdir, rmdir, chmod, chown without file content changes
    * commands with CLAUDE_CONCEPT_GATE=off or CLAUDE_BASH_GATE=off set

Blocked bash:
    * `>` or `>>` redirection to a non-trivial source file
    * `sed -i` / `awk -i inplace` on a non-trivial source file
    * `tee` writing to a non-trivial source file
    * `cp` / `mv` whose destination is a non-trivial source file

Hook contract (Claude Code):
    stdin:  JSON with { tool_name: "Bash", tool_input: { command: "..." } }
    exit 0: allow
    exit 2: block (stderr shown to Claude)
    other:  error (fails open)
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

# Passive error logging (fail-soft import).
sys.path.insert(0, str(Path(__file__).parent))
try:
    from _error_log import log_event
except Exception:
    def log_event(*args, **kwargs):  # type: ignore[no-redef]
        return

# Reuse the concept-gate trivial-file heuristics.
try:
    HOOKS_DIR = Path(__file__).parent
    sys.path.insert(0, str(HOOKS_DIR))
    from importlib import import_module
    _gate = import_module("concept_gate") if (HOOKS_DIR / "concept_gate.py").exists() else None
except Exception:
    _gate = None

# Standalone duplicates so we don't depend on the concept-gate module name.
TRIVIAL_EXTENSIONS = {
    ".md", ".markdown", ".txt", ".rst",
    ".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".gitignore", ".gitattributes", ".editorconfig",
    ".env", ".env.example", ".env.local",
    ".lock",
    ".log",
}

BYPASS_PATH_SEGMENTS = [
    "/.claude/", "\\.claude\\", "/.claude\\", "\\.claude/",
    "/memory.md", "\\memory.md",
    "/MECHANISMS.md", "\\MECHANISMS.md",
    "/VOCABULARY.md", "\\VOCABULARY.md",
    "/concepts/", "\\concepts\\",
    "/node_modules/", "\\node_modules\\",
    "/bin/", "\\bin\\",
    "/obj/", "\\obj\\",
    "/dist/", "\\dist\\",
    "/.git/", "\\.git\\",
    "/target/", "\\target\\",
    "/.venv/", "\\.venv\\",
    "/venv/", "\\venv\\",
    "/__pycache__/", "\\__pycache__\\",
    "/.vscode/", "\\.vscode\\",
    "/.idea/", "\\.idea\\",
]

BYPASS_FILENAMES = {
    "CLAUDE.md", "memory.md", "MECHANISMS.md", "VOCABULARY.md",
    "README.md", ".gitkeep",
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "Cargo.lock", "poetry.lock", "requirements.txt",
    ".gitignore", ".gitattributes", ".editorconfig",
}

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

# Statuses the bash-gate honors (match concept-gate).
HONORED_STATUSES = {"approved", "implemented"}
IGNORED_STATUSES = {"archived", "superseded", "draft", "rejected"}


def log(msg: str) -> None:
    print(f"[bash-gate] {msg}", file=sys.stderr)


def is_trivial_target(path_str: str) -> bool:
    path = Path(path_str)
    if path.name in BYPASS_FILENAMES:
        return True
    if path.suffix.lower() in TRIVIAL_EXTENSIONS:
        return True
    ps = str(path)
    for seg in BYPASS_PATH_SEGMENTS:
        if seg in ps:
            return True
    return False


def contract_status(contract_path: Path) -> str:
    try:
        text = contract_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "unknown"
    for line in text.splitlines()[:60]:
        m = re.search(r"\*?\*?Status:\*?\*?\s*([a-zA-Z_-]+)", line)
        if m:
            s = m.group(1).lower().strip()
            if s.startswith("superseded"):
                return "superseded"
            return s
    return "unknown"


def contract_covers(contract_path: Path, target: str) -> bool:
    try:
        text = contract_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    target_norm = target.replace("\\", "/").lower()
    sections = re.split(r"(?im)^\*?\*?files to touch:?\*?\*?\s*$", text)
    blocks = sections[1:] if len(sections) >= 2 else [text]
    for b in blocks:
        chunk = re.split(r"\n\s*\n|^#", b, maxsplit=1, flags=re.MULTILINE)[0]
        for line in chunk.splitlines():
            stripped = line.strip()
            if not stripped.startswith(("-", "*", "+")):
                continue
            entry = stripped.lstrip("-*+ ").strip().strip("`").rstrip(",;.")
            if not entry or entry.lower().startswith("pre-written"):
                continue
            en = entry.replace("\\", "/").lower()
            if en in target_norm:
                return True
            esc = re.escape(en).replace(r"\.\.\.", ".*").replace(r"\*", "[^/]*")
            if re.search(rf"(^|/){esc}(/|$)", target_norm):
                return True
    return False


def has_contract_covering(target: str) -> bool:
    mds = []
    for _base in CONCEPTS_ROOTS:
        if not _base.exists():
            continue
        try:
            mds.extend(_base.rglob("*.md"))
        except OSError:
            continue
    if not mds:
        return False
    try:
        mds.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return False
    for md in mds:
        status = contract_status(md)
        if status in IGNORED_STATUSES or status not in HONORED_STATUSES:
            continue
        if contract_covers(md, target):
            return True
    return False


_QUOTE_RE = re.compile(r"""
    '(?:[^'\\]|\\.)*'      # single-quoted string
    |
    "(?:[^"\\]|\\.)*"      # double-quoted string
""", re.VERBOSE)


def _strip_quoted(command: str) -> str:
    """
    Replace every quoted segment with a sequence of spaces of the same
    length. This preserves offsets so error messages can still point at
    the right column, while hiding `>`/`|`/`tee`/etc. that appear inside
    string literals (e.g. `echo '{"a": 1}' | py -3 ...`).
    """
    def _blank(match: re.Match[str]) -> str:
        return " " * len(match.group(0))
    return _QUOTE_RE.sub(_blank, command)


def parse_redirect_targets(command: str) -> list[tuple[str, str]]:
    """
    Return list of (tool, target_path) pairs representing every write
    operation in the command. Best-effort parsing -- we miss deeply
    obfuscated constructs, but catch the common cases.

    Quoted strings are blanked before regex matching so that content
    inside them (e.g. JSON passed to echo) cannot trigger false positives.
    Tokens that look like targets are re-fetched from the ORIGINAL command
    by offset, so the returned path has its original characters.
    """
    targets: list[tuple[str, str]] = []

    # Normalize: collapse line continuations
    cmd = re.sub(r"\\\n", " ", command)
    # Mask quoted strings so our regexes don't trip on their content.
    masked = _strip_quoted(cmd)

    def _capture(match: re.Match[str], group_idx: int) -> str:
        """Return the original (un-masked) text for a capture group."""
        start, end = match.span(group_idx)
        return cmd[start:end]

    def _clean(target: str) -> str:
        """Strip surrounding quotes and trailing shell punctuation."""
        t = target.strip()
        while t and t[0] in "'\"":
            t = t[1:]
        while t and t[-1] in "'\"":
            t = t[:-1]
        # Trim anything that shell tokenization would have split on
        t = re.split(r"[;|&]", t, maxsplit=1)[0]
        return t.strip()

    def _is_dev_null(t: str) -> bool:
        return t.startswith("/dev/") or t in {"NUL", "nul"}

    # 1. Shell redirection:  > file   >> file   2> file   &> file
    for m in re.finditer(r"(?:^|\s|;|&&|\|\|)(?:\d?>>?|&>)\s*([^\s;|&<>]+)", masked):
        target = _clean(_capture(m, 1))
        if target and not _is_dev_null(target):
            targets.append((">", target))

    # 2. tee (with or without -a)
    for m in re.finditer(r"(?:^|\s|\|)tee\s+(?:-a\s+)?([^\s;|&]+)", masked):
        target = _clean(_capture(m, 1))
        if target and not _is_dev_null(target):
            targets.append(("tee", target))

    # 3. sed -i / sed -i ''
    for m in re.finditer(r"(?:^|\s)sed\s+\S*-i\S*\s+(?:\S+\s+){0,4}([^\s;|&]+)", masked):
        target = _clean(_capture(m, 1))
        if target:
            targets.append(("sed -i", target))

    # 4. awk -i inplace
    for m in re.finditer(r"(?:^|\s)awk\s+[^\n;|&]*-i\s+inplace[^\n;|&]*?\s+([^\s;|&]+)", masked):
        target = _clean(_capture(m, 1))
        if target:
            targets.append(("awk -i inplace", target))

    # 5. cp / mv: last non-flag arg is the destination
    for kw in ("cp", "mv"):
        for m in re.finditer(rf"(?:^|\s){kw}\s+((?:\S+\s+){1,})(\S+)", masked):
            args_str = _capture(m, 1) + _capture(m, 2)
            parts = [p for p in args_str.split() if not p.startswith("-")]
            if len(parts) >= 2:
                dest = _clean(parts[-1])
                if "." in Path(dest).name:
                    targets.append((kw, dest))

    # 6. dd of=file
    for m in re.finditer(r"(?:^|\s)dd\s+[^;|&]*?of=([^\s;|&]+)", masked):
        target = _clean(_capture(m, 1))
        if target:
            targets.append(("dd", target))

    # 7. python -c "...open('file','w')..." -- look at the ORIGINAL command
    # because this pattern lives inside a quoted string that we masked.
    for m in re.finditer(r"open\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"][wax]", cmd):
        targets.append(("python open-write", m.group(1)))

    # Deduplicate
    seen: set[tuple[str, str]] = set()
    unique: list[tuple[str, str]] = []
    for t in targets:
        if t in seen:
            continue
        seen.add(t)
        unique.append(t)
    return unique


def block(reason: str, command: str, targets: list[tuple[str, str]]) -> None:
    bar = "=" * 62
    msg = [
        "",
        bar,
        "[bash-gate] BLOCKED -- Data-First Engineering Protocol",
        bar,
        f"Reason:  {reason}",
        "",
        "The following bash write operations target files without an",
        "approved concept contract:",
        "",
    ]
    for tool, path in targets:
        msg.append(f"  * {tool:>10}  ->  {path}")
    msg.extend([
        "",
        "This hook exists to prevent bash from dodging the concept-gate",
        "by redirecting output to source files.",
        "",
        "Next steps:",
        "  1. Run /design-first <what you are trying to do>",
        "  2. Or use Edit/Write tools (covered by concept-gate.py)",
        "",
        "Useful commands:",
        "  /list-contracts       -- see all contracts and their statuses",
        "",
        "Escape hatches (use sparingly):",
        "  * CLAUDE_CONCEPT_GATE=off  (disables both concept-gate and bash-gate)",
        "  * CLAUDE_BASH_GATE=off     (disables only this hook)",
        bar,
        "",
    ])
    try:
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    print("\n".join(msg), file=sys.stderr)
    log_event(
        hook="bash-gate",
        event="block",
        file=targets[0][1] if targets else None,
        details={
            "reason": reason,
            "command": command[:500] if command else "",
            "target_count": len(targets),
            "targets": [p for _, p in targets[:10]],
        },
    )
    sys.exit(2)


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        sys.exit(0)  # fail open

    if os.environ.get("CLAUDE_CONCEPT_GATE", "").lower() in {"off", "0", "false", "no"}:
        sys.exit(0)
    if os.environ.get("CLAUDE_BASH_GATE", "").lower() in {"off", "0", "false", "no"}:
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    command = (payload.get("tool_input") or {}).get("command", "")
    if not command:
        sys.exit(0)

    targets = parse_redirect_targets(command)
    if not targets:
        sys.exit(0)  # no write operations detected

    # Resolve each target against CWD and check it.
    cwd = Path.cwd()
    blocked: list[tuple[str, str]] = []
    for tool, raw_path in targets:
        # Expand env vars and ~
        expanded = os.path.expandvars(os.path.expanduser(raw_path))
        if not expanded:
            continue
        full = expanded if Path(expanded).is_absolute() else str((cwd / expanded).resolve(strict=False))

        if is_trivial_target(full) or is_trivial_target(raw_path):
            continue
        if has_contract_covering(full):
            continue
        blocked.append((tool, full))

    if not blocked:
        sys.exit(0)

    block(
        "bash command writes to source file(s) without approved contract",
        command,
        blocked,
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        log(f"internal error (failing open): {e}")
        sys.exit(0)
