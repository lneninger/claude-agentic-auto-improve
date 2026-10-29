#!/usr/bin/env python3
"""test_angular_rule_coverage.py -- drift test for the angular-tailwind rule documents.

Contract: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md (sub-task 2: Coverage row, Rule document
set, Rule ID). Brief: .claude/work-items/2026-10-28-88-t2-coverage-test.md.

WHAT IS PINNED
--------------
The old prompt hook (``angular-tailwind-advisor.py``) printed a rule block (REMINDER) and a layout nudge
(DESIGN_NUDGE). The hook is disabled now; its rules live in four shipped documents. This test fails when a
rule the hook printed is no longer in the documents:

  * COVERAGE_ROWS is companion 2's coverage map of issue #84, verbatim, as data. Each row names the catalogue
    Rule IDs that must cover the printed rule and the literal fragments that must appear in those rules. A row
    with a ``printed`` phrase is also checked against the hook's own text (read with ``ast``, never imported),
    so a row cannot drift away from what the hook printed;
  * every catalogue ID (A-001..A-027, M-001..M-016 without 008 and 010, T-001..T-025 without 024: 65 rules)
    appears exactly once as a ``### <ID> -- <title>`` heading across the four documents, in its own document;
  * the P series ids are unique and none is a catalogue id;
  * every document opens with its boundary paragraph and the precedence paragraph, word for word;
  * no document carries a project token (the positive control plants a made-up name and expects it found);
  * positive controls: delete one rule from a temporary copy and the failure names that rule.

No row is skipped: rows run under subTest, and a guard test pins the row count and shape.
"""

from __future__ import annotations

import ast
import re
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ADDON = ROOT / ".claude" / "addons" / "angular-tailwind"
DOCS_DIR = ADDON / "documents"
ADVISOR = ADDON / "hooks" / "angular-tailwind-advisor.py"

ANGULAR = "ANGULAR_CODE_RULES.md"
MATERIAL = "ANGULAR_MATERIAL_RULES.md"
TAILWIND = "TAILWINDCSS_RULES.md"
PATTERNS = "UI-UX-PATTERNS.md"
DOCUMENT_NAMES = (ANGULAR, MATERIAL, TAILWIND, PATTERNS)

# ---------------------------------------------------------------------------------------------------------
# The catalogue (issue #84, companion 1): 65 ids, each in exactly one document.
# ---------------------------------------------------------------------------------------------------------
CATALOGUE_IDS: dict[str, str] = {}
for _n in range(1, 28):
    CATALOGUE_IDS["A-%03d" % _n] = PATTERNS if _n == 25 else ANGULAR
for _n in (1, 2, 3, 4, 5, 6, 7, 9, 11, 12, 13, 14, 15, 16):
    CATALOGUE_IDS["M-%03d" % _n] = MATERIAL
for _n in list(range(1, 24)) + [25]:
    CATALOGUE_IDS["T-%03d" % _n] = TAILWIND

# ---------------------------------------------------------------------------------------------------------
# The boundary paragraph of each document and the precedence paragraph, word for word.
# ---------------------------------------------------------------------------------------------------------
BOUNDARY = {
    ANGULAR: (
        "**What it holds, and what it does not.** This document holds the Angular code rules: components, "
        "templates, signals, state services, subscriptions and accessibility (rules `A-001` to `A-027`, except "
        "`A-025`). It does not hold the rules for Angular Material; those are in `ANGULAR_MATERIAL_RULES.md`. It "
        "does not hold the rules for Tailwind CSS and styling; those are in `TAILWINDCSS_RULES.md`. It does not "
        "hold `A-025` (loading, error and empty states, with their markup) or the patterns of the `P` series; "
        "those are in `UI-UX-PATTERNS.md`."
    ),
    MATERIAL: (
        "**What it holds, and what it does not.** This document holds the Angular Material rules: how to import, "
        "style and fix the Material components (rules `M-001` to `M-016`). It does not hold the Angular code "
        "rules; those are in `ANGULAR_CODE_RULES.md`. It does not hold the rules for Tailwind CSS and styling in "
        "general; those are in `TAILWINDCSS_RULES.md`. It does not hold the states and error-banner patterns; "
        "those are in `UI-UX-PATTERNS.md`."
    ),
    TAILWIND: (
        "**What it holds, and what it does not.** This document holds the Tailwind CSS and styling rules (rules "
        "`T-001` to `T-025`): inline styles, colour tokens, component stylesheets, scroll containers, numbers and "
        "responsive layout. It also holds the scroll container pattern, with its snippet and install step. It "
        "does not hold the Angular code rules; those are in `ANGULAR_CODE_RULES.md`. It does not hold the rules "
        "for Angular Material components; those are in `ANGULAR_MATERIAL_RULES.md`. It does not hold the states "
        "pattern or the error banner; those are in `UI-UX-PATTERNS.md`."
    ),
    PATTERNS: (
        "**What it holds, and what it does not.** This document holds the generic patterns that need markup: the "
        "loading, error and empty states of a view (`A-025`), and the error banner (`P-001`). It does not hold "
        "the Angular code rules; those are in `ANGULAR_CODE_RULES.md`. It does not hold the rules for Angular "
        "Material components; those are in `ANGULAR_MATERIAL_RULES.md`. It does not hold the rules for Tailwind "
        "CSS and styling, or the scroll container pattern; those are in `TAILWINDCSS_RULES.md`. Its name differs "
        "from a project's own design document on purpose, so the two never collide."
    ),
}
PRECEDENCE = (
    "**Which rule wins.** The project's own instructions win over every rule document. A document the project "
    "wrote and lists in `review.documents` wins over this plugin document where they disagree. For what it "
    "checks, the guard's verdict is final."
)

# Tokens that belong to one real project and must never appear in a shipped document.
PROJECT_TOKENS = ("isSuccess", "/api/screeners", "screeners")
MADE_UP_TOKEN = "zorblax-ledger"  # positive control only; no real project uses this name

# ---------------------------------------------------------------------------------------------------------
# Companion 2's coverage map, verbatim, as data.
#   printed   -- (constant, phrase) the hook printed; the phrase must sit inside that constant (or None)
#   ids       -- catalogue ids that must cover it; each id must exist, the fragments are searched in their text
#   fragments -- literal fragments that must appear in the text of the ids above
#   enforced  -- id -> "blocks" | "warns": the "Enforced by" line of that rule
#   anywhere  -- literal fragments that must appear somewhere in the document set
# ---------------------------------------------------------------------------------------------------------
COVERAGE_ROWS = [
    {
        "name": "ZERO static style attributes",
        "printed": ("REMINDER", 'ZERO static style="..." attributes allowed'),
        "ids": ["T-001"],
        "fragments": ['ZERO static style="..." attributes allowed'],
    },
    {
        "name": "Every static property is a Tailwind utility from the theme bridge",
        "printed": ("REMINDER", "Every static property must be a Tailwind utility from the @theme bridge"),
        "ids": ["T-001", "T-002", "T-005"],
        "fragments": [
            "Every static property must be a Tailwind utility from the @theme bridge",
            "var(--mat-sys-*)",
            "@theme",
        ],
    },
    {
        "name": "Dynamic [style.prop] bindings are allowed",
        "printed": ("REMINDER", 'Dynamic [style.prop]="expr()" bindings ARE allowed for runtime-computed values'),
        "ids": ["T-008"],
        "fragments": ["[style.prop]", "[style]", "[attr.style]", "computed at run time"],
    },
    {
        "name": "Component stylesheets near-empty, with the allowed content list",
        "printed": ("REMINDER", "near-empty. Only allowed content is third-party overrides"),
        "ids": ["T-010"],
        "fragments": ["near-empty", "third-party overrides", "@keyframes", "@media", "@supports", "@apply"],
    },
    {
        "name": ":host ::ng-deep, dead :host under ViewEncapsulation.None, scope under the element selector",
        "printed": ("REMINDER", ":host matches nothing, so scope them under the component's element selector"),
        "ids": ["T-011"],
        "fragments": [
            ":host ::ng-deep",
            "ViewEncapsulation.None",
            ":host matches nothing",
            "scope them under the component's element selector",
            "my-widget .vendor-class",
        ],
    },
    {
        "name": "Raw property rules belong in the template as Tailwind classes",
        "printed": ("REMINDER", "Raw property rules belong in the template as Tailwind classes"),
        "ids": ["T-010"],
        "fragments": ["Raw property rules belong in the template as Tailwind classes"],
    },
    {
        "name": "Gray utilities banned, with replacements",
        "printed": ("REMINDER", "Banned: text-gray-*, bg-gray-*, border-gray-*"),
        "ids": ["T-003"],
        "fragments": [
            "text-gray-*", "bg-gray-*", "border-gray-*",
            "text-on-surface-variant", "bg-surface-variant", "border-outline-variant",
        ],
    },
    {
        "name": "Hard-coded hex colours banned in templates",
        "printed": ("REMINDER", "Banned: hardcoded hex colors in templates"),
        "ids": ["T-004"],
        "fragments": [
            "hardcoded hex colors in templates", "Material token utilities",
            "text-primary", "bg-surface-container", "border-outline-variant",
        ],
    },
    {
        "name": "Inline template: and styles: banned",
        "printed": ("REMINDER", "Banned: inline template: / styles: in @Component() decorators"),
        "ids": ["A-003"],
        "fragments": [
            "template:", "styles:", "@Component()", "templateUrl", "styleUrl",
            ".component.html", ".component.scss",
        ],
    },
    {
        "name": "Inline overflow-y-auto and sticky top-0 banned; use the scroll-edge classes",
        "printed": ("REMINDER", "Banned: inline overflow-y-auto / sticky top-0 for scroll containers"),
        "ids": ["T-012", "T-013", "T-014"],
        "fragments": [
            "overflow-y-auto", "sticky top-0",
            "scroll-edge", "scroll-edge-content", "scroll-edge-header",
            "h-full min-h-0",
        ],
    },
    {
        "name": "The guard blocks templates and decorators and only warns on stylesheets",
        "printed": ("REMINDER", "blocks template and decorator violations and only warns on stylesheets"),
        "ids": ["T-001", "T-003", "T-004", "A-003", "T-010", "T-012"],
        "fragments": [],
        "enforced": {
            "T-001": "blocks", "T-003": "blocks", "T-004": "blocks",
            "A-003": "blocks", "T-010": "warns", "T-012": "blocks",
        },
        "anywhere": [
            "blocks template and decorator violations and only warns on stylesheets",
            "Get it right the first time",
        ],
    },
    {
        "name": "Reference documents list",
        "printed": None,
        "ids": [],
        "fragments": [],
        "anywhere": ["review.documents"],
    },
    {
        "name": "Per-app appendix",
        "printed": None,
        "ids": ["T-015", "T-021", "T-022"],
        "fragments": ["advisorRemindersAppendix", ".app-rules.json", "unlayered", "frontend.theme-polarity"],
    },
    {
        "name": "Layout nudge",
        "printed": ("DESIGN_NUDGE", "agentic-auto-improve:application-design"),
        "ids": [],
        "fragments": [],
        "anywhere": [
            "agentic-auto-improve:application-design",
            "agentic-auto-improve:website-design",
            "advisory",
        ],
    },
]

HEADING_RX = re.compile(r"^### ([AMTP]-\d{3}) — ", re.MULTILINE)


# ---------------------------------------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------------------------------------
def norm(text: str) -> str:
    """Fold every run of whitespace to one space, so a wrapped line compares equal to an unwrapped one."""
    return " ".join(text.split())


def read_advisor_constants(path: Path) -> dict[str, str]:
    """Read REMINDER and DESIGN_NUDGE from the advisor script with ast. The script is never imported."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("REMINDER", "DESIGN_NUDGE"):
                    found[target.id] = ast.literal_eval(node.value)
    return found


def load_documents(folder: Path) -> dict[str, str]:
    docs: dict[str, str] = {}
    for name in DOCUMENT_NAMES:
        p = folder / name
        docs[name] = p.read_text(encoding="utf-8").replace("\r\n", "\n") if p.exists() else ""
    return docs


def split_sections(text: str) -> list[tuple[str, str]]:
    """Return (rule id, section text) for every rule heading. A section ends at the next heading of level 1-3."""
    lines = text.split("\n")
    out: list[tuple[str, str]] = []
    current_id: str | None = None
    buf: list[str] = []
    for line in lines:
        is_boundary = line.startswith(("# ", "## ", "### "))
        if is_boundary:
            if current_id is not None:
                out.append((current_id, "\n".join(buf)))
            m = HEADING_RX.match(line)
            current_id = m.group(1) if m else None
            buf = [line] if m else []
        elif current_id is not None:
            buf.append(line)
    if current_id is not None:
        out.append((current_id, "\n".join(buf)))
    return out


def index_rules(docs: dict[str, str]) -> dict[str, list[tuple[str, str]]]:
    """rule id -> list of (document name, section text); a list longer than one is a duplicate."""
    index: dict[str, list[tuple[str, str]]] = {}
    for name, text in docs.items():
        for rule_id, section in split_sections(text):
            index.setdefault(rule_id, []).append((name, section))
    return index


def remove_rule(text: str, rule_id: str) -> str:
    """Return text without the section of one rule (heading to the next heading). Used by the controls."""
    for found_id, section in split_sections(text):
        if found_id == rule_id:
            return text.replace(section, "", 1)
    return text


# ---------------------------------------------------------------------------------------------------------
# Checks. Each returns a list of problem strings; an empty list means the check passed.
# ---------------------------------------------------------------------------------------------------------
def catalogue_problems(docs: dict[str, str]) -> list[str]:
    problems: list[str] = []
    index = index_rules(docs)
    for rule_id, home in CATALOGUE_IDS.items():
        where = [name for name, _ in index.get(rule_id, [])]
        if not where:
            problems.append("%s: no heading in any document (expected one in %s)" % (rule_id, home))
        elif len(where) > 1:
            problems.append("%s: appears %d times (%s); expected exactly once" % (rule_id, len(where), ", ".join(where)))
        elif where[0] != home:
            problems.append("%s: found in %s, expected in %s" % (rule_id, where[0], home))
    for rule_id in index:
        if rule_id not in CATALOGUE_IDS and not rule_id.startswith("P-"):
            problems.append("%s: a heading outside the catalogue and outside the P series" % rule_id)
    return problems


def p_series_problems(docs: dict[str, str]) -> list[str]:
    problems: list[str] = []
    index = index_rules(docs)
    p_ids = sorted(i for i in index if i.startswith("P-"))
    if not p_ids:
        problems.append("P series: no P rule heading found (P-001 is expected)")
    for rule_id in p_ids:
        if len(index[rule_id]) > 1:
            problems.append("%s: the P id is not unique (%d headings)" % (rule_id, len(index[rule_id])))
        if rule_id in CATALOGUE_IDS:
            problems.append("%s: a P id equals a catalogue id" % rule_id)
    return problems


def _union_text(index: dict[str, list[tuple[str, str]]], ids: list[str]) -> str:
    return norm(" ".join(section for i in ids for _, section in index.get(i, [])))


def row_problems(row: dict, docs: dict[str, str], constants: dict[str, str]) -> list[str]:
    """Problems of one coverage row. Every message starts with the row name and names the missing rule."""
    problems: list[str] = []
    label = "row %r" % row["name"]
    index = index_rules(docs)
    everything = norm(" ".join(docs.values()))

    printed = row.get("printed")
    if printed is not None:
        const, phrase = printed
        if const not in constants:
            problems.append("%s: the advisor script has no %s" % (label, const))
        elif norm(phrase) not in norm(constants[const]):
            problems.append("%s: the phrase %r is not in the hook's %s" % (label, phrase, const))

    for rule_id in row["ids"]:
        if rule_id not in index:
            problems.append("%s: rule %s is missing from the documents" % (label, rule_id))
    present = [i for i in row["ids"] if i in index]
    union = _union_text(index, present)
    for fragment in row["fragments"]:
        if norm(fragment) not in union:
            problems.append("%s: fragment %r is not in %s" % (label, fragment, "/".join(row["ids"])))
    for rule_id, level in row.get("enforced", {}).items():
        sections = [s for _, s in index.get(rule_id, [])]
        if not sections:
            continue  # already reported as missing above
        marker = "Enforced by: guard %s" % level
        if not any(marker in s for s in sections):
            problems.append("%s: rule %s does not say %r" % (label, rule_id, marker))
    for fragment in row.get("anywhere", []):
        if norm(fragment) not in everything:
            problems.append("%s: fragment %r is in no document" % (label, fragment))
    return problems


def nudge_problems(docs: dict[str, str], constants: dict[str, str]) -> list[str]:
    """Every skill the hook's layout nudge names must be named in the documents."""
    everything = norm(" ".join(docs.values()))
    names = sorted(set(re.findall(r"agentic-auto-improve:[a-z-]+", constants.get("DESIGN_NUDGE", ""))))
    problems = ["DESIGN_NUDGE names no skill (the parse found nothing)"] if not names else []
    for skill in names:
        if skill not in everything:
            problems.append("layout nudge: skill %s is in no document" % skill)
    return problems


def unclaimed_blocks(constants: dict[str, str]) -> list[str]:
    """REMINDER blocks (after the header) that no coverage row claims through its printed phrase."""
    blocks = [norm(b) for b in constants["REMINDER"].split("\n\n") if b.strip()][1:]
    phrases = [norm(r["printed"][1]) for r in COVERAGE_ROWS if r.get("printed") and r["printed"][0] == "REMINDER"]
    return [b for b in blocks if not any(p in b for p in phrases)]


def paragraph_problems(docs: dict[str, str]) -> list[str]:
    problems: list[str] = []
    for name in DOCUMENT_NAMES:
        paragraphs = [p.strip() for p in docs[name].split("\n\n")]
        if BOUNDARY[name] not in paragraphs:
            problems.append("%s: the boundary paragraph is missing or changed" % name)
        if PRECEDENCE not in paragraphs:
            problems.append("%s: the precedence paragraph is missing or changed" % name)
        if BOUNDARY[name] in paragraphs and PRECEDENCE in paragraphs:
            if paragraphs.index(PRECEDENCE) != paragraphs.index(BOUNDARY[name]) + 1:
                problems.append("%s: the precedence paragraph does not follow the boundary paragraph" % name)
    return problems


def token_problems(docs: dict[str, str], tokens: tuple[str, ...]) -> list[str]:
    problems: list[str] = []
    for name, text in docs.items():
        for token in tokens:
            if token.lower() in text.lower():
                problems.append("%s: contains the project token %r" % (name, token))
    return problems


# ---------------------------------------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------------------------------------
class RuleDocumentCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.docs = load_documents(DOCS_DIR)
        cls.constants = read_advisor_constants(ADVISOR)

    def test_inputs_exist(self) -> None:
        for name in DOCUMENT_NAMES:
            self.assertTrue((DOCS_DIR / name).is_file(), "document %s is missing under %s" % (name, DOCS_DIR))
        self.assertIn("REMINDER", self.constants, "REMINDER not found in the advisor script")
        self.assertIn("DESIGN_NUDGE", self.constants, "DESIGN_NUDGE not found in the advisor script")
        self.assertEqual(len(CATALOGUE_IDS), 65, "the catalogue holds 65 rules (issue #84 companion 1)")

    def test_advisor_is_read_with_ast_and_never_imported(self) -> None:
        source = Path(__file__).read_text(encoding="utf-8")
        code_lines = [ln for ln in source.splitlines() if ln.lstrip().startswith(("import ", "from "))]
        self.assertFalse(
            any("advisor" in ln for ln in code_lines),
            "the advisor script must be read with ast, not imported",
        )

    def test_coverage_rows_have_the_map_shape_and_none_is_empty(self) -> None:
        self.assertEqual(len(COVERAGE_ROWS), 14, "companion 2's coverage map has 14 rows")
        names = [r["name"] for r in COVERAGE_ROWS]
        self.assertEqual(len(set(names)), len(names), "row names must be unique")
        for row in COVERAGE_ROWS:
            has_requirement = row["ids"] or row["fragments"] or row.get("anywhere")
            self.assertTrue(has_requirement, "row %r asserts nothing" % row["name"])
            for rule_id in row["ids"]:
                self.assertIn(rule_id, CATALOGUE_IDS, "row %r names an unknown id %s" % (row["name"], rule_id))

    def test_every_coverage_row_is_covered(self) -> None:
        for row in COVERAGE_ROWS:
            with self.subTest(row=row["name"]):
                problems = row_problems(row, self.docs, self.constants)
                self.assertEqual(problems, [], "coverage row failed:\n" + "\n".join(problems))

    def test_every_reminder_block_is_claimed_by_a_row(self) -> None:
        self.assertEqual(
            unclaimed_blocks(self.constants), [],
            "a block the hook printed is claimed by no coverage row",
        )

    def test_layout_nudge_skills_are_named_in_the_documents(self) -> None:
        self.assertEqual(nudge_problems(self.docs, self.constants), [])

    def test_every_catalogue_id_appears_once_in_its_document(self) -> None:
        problems = catalogue_problems(self.docs)
        self.assertEqual(problems, [], "catalogue problems:\n" + "\n".join(problems))

    def test_p_ids_are_unique_and_restate_no_catalogue_id(self) -> None:
        problems = p_series_problems(self.docs)
        self.assertEqual(problems, [], "P series problems:\n" + "\n".join(problems))

    def test_every_document_has_the_boundary_and_precedence_paragraphs(self) -> None:
        problems = paragraph_problems(self.docs)
        self.assertEqual(problems, [], "paragraph problems:\n" + "\n".join(problems))

    def test_no_document_carries_a_project_token(self) -> None:
        problems = token_problems(self.docs, PROJECT_TOKENS)
        self.assertEqual(problems, [], "project tokens found:\n" + "\n".join(problems))


class PositiveControlTests(unittest.TestCase):
    """Each control breaks a temporary copy of the documents and expects the failure to name the break."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="rule-coverage-control-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for name in DOCUMENT_NAMES:
            shutil.copyfile(DOCS_DIR / name, self.tmp / name)
        self.constants = read_advisor_constants(ADVISOR)

    def _edit(self, name: str, fn) -> dict[str, str]:
        path = self.tmp / name
        path.write_text(fn(path.read_text(encoding="utf-8").replace("\r\n", "\n")), encoding="utf-8")
        return load_documents(self.tmp)

    def test_the_untouched_copy_passes_every_check(self) -> None:
        docs = load_documents(self.tmp)
        self.assertEqual(catalogue_problems(docs), [])
        for row in COVERAGE_ROWS:
            self.assertEqual(row_problems(row, docs, self.constants), [], row["name"])

    def test_deleting_one_rule_fails_and_names_it(self) -> None:
        docs = self._edit(TAILWIND, lambda t: remove_rule(t, "T-003"))
        self.assertNotIn("T-003", index_rules(docs), "the control did not delete T-003")
        catalogue = catalogue_problems(docs)
        self.assertTrue(any(p.startswith("T-003") for p in catalogue), "catalogue check did not name T-003: %r" % catalogue)
        gray_row = next(r for r in COVERAGE_ROWS if r["ids"] == ["T-003"])
        row = row_problems(gray_row, docs, self.constants)
        self.assertTrue(any("T-003" in p for p in row), "the gray-utility row did not name T-003: %r" % row)

    def test_deleting_a_fragment_from_a_rule_fails_and_names_it(self) -> None:
        docs = self._edit(TAILWIND, lambda t: t.replace("scroll-edge-header", "REDACTED"))
        scroll_row = next(r for r in COVERAGE_ROWS if "T-012" in r["ids"])
        problems = row_problems(scroll_row, docs, self.constants)
        self.assertTrue(any("scroll-edge-header" in p for p in problems), "fragment loss not named: %r" % problems)

    def test_a_duplicated_rule_fails_and_names_it(self) -> None:
        heading = "### A-007 — Every @for has a track expression\n\nCopy.\n\n"
        docs = self._edit(MATERIAL, lambda t: t + "\n" + heading)
        problems = catalogue_problems(docs)
        self.assertTrue(any(p.startswith("A-007") and "2 times" in p for p in problems), repr(problems))

    def test_a_duplicated_p_id_fails_and_names_it(self) -> None:
        heading = "\n### P-001 — A second banner\n\nCopy.\n"
        docs = self._edit(PATTERNS, lambda t: t + heading)
        problems = p_series_problems(docs)
        self.assertTrue(any(p.startswith("P-001") for p in problems), repr(problems))

    def test_a_changed_paragraph_fails_and_names_the_document(self) -> None:
        docs = self._edit(MATERIAL, lambda t: t.replace("the guard's verdict is final", "the guard may be ignored"))
        problems = paragraph_problems(docs)
        self.assertTrue(any(p.startswith(MATERIAL) and "precedence" in p for p in problems), repr(problems))

    def test_a_planted_project_token_is_found(self) -> None:
        docs = self._edit(ANGULAR, lambda t: t + "\nCheck %s before reading the value.\n" % MADE_UP_TOKEN)
        problems = token_problems(docs, PROJECT_TOKENS + (MADE_UP_TOKEN,))
        self.assertTrue(
            any(p.startswith(ANGULAR) and MADE_UP_TOKEN in p for p in problems),
            "the made-up token was not found: %r" % problems,
        )
        self.assertEqual(token_problems(load_documents(DOCS_DIR), (MADE_UP_TOKEN,)), [], "the real documents must not hold it")


if __name__ == "__main__":
    unittest.main()
