"""Pin W10: every repository path cited in the shipped design documents exists.

Contract: .claude/concepts/2026-10-30-angular-tailwind-followups.md, sub-task t2 (ledger row W10,
disposition already-resolved). The shipped design documents are the two design skills and their
reference files. (The designer agent file is not a design document: it cites .claude/AGENT_STANDARDS.md,
.claude/HANDOFF_SCHEMA.md and ../AGENT_PROTOCOL.md, which this repository does not hold. That is a
separate matter, outside W10.) A path they cite must resolve, or the reader is sent to a file that
is not there.

What is a cited path: a backticked token or a markdown link target that holds a "/" and looks like a
file (ends in .md, .py or .json) or starts with ".claude/", "skills/" or "agents/". A token with a
placeholder, a wildcard or a variable ("<", ">", "*", "$", "{") is not a path.

Excluded BY NAME (the only exclusions):
  * INSTALL_TIME: files the consuming project holds, not the plugin repository
    (".claude/project-profile.md" is the project's own profile; the plugin ships only a template).
  * REMOVAL_NOTE: any token starting "~/" or naming "ui-ux-pro-max" is the removal note at
    skills/website-design/references/foundation.md:47, which says that directory never existed.

A path resolves when it exists against the repository root, the citing document's folder, or a
skill folder (a skill cites a sibling skill's "references/..." by the short form).

Run: py -3 .claude/scripts/tests/test_design_document_paths.py
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

SHIPPED_DESIGN_DOCUMENTS = [
    "skills/website-design/SKILL.md",
    "skills/website-design/references/foundation.md",
    "skills/application-design/SKILL.md",
    "skills/application-design/references/application-patterns.md",
]

INSTALL_TIME = {".claude/project-profile.md"}
REMOVAL_NOTE_MARKERS = ("~/", "ui-ux-pro-max")

BACKTICK = re.compile(r"`([^`\s]+)`")
LINK = re.compile(r"\]\(([^)\s]+)\)")
PLACEHOLDER = re.compile(r"[<>*${}]")


def cited_paths(text: str) -> list[str]:
    out: list[str] = []
    for token in BACKTICK.findall(text) + LINK.findall(text):
        token = token.strip().rstrip(".,;:")
        if "://" in token or PLACEHOLDER.search(token) or "/" not in token:
            continue
        if not (token.endswith((".md", ".py", ".json")) or token.startswith((".claude/", "skills/", "agents/"))):
            continue
        out.append(token)
    return out


def is_excluded(token: str) -> bool:
    normal = token[2:] if token.startswith("./") else token
    return normal in INSTALL_TIME or any(m in token for m in REMOVAL_NOTE_MARKERS)


def resolves(token: str, document: Path) -> bool:
    bases = [REPO_ROOT, document.parent] + sorted((REPO_ROOT / "skills").glob("*"))
    return any((base / token).exists() for base in bases)


def missing_paths(relative_document: str, text: str | None = None) -> tuple[list[str], int]:
    document = REPO_ROOT / relative_document
    body = document.read_text(encoding="utf-8") if text is None else text
    checked, missing = 0, []
    for token in cited_paths(body):
        if is_excluded(token):
            continue
        checked += 1
        if not resolves(token, document):
            missing.append(token)
    return missing, checked


class DesignDocumentPathsTests(unittest.TestCase):
    def test_every_shipped_design_document_exists(self):
        for rel in SHIPPED_DESIGN_DOCUMENTS:
            self.assertTrue((REPO_ROOT / rel).is_file(), f"W10: the shipped design document {rel} is missing")

    def test_every_cited_repository_path_exists(self):
        total = 0
        for rel in SHIPPED_DESIGN_DOCUMENTS:
            missing, checked = missing_paths(rel)
            total += checked
            self.assertEqual(missing, [], f"W10: {rel} cites repository paths that do not exist: {missing}")
        self.assertGreaterEqual(total, 5, "W10: the extractor found too few paths; it is not looking at the documents")

    def test_the_extractor_finds_the_known_sibling_skill_citation(self):
        text = (REPO_ROOT / "skills/application-design/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("../website-design/references/foundation.md", cited_paths(text))

    def test_control_a_planted_missing_path_is_reported(self):
        planted = "See `skills/website-design/references/does-not-exist.md` for more."
        missing, checked = missing_paths("skills/website-design/SKILL.md", text=planted)
        self.assertEqual(checked, 1)
        self.assertEqual(missing, ["skills/website-design/references/does-not-exist.md"])

    def test_control_exclusions_are_by_name_only(self):
        self.assertTrue(is_excluded(".claude/project-profile.md"))
        self.assertTrue(is_excluded("~/.claude/references/ui-ux-pro-max/"))
        self.assertFalse(is_excluded("skills/website-design/references/missing.md"))
        self.assertFalse(is_excluded(".claude/registries/JOURNAL.md"))


if __name__ == "__main__":
    unittest.main()
