#!/usr/bin/env python3
"""
Repository consistency scans (issue 80).

  (1) CI runs the guard tests AND can fail the build on them: the `tests` job of a workflow runs
      test_check_version_bump.py and test_repo_consistency.py, neither run line swallows its exit code
      (`|| true`, `; exit 0`, `continue-on-error`), neither the job nor the step is continue-on-error or
      `if: false`, the workflow triggers on pull_request, and the slow test_skill_script_lookup.py
      (3-4 minutes) is deliberately NOT listed.
  (2) The registry-append version-raise sentence is the same single line in the three flows that carry it,
      sitting in the right section of each, and the CLAUDE.md heading it cites exists.
  (3) Two different hook measures, each checked against its own oracle (they are equal today only by
      coincidence; one db-destructive-guard file is registered three times, so they can drift apart):
        (a) HOOK FILES: every "N hooks" / "N hook files" in the README and in the manifest `description`
            fields equals the number of `*.py` files directly in .claude/hooks/ whose name does not start
            with `_`, excluding gate-launch.py.
        (b) REGISTRATIONS: every "N registrations" in the README equals the number of command entries in
            .claude/hooks/hooks.json.
      A count directly after the word "retired" is a history figure, not a current count, and is skipped.
      No test asserts (a) == (b); each is compared only with its own oracle.

Every comparison lives in a helper that returns a list of violations. The real tests assert the list is empty;
each positive control feeds the SAME helper a broken fixture and asserts it is non-empty.

Run: py -3 .claude/scripts/tests/test_repo_consistency.py
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = PLUGIN_ROOT / ".github" / "workflows"

REQUIRED_TESTS = (
    ".claude/scripts/tests/test_check_version_bump.py",
    ".claude/scripts/tests/test_repo_consistency.py",
)
EXCLUDED_TEST = "test_skill_script_lookup.py"
CI_JOB = "tests"

CANONICAL = (
    "A registry append is a shipped change: batch it into a change that already raises the plugin "
    "version, or raise at least a patch version (see CLAUDE.md, \"Every change to shipped plugin "
    "files bumps the plugin version\")."
)
HEADING = "## Every change to shipped plugin files bumps the plugin version"
# file -> placement rule: ("heading", predicate on the heading line) or ("after", marker line, line window)
SENTENCE_PLACEMENT = {
    "agents/fullstack-code-reviewer.md": ("heading", lambda h: h.startswith("### Registry janitor duties")),
    "skills/journal-add/SKILL.md": ("heading", lambda h: h.startswith("#") and "Version raise" in h),
    "skills/design-first/SKILL.md": ("after", "- **Tags:** <2-5 grep-friendly keywords>", 12),
}

MANIFESTS = (
    "plugin.json",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".cursor-plugin/plugin.json",
)
# Surfaces that must state a hook count (so the scan is proven to have read one).
MANIFESTS_WITH_COUNT = (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json")

WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen twenty".split())}
_NUM = r"(\d+|" + "|".join(w for w in WORDS if w != "zero") + r")"
# <number> [up to three words] hooks | hook files. The noun is exact so "9 hook test suites" never matches.
# A gap word may not itself be a digit string or a spelled number, so the number taken is the one nearest the noun.
_GAP_WORD = r"(?!(?:\d|(?:" + "|".join(w for w in WORDS if w != "zero") + r")\b))\w+"
_COUNT_RE = re.compile(r"(?i)(?<![\w.])" + _NUM + r"[ \t]+(?:" + _GAP_WORD + r"[ \t]+){0,3}?(?:hooks|hook files)\b(?!/)")
# <number> registrations (measure b)
_REG_RE = re.compile(r"(?i)(?<![\w.])" + _NUM + r"\s+registrations\b")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- helpers: hook counts -------------------------------------------------------------------------------
def hook_command_count(config: dict) -> int:
    """Measure (b), registrations: number of command entries in hooks.json."""
    return sum(len(g.get("hooks", [])) for groups in config["hooks"].values() for g in groups)


def hook_file_count(hooks_dir: Path) -> int:
    """Measure (a), hook files: *.py files directly in hooks_dir, not starting with '_', minus gate-launch.py."""
    return sum(1 for p in hooks_dir.glob("*.py")
               if p.is_file() and not p.name.startswith("_") and p.name != "gate-launch.py")


def _counts(regex: re.Pattern, text: str) -> list[tuple[str, int]]:
    found = []
    for m in regex.finditer(text):
        if re.search(r"(?i)retired\s+$", text[max(0, m.start() - 12):m.start()]):
            continue
        tok = m.group(1).lower()
        found.append((re.sub(r"\s+", " ", m.group(0)), int(tok) if tok.isdigit() else WORDS[tok]))
    return found


def readme_counts(text: str) -> list[tuple[str, int]]:
    """(matched text, number) for each 'N hooks' / 'N hook files' count, skipping history counts after 'retired'."""
    return _counts(_COUNT_RE, text)


def registration_counts(text: str) -> list[tuple[str, int]]:
    """(matched text, number) for each 'N registrations' phrase."""
    return _counts(_REG_RE, text)


def stale_counts(text: str, expected_files: int) -> list[str]:
    """Violations of measure (a): 'N hooks' / 'N hook files' that differ from the hook-file count."""
    return [f"says '{t}' ({n}) but .claude/hooks/ has {expected_files} hook files"
            for t, n in readme_counts(text) if n != expected_files]


def stale_registrations(text: str, expected_entries: int) -> list[str]:
    """Violations of measure (b): 'N registrations' that differ from the hooks.json command-entry count."""
    return [f"says '{t}' ({n}) but hooks.json has {expected_entries} command entries"
            for t, n in registration_counts(text) if n != expected_entries]


def manifest_descriptions(data: dict) -> list[str]:
    out = [data["description"]] if isinstance(data.get("description"), str) else []
    for p in data.get("plugins", []) or []:
        if isinstance(p, dict) and isinstance(p.get("description"), str):
            out.append(p["description"])
    return out


HOOKS_DIR = PLUGIN_ROOT / ".claude" / "hooks"


def expected_hook_count() -> int:
    """Oracle for measure (a): hook files."""
    return hook_file_count(HOOKS_DIR)


def expected_registration_count() -> int:
    """Oracle for measure (b): hooks.json command entries."""
    return hook_command_count(json.loads(read(HOOKS_DIR / "hooks.json")))


# --- helpers: CI ----------------------------------------------------------------------------------------
def _code_lines(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]


def _indent(ln: str) -> int:
    return len(ln) - len(ln.lstrip())


def on_block(text: str) -> list[str]:
    lines, out, inside = _code_lines(text), [], False
    for ln in lines:
        if re.match(r"(?:on|\"on\"|'on'):", ln):
            inside = True
            out.append(ln)
        elif inside:
            if _indent(ln) == 0:
                break
            out.append(ln)
    return out


def job_block(text: str, job: str) -> list[str]:
    lines, out, inside = _code_lines(text), [], False
    for ln in lines:
        if re.match(rf"  {re.escape(job)}:\s*$", ln):
            inside = True
            out.append(ln)
        elif inside:
            if _indent(ln) <= 2:
                break
            out.append(ln)
    return out


_FALSE_IF = re.compile(r"^\s*(?:-\s*)?if:\s*['\"]?(?:false|\$\{\{\s*false\s*\}\})['\"]?\s*$", re.I)
_COE = re.compile(r"^\s*(?:-\s*)?continue-on-error:\s*['\"]?(?:true|\$\{\{\s*true\s*\}\})['\"]?\s*$", re.I)
_SWALLOW = re.compile(r"\|\|\s*(?:true|:|exit\s+0)\b|;\s*exit\s+0\b|continue-on-error", re.I)


def ci_violations(text: str, required=REQUIRED_TESTS, job: str = CI_JOB) -> list[str]:
    out: list[str] = []
    on = " ".join(on_block(text))
    if "pull_request" not in on:
        out.append("workflow `on:` does not include pull_request")
    block = job_block(text, job)
    if not block:
        return out + [f"no `{job}` job in the workflow"]
    for ln in block:
        if _indent(ln) == 4 and (_COE.match(ln) or _FALSE_IF.match(ln)):
            out.append(f"job `{job}` carries `{ln.strip()}`")
    # split the job's steps at lines that start a step ("- " at indent 6)
    steps: list[list[str]] = []
    for ln in block:
        if _indent(ln) == 6 and ln.lstrip().startswith("- "):
            steps.append([ln])
        elif steps:
            steps[-1].append(ln)
    for tf in required:
        homes = [s for s in steps if any(re.match(r"\s*(?:-\s*)?run:", ln) and tf in ln for ln in s)]
        if not homes:
            out.append(f"job `{job}` has no `run:` step for {tf}")
            continue
        for s in homes:
            run = next(ln for ln in s if re.match(r"\s*(?:-\s*)?run:", ln) and tf in ln)
            if not re.search(r"unittest|python", run):
                out.append(f"run line for {tf} does not run it with python/unittest")
            if _SWALLOW.search(run):
                out.append(f"run line for {tf} swallows its exit code: {run.strip()}")
            for ln in s:
                if _COE.match(ln) or _FALSE_IF.match(ln):
                    out.append(f"step running {tf} carries `{ln.strip()}`")
    return out


# --- helpers: sentence placement ------------------------------------------------------------------------
def _norm(ln: str) -> str:
    return re.sub(r"^(?:-|>)\s+", "", ln.strip())


def _heading_sections(text: str):
    """Yield (heading line, body lines) for each markdown heading outside code fences."""
    cur, body, fence = None, [], False
    for ln in text.splitlines():
        if ln.strip().startswith("```"):
            fence = not fence
        if not fence and re.match(r"#{1,6}\s", ln):
            if cur is not None:
                yield cur, body
            cur, body = ln.strip(), []
        elif cur is not None:
            body.append(ln)
    if cur is not None:
        yield cur, body


def sentence_violations(text: str, sentence: str, rule: tuple) -> list[str]:
    if rule[0] == "heading":
        pred = rule[1]
        bodies = [b for h, b in _heading_sections(text) if pred(h)]
        if not bodies:
            return ["the section heading the sentence belongs under is missing"]
        if not any(_norm(ln) == sentence for b in bodies for ln in b):
            return ["the version-raise sentence is not (as one line) under its required heading"]
        return []
    _, marker, window = rule
    lines = text.splitlines()
    idx = [i for i, ln in enumerate(lines) if ln.strip() == marker]
    if not idx:
        return [f"marker line {marker!r} is missing"]
    if not any(_norm(ln) == sentence for i in idx for ln in lines[i + 1:i + 1 + window]):
        return [f"the version-raise sentence is not within {window} lines after {marker!r}"]
    return []


# --- (1) CI runs the tests and can fail the build -------------------------------------------------------
_CLEAN_WF = """\
name: x
on:
  pull_request:
    branches: [master]
jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: a
        run: python3 .claude/scripts/tests/test_a.py
      - name: b
        run: python3 .claude/scripts/tests/test_b.py
"""


class CiRunsTests(unittest.TestCase):
    def _texts(self) -> list[str]:
        files = sorted(WORKFLOWS.glob("*.yml")) if WORKFLOWS.is_dir() else []
        self.assertTrue(files, "no workflow files read under .github/workflows/")
        return [read(f) for f in files]

    def test_tests_job_runs_required_files_and_can_fail_the_build(self):
        texts = self._texts()
        withjob = [t for t in texts if job_block(t, CI_JOB)]
        self.assertTrue(withjob, f"no workflow has a `{CI_JOB}` job")
        for t in withjob:
            self.assertEqual(ci_violations(t), [], "the CI tests job cannot reliably fail the build")

    def test_required_test_files_exist(self):
        for tf in REQUIRED_TESTS:
            with self.subTest(test_file=tf):
                self.assertTrue((PLUGIN_ROOT / tf).is_file(), f"{tf} does not exist")

    def test_workflow_does_not_list_slow_skill_script_lookup(self):
        for text in self._texts():
            self.assertNotIn(EXCLUDED_TEST, text, f"workflow lists {EXCLUDED_TEST} (3-4 minutes, excluded)")

    def test_control_clean_workflow_has_no_violations(self):
        self.assertEqual(ci_violations(_CLEAN_WF, ("test_a.py", "test_b.py")), [])

    def test_control_each_swallowing_pattern_is_reported(self):
        req = ("test_a.py", "test_b.py")
        cases = {
            "or true": _CLEAN_WF.replace("test_a.py\n", "test_a.py || true\n"),
            "exit 0": _CLEAN_WF.replace("test_b.py\n", "test_b.py; exit 0\n"),
            "step continue-on-error": _CLEAN_WF.replace(
                "      - name: a\n", "      - name: a\n        continue-on-error: true\n"),
            "step if false": _CLEAN_WF.replace("      - name: a\n", "      - name: a\n        if: false\n"),
            "job continue-on-error": _CLEAN_WF.replace(
                "    runs-on: ubuntu-latest\n", "    runs-on: ubuntu-latest\n    continue-on-error: true\n"),
            "job if false": _CLEAN_WF.replace(
                "    runs-on: ubuntu-latest\n", "    runs-on: ubuntu-latest\n    if: false\n"),
            "only workflow_dispatch": _CLEAN_WF.replace(
                "  pull_request:\n    branches: [master]\n", "  workflow_dispatch:\n"),
            "file not run": _CLEAN_WF.replace("test_b.py", "test_c.py"),
            "no tests job": _CLEAN_WF.replace("  tests:", "  other:"),
        }
        for name, wf in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual(ci_violations(wf, req), [], f"{name} must be reported")

    def test_control_commented_run_line_does_not_count(self):
        wf = _CLEAN_WF.replace("        run: python3 .claude/scripts/tests/test_a.py",
                               "        # run: python3 .claude/scripts/tests/test_a.py")
        self.assertNotEqual(ci_violations(wf, ("test_a.py",)), [])


# --- (2) same sentence in three flows, in the right section ---------------------------------------------
class VersionRaiseSentenceTests(unittest.TestCase):
    def test_sentence_sits_in_its_section_in_each_flow(self):
        for rel, rule in SENTENCE_PLACEMENT.items():
            with self.subTest(file=rel):
                p = PLUGIN_ROOT / rel
                self.assertTrue(p.is_file(), f"{rel} does not exist")
                self.assertEqual(sentence_violations(read(p), CANONICAL, rule), [], rel)

    def test_cited_heading_exists_in_claude_md(self):
        p = PLUGIN_ROOT / "CLAUDE.md"
        self.assertTrue(p.is_file(), "CLAUDE.md does not exist")
        lines = [ln.strip() for ln in read(p).splitlines()]
        self.assertIn(HEADING, lines, "CLAUDE.md lacks the heading the sentence cites")

    def test_control_correct_placement_has_no_violations(self):
        h = SENTENCE_PLACEMENT["agents/fullstack-code-reviewer.md"]
        self.assertEqual(sentence_violations(f"### Registry janitor duties (x)\n\n{CANONICAL}\n", CANONICAL, h), [])
        j = SENTENCE_PLACEMENT["skills/journal-add/SKILL.md"]
        self.assertEqual(sentence_violations(f"## Version raise\n\n- {CANONICAL}\n", CANONICAL, j), [])
        d = SENTENCE_PLACEMENT["skills/design-first/SKILL.md"]
        self.assertEqual(sentence_violations(f"{d[1]}\n\n{CANONICAL}\n", CANONICAL, d), [])

    def test_control_wrong_section_is_reported(self):
        h = SENTENCE_PLACEMENT["agents/fullstack-code-reviewer.md"]
        wrong = f"### Registry janitor duties\n\nnothing\n\n### Other\n\n{CANONICAL}\n"
        self.assertNotEqual(sentence_violations(wrong, CANONICAL, h), [], "sentence under the next heading")
        j = SENTENCE_PLACEMENT["skills/journal-add/SKILL.md"]
        self.assertNotEqual(sentence_violations(f"## Version raise\n\n## Other\n{CANONICAL}\n", CANONICAL, j), [])
        d = SENTENCE_PLACEMENT["skills/design-first/SKILL.md"]
        far = d[1] + "\n" + "\n".join("filler" for _ in range(12)) + "\n" + CANONICAL + "\n"
        self.assertNotEqual(sentence_violations(far, CANONICAL, d), [], "sentence beyond the 12-line window")

    def test_control_split_or_partial_sentence_is_reported(self):
        h = SENTENCE_PLACEMENT["agents/fullstack-code-reviewer.md"]
        split = f"### Registry janitor duties\n{CANONICAL[:60]}\n{CANONICAL[60:]}\n"
        self.assertNotEqual(sentence_violations(split, CANONICAL, h), [])
        self.assertNotEqual(sentence_violations("A registry append is a shipped change.", CANONICAL, h), [])


# --- (3) hook counts in the README and manifest descriptions --------------------------------------------
class HookCountTests(unittest.TestCase):
    def test_expected_counts_are_read(self):
        self.assertGreater(expected_hook_count(), 0, "no hook files read from .claude/hooks/")
        self.assertGreater(expected_registration_count(), 0, "no command entries read from hooks.json")

    def test_readme_hook_counts_equal_hook_file_count(self):
        found = readme_counts(read(PLUGIN_ROOT / "README.md"))
        self.assertTrue(found, "no hook count read in README.md")
        self.assertEqual(stale_counts(read(PLUGIN_ROOT / "README.md"), expected_hook_count()), [],
                         "README states a stale hook-file count")

    def test_readme_registration_counts_equal_hooks_json_entries(self):
        readme = read(PLUGIN_ROOT / "README.md")
        self.assertTrue(registration_counts(readme), "no 'N registrations' phrase read in README.md")
        self.assertEqual(stale_registrations(readme, expected_registration_count()), [],
                         "README states a stale registration count")

    def test_manifest_descriptions_state_the_real_hook_count(self):
        expected = expected_hook_count()
        for rel in MANIFESTS:
            with self.subTest(manifest=rel):
                p = PLUGIN_ROOT / rel
                self.assertTrue(p.is_file(), f"{rel} does not exist")
                descs = manifest_descriptions(json.loads(read(p)))
                self.assertTrue(descs, f"no description read in {rel}")
                if rel in MANIFESTS_WITH_COUNT:
                    self.assertTrue(any(readme_counts(d) for d in descs),
                                    f"no hook count read in {rel} descriptions")
                for d in descs:
                    self.assertEqual(stale_counts(d, expected), [], f"{rel} description has a stale hook count")

    def test_provider_table_row_is_among_scanned_occurrences(self):
        readme = read(PLUGIN_ROOT / "README.md")
        rows = re.findall(r"^\|\s*(\d+) hooks\s*\|", readme, re.M)
        self.assertTrue(rows, "no `| N hooks |` provider table row in README.md")
        scanned = {t.lower() for t, _ in readme_counts(readme)}
        for r in rows:
            self.assertIn(f"{r} hooks", scanned, "provider table row is not among the scanned occurrences")

    def test_control_broken_fixtures_are_reported(self):
        for fixture in ("12 generic hooks", "17 enforcement hooks", "twelve hook files",
                        "28 skills, 14 agents and 17 enforcement hooks that put design first",
                        "12 Claude Code enforcement hooks"):
            with self.subTest(fixture=fixture):
                self.assertNotEqual(stale_counts(fixture, 14), [], f"{fixture!r} must be reported")

    def test_control_three_word_gap_is_scanned_but_test_suites_are_not(self):
        self.assertEqual(readme_counts("12 Claude Code enforcement hooks"),
                         [("12 Claude Code enforcement hooks", 12)])
        self.assertEqual(readme_counts("9 hook test suites"), [])
        # the gap never spans a line break or a path: a layout row followed by a `hooks/` row is not a count
        self.assertEqual(readme_counts("6 generic data files\n  hooks/   14 generic hooks"),
                         [("14 generic hooks", 14)])

    def test_control_number_nearest_the_noun_is_taken(self):
        # a gap word may not itself be a number, so '14 agents and 13 hooks' reads 13, never 14
        self.assertEqual(readme_counts("14 agents and 13 hooks"), [("13 hooks", 13)])
        self.assertEqual(readme_counts("14 agents and thirteen hooks"), [("thirteen hooks", 13)])
        self.assertEqual(stale_counts("28 skills, 14 agents and 13 hooks that put design first", 13), [])
        self.assertEqual(stale_counts("14 agents and thirteen hooks", 13), [])
        wrong = stale_counts("14 agents and 13 hooks", 14)
        self.assertEqual(len(wrong), 1)
        self.assertIn("13", wrong[0])
        wrong_word = stale_counts("14 agents and thirteen hooks", 14)
        self.assertEqual(len(wrong_word), 1)
        self.assertIn("thirteen", wrong_word[0])
        only17 = stale_counts("28 skills, 14 agents and 17 enforcement hooks", 13)
        self.assertEqual(len(only17), 1)
        self.assertIn("(17)", only17[0])

    def test_control_files_and_registrations_are_separate_measures(self):
        with tempfile.TemporaryDirectory() as tmp:
            def dir_with(n_files: int) -> Path:
                d = Path(tmp) / f"hooks{n_files}"
                d.mkdir()
                for i in range(n_files):
                    (d / f"h{i}.py").write_text("", encoding="utf-8")
                (d / "_helper.py").write_text("", encoding="utf-8")
                (d / "gate-launch.py").write_text("", encoding="utf-8")
                return d

            def cfg(n_entries: int) -> dict:
                return {"hooks": {"E": [{"hooks": [{"command": str(i)} for i in range(n_entries)]}]}}

            files15, files14 = hook_file_count(dir_with(15)), hook_file_count(dir_with(14))
            self.assertEqual((files15, files14), (15, 14), "underscore files and gate-launch.py are excluded")
            entries14, entries15 = hook_command_count(cfg(14)), hook_command_count(cfg(15))
            hooks_phrase, reg_phrase = "It ships 14 hooks.", "That makes 14 registrations."
            # 15 files, 14 entries: '14 hooks' is stale, '14 registrations' is clean
            self.assertNotEqual(stale_counts(hooks_phrase, files15), [])
            self.assertEqual(stale_registrations(reg_phrase, entries14), [])
            # 14 files, 15 entries: '14 hooks' is clean, '14 registrations' is stale
            self.assertEqual(stale_counts(hooks_phrase, files14), [])
            self.assertNotEqual(stale_registrations(reg_phrase, entries15), [])
            # words work too, and the two scans do not read each other's phrases
            self.assertNotEqual(stale_registrations("fourteen registrations", 15), [])
            self.assertEqual(stale_counts(reg_phrase, 99), [])
            self.assertEqual(stale_registrations(hooks_phrase, 99), [])

    def test_control_correct_fixtures_are_clean(self):
        for fixture in ("14 hooks", "14 generic hooks", "fourteen hook files", "| 14 hooks | yes |",
                        "Version 0.7.0 retired six hooks.", "9 hook test suites", "the hooks run twice"):
            with self.subTest(fixture=fixture):
                self.assertEqual(stale_counts(fixture, 14), [], f"{fixture!r} must not be reported")

    def test_control_command_entry_count(self):
        cfg = {"hooks": {"A": [{"hooks": [1, 2]}, {"hooks": [3]}], "B": [{"hooks": [4]}]}}
        self.assertEqual(hook_command_count(cfg), 4)


# --- (4) README tree and provider-table counts (issue 363; contract 2026-11-11-audit-followups-165, V9, Q1, Q2) -----
# Count-claim oracle: each noun a README count can name maps to one filesystem measure. The skill measure and the
# agent measure are separate; "subagents" is the Claude Code word for the agent files, so it reads the agent measure.
# Q2: a hook data file is a `.json` file directly in .claude/hooks/ other than hooks.json.
CLAUDE_DIR = PLUGIN_ROOT / ".claude"
_ORACLE_NOUNS = (
    ("working agreements", "agreements"), ("subagents", "agents"), ("skills", "skills"), ("agents", "agents"),
    ("hooks", "hooks"), ("shared helper modules", "helpers"), ("generic data files", "data_files"),
    ("document templates", "templates"), ("reference documents", "references"), ("add-ons", "addons"),
)
_CLAIM_RE = re.compile(
    r"(?i)(?<![\w.])(\d+|" + "|".join(w for w in WORDS if w != "zero") + r")[ \t]+(?:[\w-]+[ \t]+){0,2}?("
    + "|".join(re.escape(n) for n, _ in _ORACLE_NOUNS) + r")\b")
_NOUN_MEASURE = dict(_ORACLE_NOUNS)
# tree lines that must carry no number at all (Q1), keyed by (parent label, label)
_NUMBER_FREE_LINES = (("hooks/", "tests/"), (".claude/", "scripts/"), ("scripts/", "tests/"))


def count_oracles(root: Path) -> dict[str, int]:
    """Filesystem oracle for each measure a README tree line or provider-table row can claim."""
    claude = root / ".claude"
    hooks = claude / "hooks"
    return {
        "skills": sum(1 for p in (root / "skills").glob("*/SKILL.md") if p.is_file()),
        "agents": sum(1 for p in (root / "agents").glob("*.md") if p.is_file()),
        "agreements": sum(1 for p in (claude / "agreements").glob("*.md") if p.is_file()),
        "addons": sum(1 for p in (claude / "addons").glob("*/addon.json") if p.is_file()),
        "hooks": hook_file_count(hooks),
        "helpers": sum(1 for p in hooks.glob("_*.py") if p.is_file()),
        "data_files": sum(1 for p in hooks.glob("*.json") if p.is_file() and p.name != "hooks.json"),
        "templates": sum(1 for p in (claude / "templates").glob("*.md") if p.is_file()),
        "references": sum(1 for p in (claude / "references").glob("*.md") if p.is_file()),
    }


def claim_violations(line: str, oracles: dict[str, int]) -> list[str]:
    """Each 'N <noun>' claim on one line that differs from its oracle."""
    out = []
    for m in _CLAIM_RE.finditer(line):
        tok = m.group(1).lower()
        n = int(tok) if tok.isdigit() else WORDS[tok]
        measure = _NOUN_MEASURE[m.group(2).lower()]
        if n != oracles[measure]:
            out.append(f"says '{re.sub(chr(32) + '+', ' ', m.group(0))}' ({n}) but the {measure} oracle is {oracles[measure]}")
    return out


def tree_block(readme: str) -> list[str]:
    """Lines of the first fenced block under '## What is included'."""
    m = re.search(r"^## What is included\s*\n```[^\n]*\n(.*?)^```", readme, re.M | re.S)
    return m.group(1).splitlines() if m else []


def provider_rows(readme: str) -> list[str]:
    """Table rows under '### What each provider actually gets'."""
    m = re.search(r"^### What each provider actually gets\s*\n(.*?)(?=^#{1,3} |\Z)", readme, re.M | re.S)
    return [ln for ln in m.group(1).splitlines() if ln.startswith("|")] if m else []


def tree_count_violations(lines: list[str], oracles: dict[str, int]) -> list[str]:
    """Counts on tree lines must match the oracle; the Q1 lines must carry no number."""
    out = []
    stack: list[tuple[int, str]] = []  # (indent, label) of the enclosing lines
    for ln in lines:
        if not ln.strip():
            continue
        indent = len(ln) - len(ln.lstrip())
        while stack and stack[-1][0] >= indent:
            stack.pop()
        label = ln.split()[0]
        parent = stack[-1][1] if stack else ""
        stack.append((indent, label))
        for v in claim_violations(ln, oracles):
            out.append(f"tree line '{ln.strip()}': {v}")
        if (parent, label) in _NUMBER_FREE_LINES and re.search(r"(?i)(?<![\w.])\d+(?![\w.])", ln[len(label) + indent:]):
            out.append(f"tree line '{ln.strip()}' carries a number; Q1 keeps the {label} line number-free")
    return out


def provider_table_violations(rows: list[str], oracles: dict[str, int]) -> list[str]:
    out = []
    for ln in rows:
        first_cell = ln.strip("|").split("|")[0]
        out += [f"provider row '{first_cell.strip()}': {v}" for v in claim_violations(first_cell, oracles)]
    return out


_TREE_FIXTURE = """\
skills/          34 generic skills
.claude/
  hooks/         14 generic hooks, a gate launcher, 8 shared helper modules, 5 generic data files
    tests/       23 hook test suites
  scripts/       workflow scripts
    tests/       suites
"""


class ReadmeCountPinTests(unittest.TestCase):
    """Real assertions read the README and the filesystem only; none reads a manifest (I-2)."""

    def test_oracles_are_read(self):
        for name, n in count_oracles(PLUGIN_ROOT).items():
            self.assertGreater(n, 0, f"oracle {name} read nothing")

    def test_tree_counts_match_oracles(self):
        lines = tree_block(read(PLUGIN_ROOT / "README.md"))
        self.assertTrue(lines, "no tree block under '## What is included'")
        self.assertEqual(tree_count_violations(lines, count_oracles(PLUGIN_ROOT)), [])

    def test_provider_table_counts_match_oracles(self):
        rows = provider_rows(read(PLUGIN_ROOT / "README.md"))
        self.assertTrue(rows, "no provider table under '### What each provider actually gets'")
        self.assertEqual(provider_table_violations(rows, count_oracles(PLUGIN_ROOT)), [])

    def test_every_oracle_is_claimed_in_the_tree_or_table(self):
        readme = read(PLUGIN_ROOT / "README.md")
        text = "\n".join(tree_block(readme) + provider_rows(readme))
        claimed = {_NOUN_MEASURE[m.group(2).lower()] for m in _CLAIM_RE.finditer(text)}
        self.assertEqual(claimed, set(count_oracles(PLUGIN_ROOT)), "a measure is never read from the README")

    def test_control_wrong_tree_counts_are_reported(self):
        oracles = {"skills": 34, "agents": 15, "agreements": 7, "addons": 3, "hooks": 14, "helpers": 8,
                   "data_files": 5, "templates": 6, "references": 4}
        clean = _TREE_FIXTURE.replace("23 hook test suites", "hook test suites")
        self.assertEqual(tree_count_violations(clean.splitlines(), oracles), [])
        for old, new in (("34 generic skills", "33 generic skills"), ("5 generic data files", "6 generic data files"),
                         ("8 shared", "9 shared"), ("14 generic hooks", "twelve generic hooks")):
            with self.subTest(change=new):
                self.assertNotEqual(tree_count_violations(clean.replace(old, new).splitlines(), oracles), [])

    def test_control_number_free_lines_reject_a_number(self):
        oracles = {"skills": 34, "hooks": 14, "helpers": 8, "data_files": 5}
        # the fixture's 'tests/ 23 hook test suites' line sits under hooks/, so only it is reported
        v = tree_count_violations(_TREE_FIXTURE.splitlines(), oracles)
        self.assertEqual(len(v), 1, v)
        self.assertIn("23 hook test suites", v[0])
        self.assertNotEqual(tree_count_violations([".claude/", "  scripts/       23 workflow scripts"], {}), [])
        self.assertNotEqual(tree_count_violations(["  scripts/       x", "    tests/       36 suites"], {}), [])
        self.assertEqual(tree_count_violations([".claude/", "  scripts/       workflow scripts",
                                                "    tests/       suites"], {}), [])

    def test_control_provider_rows_skill_agent_subagent_measures(self):
        oracles = {"skills": 34, "agents": 15, "hooks": 14, "agreements": 7}
        clean = ["| 34 skills | yes | yes | yes |", "| 15 agents | yes | yes | no |",
                 "| 15 subagents | yes | yes | no |", "| 14 hooks | yes | no | no |",
                 "| 7 working agreements, delivered by a hook | yes | no | no |"]
        self.assertEqual(provider_table_violations(clean, oracles), [])
        for row in ("| 33 skills | yes |", "| 14 agents | yes |", "| 14 subagents | yes |",
                    "| fifteen skills | yes |", "| 13 hooks | yes |", "| 6 working agreements | yes |"):
            with self.subTest(row=row):
                self.assertNotEqual(provider_table_violations([row], oracles), [])

    def test_control_manifest_shaped_description_string(self):
        # a string shaped like a manifest description, fed to the same helper; no real manifest is read (I-2)
        description = "28 skills, 14 agents and 17 enforcement hooks that put design first"
        oracles = {"skills": 34, "agents": 15, "hooks": 14}
        v = claim_violations(description, oracles)
        self.assertEqual(len(v), 3, v)
        self.assertEqual(claim_violations("34 skills, 15 agents and 14 hooks", oracles), [])

    def test_control_oracle_reads_a_fixture_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ("skills/a/SKILL.md", "skills/b/SKILL.md", "agents/x.md", ".claude/hooks/h.py",
                        ".claude/hooks/gate-launch.py", ".claude/hooks/_u.py", ".claude/hooks/hooks.json",
                        ".claude/hooks/r.rules.json", ".claude/agreements/g.md", ".claude/addons/q/addon.json",
                        ".claude/templates/t.md", ".claude/references/r.md"):
                f = root / rel
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text("", encoding="utf-8")
            (root / "skills" / "empty").mkdir()  # a folder with no SKILL.md is not a skill
            self.assertEqual(count_oracles(root), {
                "skills": 2, "agents": 1, "agreements": 1, "addons": 1, "hooks": 1, "helpers": 1,
                "data_files": 1, "templates": 1, "references": 1})


if __name__ == "__main__":
    unittest.main()
