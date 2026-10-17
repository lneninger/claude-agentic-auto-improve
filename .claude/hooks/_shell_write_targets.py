#!/usr/bin/env python3
"""
_shell_write_targets.py -- the shell parser two hooks share: which files a shell command writes.

``parse_redirect_targets(command)`` reads shell text and returns (tool, path) pairs for the
redirect, ``tee``, ``sed -i``, ``awk -i inplace``, ``cp``/``mv``, ``dd of=`` and Python
write-open forms it recognises. ``_QUOTE_RE`` and ``_strip_quoted`` are the two pieces it uses.
They were moved VERBATIM from ``bash-gate.py`` (lines 365-474) so the default main-checkout
guard no longer has to load the strict add-on's file to read a command.

Its two importers:
  * ``_main_checkout_guard.py`` (a default hook helper), and
  * ``bash-gate.py`` (the strict shell gate add-on).

It reads only the command text and uses only the standard library (``re``, ``pathlib``), so it
can never fail to load for a missing sibling. It is a helper: the underscore marks it, and it
is never registered in ``hooks.json``.
"""

from __future__ import annotations

import re
from pathlib import Path

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
