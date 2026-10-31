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

# The shell parser lives beside this hook in _shell_write_targets.py (a plugin default-tree helper that the
# add-on install copies into the project). A strict gate that silently stops reading is worse than a loud
# one, so when the import fails this hook exits 2 and names the missing file.
try:
    from _shell_write_targets import parse_redirect_targets
except Exception as _exc:  # noqa: BLE001 - any failure to load the parser must be loud, never open
    print(
        "[bash-gate] BLOCKED -- the shell parser could not be imported: "
        f"{Path(__file__).resolve().parent / '_shell_write_targets.py'} "
        f"is missing or unreadable ({type(_exc).__name__}: {_exc}). "
        "Re-run /auto-improve-strict-shell-gate-install to restore it, or remove the bash-gate row "
        "from .claude/settings.json with the Edit tool (this hook judges only Bash, so Edit still works).",
        file=sys.stderr,
    )
    sys.exit(2)

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

#: Round 3 task D: bound at import time via ``getattr`` (see concept-gate.py's
#: identical comment). A missing function is treated EXACTLY like ``_pp``
#: being ``None`` everywhere below, including the fallback-mode banner text.
_pp_checkout_equivalent_path = (
    getattr(_pp, "checkout_equivalent_path", None) if _pp is not None else None
)
_pp_enclosing_worktree_root = (
    getattr(_pp, "enclosing_worktree_root", None) if _pp is not None else None
)

# Contract lookup index (fail-soft). Every entry point is bound with getattr, so
# a missing, stale or broken module leaves this gate on its own functions (D4);
# nothing is called at import.
_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if _SCRIPTS_DIR.exists():
    sys.path.insert(0, str(_SCRIPTS_DIR))
_ci_make = _ci_status = _ci_covers = _ci_file = None
try:
    import _contract_index as _ci_mod
    _ci_make = getattr(_ci_mod, "make_variant", None)
    _ci_status = getattr(_ci_mod, "status_of", None)
    _ci_covers = getattr(_ci_mod, "covers", None)
    _ci_file = getattr(_ci_mod, "__file__", None)
    if any(f is None for f in (_ci_make, _ci_status, _ci_covers, _ci_file)):
        raise AttributeError("contract lookup index is incomplete")
except Exception:
    _ci_make = _ci_status = _ci_covers = _ci_file = None

CONCEPTS_ROOTS = (
    _pp.concepts_roots() if _pp else [HOME / ".claude" / "concepts"]
)
CONCEPTS_ROOT = next(
    (r for r in CONCEPTS_ROOTS if r.exists()), CONCEPTS_ROOTS[0]
)

# Statuses the bash-gate honors (match concept-gate).
HONORED_STATUSES = {"approved", "implemented"}
IGNORED_STATUSES = {"archived", "superseded", "draft", "rejected"}

#: The full path this hook's copy of ``_project_paths.py`` would live at, used
#: only to name the missing helper in a fallback-mode block banner (INV-5).
_PROJECT_PATHS_EXPECTED_PATH = str(Path(__file__).resolve().parent / "_project_paths.py")

#: Case-insensitive via the flag, never a ``.lower()`` copy (see
#: concept-gate.py's identical comment). The optional trailing group after
#: ``worktrees`` folds the Windows aliases the helper recognises (round 3
#: task F).
_FALLBACK_WORKTREE_MARKER_RE = re.compile(
    r"/\.claude/worktrees(?:[.\ ]*|:[^/]*)/[^/]+", re.IGNORECASE
)


def _fallback_checkout_equivalent(path_str: str) -> str:
    """INV-5 fallback: crude stand-in for ``_project_paths.checkout_equivalent_path``.

    Used ONLY when ``import _project_paths`` failed. Strips the segment
    test's input down to the text after the LAST worktree-segment marker, so
    worktree source still gets no bypass while the helper is missing. A path
    with no marker is returned unchanged (today's behaviour).

    "." components are dropped BEFORE doubled separators are collapsed (round
    3 task E) -- see concept-gate.py's identical comment.
    """
    norm = path_str.replace("\\", "/")
    no_dots = re.sub(r"(^|/)\.(?=/|$)", r"\1", norm)
    collapsed = re.sub(r"/{2,}", "/", no_dots)
    matches = list(_FALLBACK_WORKTREE_MARKER_RE.finditer(collapsed))
    if not matches:
        return norm
    return collapsed[matches[-1].end():]


def _segment_test_path(path_str: str) -> str:
    """The text a guard's segment/substring bypass test should read (INV-2)."""
    if _pp_checkout_equivalent_path is not None:
        return _pp_checkout_equivalent_path(path_str)
    return _fallback_checkout_equivalent(path_str)


def _extra_concepts_roots_for_target(target_str: str) -> list[Path]:
    """A worktree target's own ``.claude/concepts`` (INV-7 / A3)."""
    if _pp_enclosing_worktree_root is None:
        return []
    root = _pp_enclosing_worktree_root(target_str)
    if not root:
        return []
    return [Path(root) / ".claude" / "concepts"]


def log(msg: str) -> None:
    print(f"[bash-gate] {msg}", file=sys.stderr)


def is_trivial_target(path_str: str) -> bool:
    path = Path(path_str)
    if path.name in BYPASS_FILENAMES:
        return True
    if path.suffix.lower() in TRIVIAL_EXTENSIONS:
        return True
    # INV-2: only the segment bypass test reads the checkout-equivalent path.
    # This is called on BOTH the resolved `full` path and the raw `raw_path`
    # at the two call sites in main() (FM: a raw worktree path must not be
    # rescued by the raw-text check).
    ps = _segment_test_path(str(path))
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


def bash_entries(contract_path: Path) -> list[str]:
    """This gate's own parse of a contract's 'Files to touch' entries.

    Normalised (forward slashes, lower case); [] on a read failure. It stops at
    the first blank line and applies no path filter, which is why this gate
    keeps its own parser rather than the shared one.
    """
    try:
        text = contract_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    entries: list[str] = []
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
            entries.append(entry.replace("\\", "/").lower())
    return entries


def bash_entries_cover(entries: list[str], target: str) -> bool:
    """True iff any entry from ``bash_entries`` references the target path."""
    target_norm = target.replace("\\", "/").lower()
    for en in entries:
        if en in target_norm:
            return True
        # A literal entry (neither '*' nor '...') has a regex that is the entry
        # itself, which can only match where the substring test above did.
        if "*" not in en and "..." not in en:
            continue
        esc = re.escape(en).replace(r"\.\.\.", ".*").replace(r"\*", "[^/]*")
        if re.search(rf"(^|/){esc}(/|$)", target_norm):
            return True
    return False


def contract_covers(contract_path: Path, target: str) -> bool:
    return bash_entries_cover(bash_entries(contract_path), target)


_CI_VARIANT = None
_CI_TRIED = False


def _ci_variant():
    """This gate's variant spec for the contract lookup index, built on first use.

    None whenever the index is unavailable: the wrappers below then run this
    gate's own functions on the real file, exactly as without an index.
    """
    global _CI_VARIANT, _CI_TRIED
    if not _CI_TRIED:
        _CI_TRIED = True
        try:
            if _ci_make is not None:
                _CI_VARIANT = _ci_make(
                    "bash", contract_status, bash_entries, bash_entries_cover,
                    [os.path.abspath(__file__), _ci_file],
                )
        except Exception:
            _CI_VARIANT = None
    return _CI_VARIANT


def _indexed_contract_status(contract_path: Path) -> str:
    """``contract_status`` through the contract lookup index (D4: any doubt reads the file).

    The index answers only for a file whose stat signature is unchanged and not
    racy, so it can skip a read but never change an allow or a block. Named
    limit it cannot see: a same-size in-place rewrite whose modification time is
    then restored, over two seconds after the last parse. Recovery:
    ``CLAUDE_CONTRACT_INDEX=off`` or deleting ``.claude/cache/contract-index/``.
    """
    try:
        variant = _ci_variant()
        if variant is not None:
            result = _ci_status(variant, contract_path)
            if isinstance(result, str):
                return result
    except Exception:
        pass
    return contract_status(contract_path)


def _indexed_contract_covers(contract_path: Path, target: str) -> bool:
    """``contract_covers`` through the contract lookup index (D4)."""
    try:
        variant = _ci_variant()
        if variant is not None:
            result = _ci_covers(variant, contract_path, target)
            if isinstance(result, bool):
                return result
    except Exception:
        pass
    return contract_covers(contract_path, target)


def has_contract_covering(target: str) -> bool:
    mds = []
    for _base in CONCEPTS_ROOTS:
        if not _base.exists():
            continue
        try:
            mds.extend(_base.rglob("*.md"))
        except OSError:
            continue
    # INV-7 / A3: a worktree target's own .claude/concepts, not a new rank
    # in claude_roots(), added only for that target.
    for _extra in _extra_concepts_roots_for_target(target):
        if not _extra.exists():
            continue
        try:
            mds.extend(_extra.rglob("*.md"))
        except OSError:
            continue
    if not mds:
        return False
    try:
        mds.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return False
    for md in mds:
        status = _indexed_contract_status(md)
        if status in IGNORED_STATUSES or status not in HONORED_STATUSES:
            continue
        if _indexed_contract_covers(md, target):
            return True
    return False


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
        "To remove this gate from the project, run /auto-improve-strict-shell-gate-uninstall.",
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

    reason = "bash command writes to source file(s) without approved contract"
    if _pp_checkout_equivalent_path is None:
        reason += (
            f" -- NOTE: _project_paths.py could not be imported (looked for "
            f"{_PROJECT_PATHS_EXPECTED_PATH}); fallback mode is in effect"
        )
    block(reason, command, blocked)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        log(f"internal error (failing open): {e}")
        sys.exit(0)
