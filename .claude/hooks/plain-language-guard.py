#!/usr/bin/env python3
"""
plain-language-guard.py -- Stop hook. Enforces the plain-language writing rule.

Leonardo asked twice (2026-08-29) that every message Claude writes drop bare
numbers, spell out short forms, and keep sentences short. Memory alone did not
hold the rule, so this hook turns it into an enforced gate: at end-of-turn it
reads back the prose Claude just wrote and blocks the stop when the writing
breaks a rule, listing exactly what to fix.

The four rules checked (all configurable in plain-language-guard.rules.json):

  1. Short form with no expansion -- a listed short form appears without ever
     being written out as "full words (SHORTFORM)" somewhere in the same turn.
  2. Bare number used as a label -- "step 3", "two of fourteen", "110/110",
     a naked "(4)". A number that counts something keeps its number but must
     carry a plain word saying what it counts.
  3. Sentence too long -- more than the configured word count in one sentence.
  4. Stacked dashes -- three or more em dashes inside one sentence, which is
     the "clauses nested inside clauses" shape the rule forbids.

Hook contract (Claude Code):
    stdin:  Stop payload -- transcript_path, stop_hook_active, session_id
    exit 0: writing is clean, or the guard chose not to act (fail-open)
    exit 2: BLOCK -- stderr carries the list of fixes back to Claude
    stderr: the findings, or a free-form diagnostic

Loop safety (important -- a Stop hook that always blocks wedges the session):
    - honours stop_hook_active: never blocks twice in a row
    - remembers the fingerprint of the message it last blocked, per session,
      and never blocks the same text twice
    - every unexpected error path returns 0, so a broken guard cannot wedge
      a session

Scope: only prose is checked. Fenced code, inline code, file paths, URLs,
dates, and version numbers are stripped out before any rule runs, because
those legitimately carry digits and short forms.

Bypass:
    CLAUDE_PLAIN_LANGUAGE_GUARD=off   -- disable for a session
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_HOOKS_DIR))

try:
    from _error_log import log_event  # type: ignore
except Exception:  # pragma: no cover - fail-soft import
    def log_event(*args, **kwargs):
        return

try:
    import _project_paths as pp  # type: ignore
    _PATHS_OK = True
except Exception:  # pragma: no cover - fail-soft import
    _PATHS_OK = False


# --------------------------------------------------------------------------
# configuration
# --------------------------------------------------------------------------

DEFAULT_RULES = {
    "max_sentence_words": 35,
    "max_em_dashes_per_sentence": 3,
    "max_findings_reported": 12,
    "short_forms": [
        "TDD", "DTO", "DI", "ORM", "EF", "API", "REST", "CRUD", "MVC", "SPA",
        "JWT", "RBAC", "CI", "CD", "PR", "UI", "UX", "DB", "CDN", "CORS",
        "LLM", "GPU", "VRAM", "LoRA", "QLoRA", "GGUF", "RAG", "JSONL",
        "IBKR", "TWS", "RTH", "OHLC", "PnL", "P&L", "ATR", "EMA", "SMA",
        "RSI", "VWAP", "CRLF", "LF", "WCAG", "OWASP", "PBKDF2", "SHA",
        "AAA", "N+1", "CD", "MCP", "SDK", "CLI", "IDE",
    ],
    "label_words": [
        "step", "phase", "item", "point", "option", "rule",
        "part", "section", "stage", "round", "attempt", "case",
    ],
}


def load_rules() -> dict:
    """Read the sidecar rules file, falling back to the built-in defaults."""
    rules = dict(DEFAULT_RULES)
    if not _PATHS_OK:
        return rules
    try:
        path = pp.hook_file("plain-language-guard.rules.json")
        if path.is_file():
            with path.open(encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                rules.update(loaded)
    except Exception as exc:
        log_event(hook="plain-language-guard", event="rules-load-failed",
                  details={"error": str(exc)})
    return rules


def is_disabled() -> bool:
    return os.environ.get("CLAUDE_PLAIN_LANGUAGE_GUARD", "").lower() in {
        "off", "0", "false", "no"
    }


# --------------------------------------------------------------------------
# transcript reading
# --------------------------------------------------------------------------

def read_last_turn_prose(transcript_path: str) -> str:
    """Return every text block Claude wrote since the last real user message.

    Tool results arrive as ``user`` entries too, so a real user message is
    identified by carrying a text block of its own. Sub-agent entries
    (``isSidechain``) are skipped -- this guard judges what Leonardo reads,
    not what a sub-agent said to its caller.
    """
    path = Path(transcript_path)
    if not path.is_file():
        return ""

    try:
        raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""

    collected: list[str] = []
    for line in reversed(raw_lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if not isinstance(entry, dict) or entry.get("isSidechain"):
            continue

        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        blocks = content if isinstance(content, list) else []
        texts = [
            block.get("text", "")
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "text"
        ]

        role = message.get("role") or entry.get("type")
        if role == "user":
            if texts or isinstance(content, str):
                break          # a real user prompt -- the turn starts here
            continue           # tool result -- keep walking back
        if role == "assistant":
            collected.extend(reversed(texts))

    collected.reverse()
    return "\n\n".join(t for t in collected if t.strip())


# --------------------------------------------------------------------------
# prose normalisation -- strip everything that legitimately carries digits
# --------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
# A path-like token must contain a letter and a separator, so a pure "24/42"
# ratio is never mistaken for a path and stripped.
_PATH_RE = re.compile(r"\S*[A-Za-z_~]\S*[/\\]\S+")
_DATE_RE = re.compile(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b")
_VERSION_RE = re.compile(r"\bv?\d+\.\d+(?:\.\d+)*\b")
_HEX_RE = re.compile(r"\b[0-9a-f]{7,40}\b")
_ISSUE_RE = re.compile(r"#\d+")


def strip_non_prose(text: str) -> str:
    """Remove the spans where digits and short forms are legitimate."""
    text = _FENCE_RE.sub(" ", text)
    text = _INLINE_CODE_RE.sub(" ", text)
    text = _MD_LINK_RE.sub(r"\1", text)
    text = _URL_RE.sub(" ", text)
    text = _PATH_RE.sub(" ", text)
    text = _DATE_RE.sub(" ", text)
    text = _VERSION_RE.sub(" ", text)
    text = _HEX_RE.sub(" ", text)
    text = _ISSUE_RE.sub(" ", text)
    return text


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def sentences(prose: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(prose) if s.strip()]


def snippet(sentence: str, width: int = 90) -> str:
    flat = " ".join(sentence.split())
    return flat if len(flat) <= width else flat[: width - 1] + "…"


# --------------------------------------------------------------------------
# the four rules
# --------------------------------------------------------------------------

def check_short_forms(prose: str, rules: dict) -> list[str]:
    """A listed short form must appear expanded as 'full words (SHORT)'."""
    findings = []
    for short in rules.get("short_forms", []):
        if not short:
            continue
        token = re.compile(r"(?<![A-Za-z0-9])" + re.escape(short) + r"(?![A-Za-z0-9])")
        if not token.search(prose):
            continue
        expanded = re.compile(r"\(\s*" + re.escape(short) + r"\s*\)")
        if expanded.search(prose):
            continue
        findings.append(
            "Short form \"%s\" is used but never written out. "
            "Write the full words first, then \"(%s)\" in brackets." % (short, short)
        )
    return findings


_RATIO_RE = re.compile(r"(?<![\w/.])\d+\s*/\s*\d+(?![\w/])")
_N_OF_M_RE = re.compile(r"(?<![\w/.])\d+\s+of\s+\d+(?![\w])", re.IGNORECASE)
# One or two digits only: a three-digit number in brackets is nearly always
# a web status code such as (404), which is a name, not a lazy label.
_LONE_PAREN_NUMBER_RE = re.compile(r"\(\s*\d{1,2}\s*\)")


def check_bare_numbers(prose: str, rules: dict) -> list[str]:
    findings = []

    for match in _RATIO_RE.finditer(prose):
        findings.append(
            "Bare count ratio \"%s\" -- say what each number counts, "
            "for example \"three of the fourteen tests failed\"." % match.group(0).strip()
        )

    for match in _N_OF_M_RE.finditer(prose):
        findings.append(
            "Bare \"%s\" -- name the things being counted, "
            "not just the two numbers." % " ".join(match.group(0).split())
        )

    for match in _LONE_PAREN_NUMBER_RE.finditer(prose):
        findings.append(
            "Naked number \"%s\" in brackets -- replace it with a name for "
            "the thing it points at." % match.group(0)
        )

    label_words = rules.get("label_words", [])
    if label_words:
        label_re = re.compile(
            r"\b(" + "|".join(re.escape(w) for w in label_words) + r")\s+\d+\b",
            re.IGNORECASE,
        )
        for match in label_re.finditer(prose):
            findings.append(
                "Numbered label \"%s\" -- name it instead, "
                "for example \"the migration step\"." % " ".join(match.group(0).split())
            )

    return findings


def check_sentence_length(prose: str, rules: dict) -> list[str]:
    limit = int(rules.get("max_sentence_words", 35))
    findings = []
    for sentence in sentences(prose):
        words = sentence.split()
        if len(words) > limit:
            findings.append(
                "Sentence runs to %d words, over the limit of %d. Split it into "
                "one idea per sentence: \"%s\"" % (len(words), limit, snippet(sentence))
            )
    return findings


def check_stacked_dashes(prose: str, rules: dict) -> list[str]:
    limit = int(rules.get("max_em_dashes_per_sentence", 3))
    findings = []
    for sentence in sentences(prose):
        if sentence.count("—") >= limit:
            findings.append(
                "Sentence stacks %d long dashes, which nests clauses inside "
                "clauses. Split it: \"%s\"" % (sentence.count("—"), snippet(sentence))
            )
    return findings


def evaluate(prose: str, rules: dict) -> list[str]:
    findings: list[str] = []
    findings.extend(check_short_forms(prose, rules))
    findings.extend(check_bare_numbers(prose, rules))
    findings.extend(check_sentence_length(prose, rules))
    findings.extend(check_stacked_dashes(prose, rules))

    # Keep the order stable and drop duplicates without losing first-seen order.
    seen = set()
    unique = []
    for finding in findings:
        if finding in seen:
            continue
        seen.add(finding)
        unique.append(finding)
    return unique


# --------------------------------------------------------------------------
# per-session memory of what was already blocked
# --------------------------------------------------------------------------

def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:32]


def state_file(session_id: str) -> Path | None:
    if not _PATHS_OK:
        return None
    try:
        directory = pp.state_dir()
        directory.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "unknown")
        return directory / ("plain-language-guard-%s.json" % safe)
    except Exception:
        return None


def already_blocked(path: Path | None, mark: str) -> bool:
    if path is None or not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return mark in (data.get("blocked") or [])
    except Exception:
        return False


def remember_block(path: Path | None, mark: str) -> None:
    if path is None:
        return
    try:
        data = {"blocked": []}
        if path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("blocked"), list):
                data = loaded
        data["blocked"] = (data["blocked"] + [mark])[-40:]
        path.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        return


def write_log(findings: list[str], blocked: bool) -> None:
    if not _PATHS_OK:
        return
    try:
        directory = pp.logs_dir()
        directory.mkdir(parents=True, exist_ok=True)
        log = directory / "plain-language-guard.log"
        with log.open("a", encoding="utf-8") as handle:
            handle.write("%s findings=%d\n" % (
                "BLOCK" if blocked else "warn-only", len(findings)))
            for finding in findings:
                handle.write("    - %s\n" % finding)
    except Exception:
        return


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

BLOCK_HEADER = (
    "Your message breaks the plain-language writing rule that Leonardo has "
    "asked for twice. Rewrite the message you just wrote, fixing every point "
    "below, then say it again. Do not apologise and do not explain the rule "
    "back to him -- just deliver the corrected message.\n"
)

BLOCK_FOOTER = (
    "\nThe rule in full: use a name instead of a bare number; write short "
    "forms out in words the first time with the short form in brackets after "
    "it; keep one idea per sentence; and write questions so a person who did "
    "not watch the work can answer them.\n"
    "Turn this guard off for a session with CLAUDE_PLAIN_LANGUAGE_GUARD=off."
)


def run() -> int:
    if is_disabled():
        return 0

    try:
        raw = sys.stdin.read()
    except Exception:
        return 0

    try:
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    # Never block twice in a row -- that is how a Stop hook wedges a session.
    if payload.get("stop_hook_active"):
        return 0

    transcript_path = payload.get("transcript_path") or ""
    if not transcript_path:
        return 0

    try:
        prose = read_last_turn_prose(transcript_path)
    except Exception as exc:
        log_event(hook="plain-language-guard", event="transcript-read-failed",
                  details={"error": str(exc)})
        return 0

    if not prose.strip():
        return 0

    rules = load_rules()

    try:
        cleaned = strip_non_prose(prose)
        findings = evaluate(cleaned, rules)
    except Exception as exc:
        log_event(hook="plain-language-guard", event="evaluate-failed",
                  details={"error": str(exc)})
        return 0

    if not findings:
        return 0

    mark = fingerprint(prose)
    path = state_file(payload.get("session_id") or "")
    if already_blocked(path, mark):
        write_log(findings, blocked=False)
        return 0

    remember_block(path, mark)
    write_log(findings, blocked=True)

    cap = int(rules.get("max_findings_reported", 12))
    shown = findings[:cap]
    extra = len(findings) - len(shown)

    lines = [BLOCK_HEADER]
    for finding in shown:
        lines.append("  - %s" % finding)
    if extra > 0:
        lines.append("  - and %d more of the same kind." % extra)
    lines.append(BLOCK_FOOTER)

    sys.stderr.write("\n".join(lines) + "\n")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception as exc:  # pragma: no cover - last-resort fail-open
        log_event(hook="plain-language-guard", event="crashed",
                  details={"error": str(exc)})
        sys.exit(0)
