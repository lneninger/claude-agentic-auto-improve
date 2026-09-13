"""
_contract_files.py -- shared "Files to touch" parser.

Single source of truth for parsing the "Files to touch" section of a concept
contract. Used by:

    - ~/.claude/hooks/concept-gate.py  (the hard gate; via contract_covers_target)
    - .claude/scripts/derive_area.py (the accuracy-skip bucket deriver)

The exposed surface:

    extract_files_from_contract(contract_path) -> list[str]
        Returns normalized path entries (forward-slash, lowercase,
        no surrounding backticks, no trailing punctuation). Empty list on
        read failure or no section.

    matches_path(pattern, target) -> bool
        Match a single entry against a normalized target. Supports '...'
        (multi-segment) and '*' (single-segment) wildcards plus substring
        matching. Both inputs must already be forward-slash lowercase.

    contract_covers_target(contract_path, target) -> bool
        Convenience wrapper: True iff any entry matches the target Path.

Behavior is byte-for-byte identical to the original implementation that
lived inline in concept-gate.py:240-303. Any future change to the parser
goes here -- the hook re-exports.
"""

from __future__ import annotations

import re
from pathlib import Path


#: Extensions that make a bare, separator-free token credible as a file path.
PATH_EXTENSIONS = {
    ".cs", ".csproj", ".sln",
    ".ts", ".tsx", ".js", ".mjs", ".jsx",
    ".html", ".scss", ".css",
    ".json", ".yml", ".yaml", ".toml", ".xml",
    ".py", ".sql", ".md", ".cmd", ".ps1", ".sh", ".http",
}


def looks_like_path(entry: str) -> bool:
    """Reject prose bullets that sit under a Files-to-touch heading.

    The first whitespace token of "- No new entity, DbSet, migration or
    ScalpingDbContext change." is "No", which matches_path then matched
    almost everywhere -- so a contract silently covered files it never
    named. An entry qualifies only if it could actually name a file.
    """
    if not entry:
        return False
    if "/" in entry or chr(92) in entry:
        return True
    dot = entry.rfind(".")
    return dot > 0 and entry[dot:].lower() in PATH_EXTENSIONS

def extract_files_from_contract(contract_path: Path) -> list[str]:
    """
    Return the list of normalized 'Files to touch' entries from a contract.

    Entries are normalized to forward-slash, lowercase, no surrounding
    backticks, no trailing punctuation. Returns [] on read failure or
    when the contract has no recognizable section.
    """
    try:
        text = contract_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    entries: list[str] = []

    sections = re.split(r"(?im)^\*?\*?files to touch:?\*?\*?\s*$", text)
    candidate_blocks = sections[1:] if len(sections) >= 2 else [text]

    for block_text in candidate_blocks:
        chunk = re.split(r"(?m)^#{1,6}\s", block_text, maxsplit=1)[0]
        for line in chunk.splitlines():
            stripped = line.strip()
            if not stripped.startswith(("-", "*", "+")):
                continue
            raw = stripped.lstrip("-*+ ").strip()
            bt_match = re.match(r"`([^`]+)`", raw)
            if bt_match:
                entry = bt_match.group(1)
            else:
                entry = raw.split()[0] if raw.split() else raw
            entry = entry.strip("`")
            if not entry or entry.lower().startswith("pre-written task"):
                continue
            entry_norm = entry.replace("\\", "/").lower().rstrip(",;.")
            if entry_norm and looks_like_path(entry_norm):
                entries.append(entry_norm)

    return entries


def matches_path(pattern: str, target: str) -> bool:
    """
    Match a 'Files to touch' entry against a normalized target path.

    Both inputs are expected to be forward-slash, lowercase. Supports
    '...' (multi-segment wildcard), '*' (single-segment wildcard), and
    substring matching so partial repo paths work.
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


def contract_covers_target(contract_path: Path, target: Path) -> bool:
    """
    True iff the contract's 'Files to touch' list references the target.

    Convenience wrapper that combines extract_files_from_contract +
    matches_path; preserves the original concept-gate.py semantics.
    """
    target_norm = str(target).replace("\\", "/").lower()
    for entry in extract_files_from_contract(contract_path):
        if matches_path(entry, target_norm):
            return True
    return False
